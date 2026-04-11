import hashlib
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Address, DeliveryAgent, Order, OrderOTP
from .services.security_service import (
    DeliverySecurityError,
    get_order_security_snapshot,
    validate_otp_read_security,
    validate_otp_request_security,
    validate_qr_scan_security,
)
from .utils import encrypt_value


class DeliveryQrScanTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer',
            email='buyer@example.com',
            password='testpass123',
        )
        self.agent_user = User.objects.create_user(
            username='agent',
            email='agent@example.com',
            password='testpass123',
        )

        delivery_group = Group.objects.get(name='DeliveryAgent')
        self.agent_user.groups.add(delivery_group)
        self.delivery_agent = DeliveryAgent.objects.create(user=self.agent_user)

        self.address = Address.objects.create(
            user=self.user,
            street='221B Baker Street',
            city='London',
            state='London',
            pincode='123456',
            is_confirmed=True,
        )

        self.order = Order.objects.create(
            user=self.user,
            address=self.address,
            payment_type='COD',
            token_value='token-123',
            expires_at=None,
            status='Pending',
        )

        self.client.login(username='agent', password='testpass123')

    def test_first_scan_starts_one_hour_window_and_assigns_agent(self):
        response = self.client.get(reverse('get_order_by_token'), {'token': self.order.token_value})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['security']['security_stage'], 'qr_active')
        self.order.refresh_from_db()

        self.assertEqual(self.order.qr_scan_count, 1)
        self.assertEqual(self.order.delivery_agent, self.delivery_agent)
        self.assertEqual(self.order.status, 'Shipped')
        self.assertIsNotNone(self.order.expires_at)
        self.assertAlmostEqual(
            self.order.expires_at,
            timezone.now() + timedelta(hours=1),
            delta=timedelta(seconds=10),
        )

    def test_third_scan_is_blocked(self):
        self.client.get(reverse('get_order_by_token'), {'token': self.order.token_value})
        self.client.get(reverse('get_order_by_token'), {'token': self.order.token_value})

        response = self.client.get(reverse('get_order_by_token'), {'token': self.order.token_value})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'This QR code can only be scanned 2 times.')
        self.order.refresh_from_db()
        self.assertEqual(self.order.qr_scan_count, 2)

    def test_second_scan_renews_expired_qr_window(self):
        self.client.get(reverse('get_order_by_token'), {'token': self.order.token_value})
        self.order.expires_at = timezone.now() - timedelta(minutes=1)
        self.order.save(update_fields=['expires_at'])

        response = self.client.get(reverse('get_order_by_token'), {'token': self.order.token_value})

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.qr_scan_count, 2)
        self.assertGreater(self.order.expires_at, timezone.now())

    def test_open_delivered_order_redirects_to_dashboard(self):
        self.order.delivery_agent = self.delivery_agent
        self.order.status = 'Delivered'
        self.order.save(update_fields=['delivery_agent', 'status'])

        response = self.client.get(
            reverse('delivery_order_detail'),
            {'order-id': self.order.id},
            follow=True,
        )

        self.assertRedirects(response, reverse('delivery_dashboard'))
        messages = list(response.context['messages'])
        self.assertTrue(any('already delivered' in str(message).lower() for message in messages))

    def test_expired_open_order_redirects_to_route_view(self):
        self.order.delivery_agent = self.delivery_agent
        self.order.status = 'Shipped'
        self.order.qr_scan_count = 1
        self.order.expires_at = timezone.now() - timedelta(minutes=1)
        self.order.save(update_fields=['delivery_agent', 'status', 'qr_scan_count', 'expires_at'])

        response = self.client.get(
            reverse('delivery_order_detail'),
            {'order-id': self.order.id},
        )

        self.assertRedirects(response, f"{reverse('delivery_route_detail')}?order-id={self.order.id}")

    def test_assigned_agent_can_request_new_otp_after_expiry(self):
        self.order.delivery_agent = self.delivery_agent
        self.order.status = 'Shipped'
        self.order.qr_scan_count = 1
        self.order.expires_at = timezone.now() - timedelta(minutes=1)
        self.order.save(update_fields=['delivery_agent', 'status', 'qr_scan_count', 'expires_at'])

        response = self.client.get(reverse('generate_order_otp', args=[self.order.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertIn('agent_half', payload)
        self.assertEqual(payload['security']['security_stage'], 'otp_active')

    def test_assigned_agent_can_poll_otp_status(self):
        self.order.delivery_agent = self.delivery_agent
        self.order.status = 'Shipped'
        self.order.save(update_fields=['delivery_agent', 'status'])
        OrderOTP.objects.create(
            order=self.order,
            otp_hash='hash',
            enc_customer_half=encrypt_value('1234'),
            enc_agent_half=encrypt_value('5678'),
            expires_at=timezone.now() + timedelta(minutes=10),
            customer_verified=False,
            agent_verified=True,
        )

        response = self.client.get(reverse('get_order_otp', args=[self.order.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['security']['security_stage'], 'otp_active')

    def test_delivered_order_still_returns_otp_completion_status(self):
        self.order.delivery_agent = self.delivery_agent
        self.order.status = 'Delivered'
        self.order.save(update_fields=['delivery_agent', 'status'])
        OrderOTP.objects.create(
            order=self.order,
            otp_hash='hash',
            enc_customer_half=encrypt_value('1234'),
            enc_agent_half=encrypt_value('5678'),
            expires_at=timezone.now() + timedelta(minutes=10),
            customer_verified=True,
            agent_verified=True,
            is_active=False,
        )

        response = self.client.get(reverse('get_order_otp', args=[self.order.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertTrue(payload['order_delivered'])
        self.assertEqual(payload['security']['security_stage'], 'delivered')

    def test_verify_otp_returns_security_snapshot(self):
        self.order.delivery_agent = self.delivery_agent
        self.order.status = 'Shipped'
        self.order.save(update_fields=['delivery_agent', 'status'])
        OrderOTP.objects.create(
            order=self.order,
            otp_hash=hashlib.sha256('12345678'.encode()).hexdigest(),
            enc_customer_half=encrypt_value('1234'),
            enc_agent_half=encrypt_value('5678'),
            expires_at=timezone.now() + timedelta(minutes=10),
            customer_verified=False,
            agent_verified=True,
            is_active=True,
        )
        self.client.logout()
        self.client.login(username='buyer', password='testpass123')

        response = self.client.post(
            reverse('verify_otp', args=[self.order.id]),
            data='{"customer_half":"1234","agent_half":"5678"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['security']['security_stage'], 'delivered')

    def test_customer_can_cancel_pending_order(self):
        self.client.logout()
        self.client.login(username='buyer', password='testpass123')
        response = self.client.post(reverse('cancel_order', args=[self.order.id]), follow=True)

        self.assertRedirects(response, reverse('yourorders'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'Cancelled')

    def test_customer_cannot_cancel_shipped_order(self):
        self.client.logout()
        self.client.login(username='buyer', password='testpass123')
        self.order.status = 'Shipped'
        self.order.save(update_fields=['status'])

        response = self.client.post(reverse('cancel_order', args=[self.order.id]), follow=True)

        self.assertRedirects(response, reverse('yourorders'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'Shipped')

    def test_security_snapshot_marks_active_qr_flow(self):
        self.order.delivery_agent = self.delivery_agent
        self.order.status = 'Shipped'
        self.order.qr_scan_count = 1
        self.order.expires_at = timezone.now() + timedelta(minutes=20)
        self.order.save(update_fields=['delivery_agent', 'status', 'qr_scan_count', 'expires_at'])

        snapshot = get_order_security_snapshot(self.order)

        self.assertEqual(snapshot['security_stage'], 'qr_active')
        self.assertTrue(snapshot['full_delivery_access'])
        self.assertFalse(snapshot['route_only_access'])
        self.assertEqual(snapshot['remaining_scans'], 1)

    def test_security_snapshot_marks_route_only_and_otp_active(self):
        self.order.delivery_agent = self.delivery_agent
        self.order.status = 'Shipped'
        self.order.qr_scan_count = 1
        self.order.expires_at = timezone.now() - timedelta(minutes=5)
        self.order.save(update_fields=['delivery_agent', 'status', 'qr_scan_count', 'expires_at'])
        OrderOTP.objects.create(
            order=self.order,
            otp_hash='hash',
            enc_customer_half=encrypt_value('1234'),
            enc_agent_half=encrypt_value('5678'),
            expires_at=timezone.now() + timedelta(minutes=10),
            customer_verified=False,
            agent_verified=False,
            is_active=True,
        )

        snapshot = get_order_security_snapshot(self.order)

        self.assertEqual(snapshot['security_stage'], 'otp_active')
        self.assertFalse(snapshot['full_delivery_access'])
        self.assertTrue(snapshot['route_only_access'])
        self.assertTrue(snapshot['otp_reissue_allowed'])

    def test_security_snapshot_marks_verified_delivery(self):
        self.order.delivery_agent = self.delivery_agent
        self.order.status = 'Delivered'
        self.order.qr_scan_count = 1
        self.order.expires_at = timezone.now()
        self.order.save(update_fields=['delivery_agent', 'status', 'qr_scan_count', 'expires_at'])
        OrderOTP.objects.create(
            order=self.order,
            otp_hash='hash',
            enc_customer_half=encrypt_value('1234'),
            enc_agent_half=encrypt_value('5678'),
            expires_at=timezone.now() + timedelta(minutes=10),
            customer_verified=True,
            agent_verified=True,
            is_active=False,
        )

        snapshot = get_order_security_snapshot(self.order)

        self.assertEqual(snapshot['security_stage'], 'delivered')
        self.assertTrue(snapshot['both_verified'])
        self.assertTrue(snapshot['is_closed'])

    def test_qr_scan_security_blocks_delivered_order(self):
        self.order.status = 'Delivered'
        self.order.save(update_fields=['status'])

        with self.assertRaises(DeliverySecurityError):
            validate_qr_scan_security(self.order)

    def test_otp_request_security_allows_route_only_order(self):
        self.order.status = 'Shipped'
        self.order.qr_scan_count = 1
        self.order.expires_at = timezone.now() - timedelta(minutes=2)
        self.order.save(update_fields=['status', 'qr_scan_count', 'expires_at'])

        security = validate_otp_request_security(self.order)

        self.assertTrue(security['route_only_access'])
        self.assertTrue(security['otp_reissue_allowed'])

    def test_otp_read_security_blocks_cancelled_order(self):
        self.order.status = 'Cancelled'
        self.order.save(update_fields=['status'])

        with self.assertRaises(DeliverySecurityError):
            validate_otp_read_security(self.order)
