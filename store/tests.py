import hashlib
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Address, DeliveryAgent, Order, OrderOTP, SecurityEventLog
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

    def test_successful_qr_scan_creates_security_event_log(self):
        self.client.get(reverse('get_order_by_token'), {'token': self.order.token_value})

        event = SecurityEventLog.objects.filter(order=self.order, event_type='qr_scan').latest('created_at')

        self.assertEqual(event.outcome, 'success')
        self.assertEqual(event.actor, self.agent_user)
        self.assertIsNotNone(event.duration_ms)

    def test_successful_otp_request_creates_security_event_log(self):
        self.order.delivery_agent = self.delivery_agent
        self.order.status = 'Shipped'
        self.order.save(update_fields=['delivery_agent', 'status'])

        response = self.client.get(reverse('generate_order_otp', args=[self.order.id]))

        self.assertEqual(response.status_code, 200)
        event = SecurityEventLog.objects.filter(order=self.order, event_type='otp_requested').latest('created_at')
        self.assertEqual(event.outcome, 'success')
        self.assertEqual(event.actor, self.agent_user)
        self.assertIsNotNone(event.duration_ms)

    def test_failed_otp_verify_creates_timed_security_event_log(self):
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
            agent_verified=False,
            is_active=True,
        )
        self.client.logout()
        self.client.login(username='buyer', password='testpass123')

        response = self.client.post(
            reverse('verify_otp', args=[self.order.id]),
            data='{"customer_half":"0000","agent_half":"9999"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['success'])
        event = SecurityEventLog.objects.filter(order=self.order, event_type='otp_verify_failed').latest('created_at')
        self.assertEqual(event.outcome, 'failed')
        self.assertIsNotNone(event.duration_ms)


class AdminSecurityLogsTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
        )
        self.buyer = User.objects.create_user(
            username='buyer2',
            email='buyer2@example.com',
            password='buyerpass123',
        )
        self.address = Address.objects.create(
            user=self.buyer,
            street='10 Downing Street',
            city='London',
            state='London',
            pincode='100001',
            is_confirmed=True,
        )
        self.order = Order.objects.create(
            user=self.buyer,
            address=self.address,
            payment_type='COD',
            token_value='token-admin-log',
            status='Shipped',
        )
        SecurityEventLog.objects.create(
            order=self.order,
            actor=self.buyer,
            event_type='qr_scan',
            outcome='success',
            duration_ms=120,
            details={'reason': 'valid_scan'},
        )
        SecurityEventLog.objects.create(
            order=self.order,
            actor=self.buyer,
            event_type='otp_verify_failed',
            outcome='failed',
            duration_ms=220,
            details={'reason': 'hash_mismatch'},
        )
        self.client.login(username='admin', password='adminpass123')

    def test_admin_security_logs_page_loads(self):
        response = self.client.get(reverse('admin_security_logs'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Security & Performance Logs')
        self.assertContains(response, 'QR Scan')
        self.assertContains(response, 'OTP Verify Failed')

    def test_admin_security_logs_page_filters_by_outcome(self):
        response = self.client.get(reverse('admin_security_logs'), {'outcome': 'failed'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OTP Verify Failed')
        self.assertNotContains(response, 'valid_scan')

    def test_admin_security_logs_page_filters_by_delivery_mode(self):
        self.order.delivery_mode = 'traditional'
        self.order.save(update_fields=['delivery_mode'])

        response = self.client.get(reverse('admin_security_logs'), {'delivery_mode': 'traditional'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<td class="fw-semibold">QR Scan</td>', html=False)
        response_secure = self.client.get(reverse('admin_security_logs'), {'delivery_mode': 'secure'})
        self.assertEqual(response_secure.status_code, 200)
        self.assertContains(response_secure, 'No security events match the current filters.')
        self.assertNotContains(response_secure, '<td class="fw-semibold">QR Scan</td>', html=False)


class DeliveryModeComparisonTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin2',
            email='admin2@example.com',
            password='adminpass123',
        )
        self.buyer = User.objects.create_user(
            username='buyer3',
            email='buyer3@example.com',
            password='buyerpass123',
        )
        self.address = Address.objects.create(
            user=self.buyer,
            street='42 Test Street',
            city='Pune',
            state='MH',
            pincode='411001',
            is_confirmed=True,
        )
        Order.objects.create(
            user=self.buyer,
            address=self.address,
            payment_type='COD',
            token_value='token-secure-mode',
            status='Delivered',
            delivery_mode='secure',
        )
        Order.objects.create(
            user=self.buyer,
            address=self.address,
            payment_type='COD',
            token_value='token-traditional-mode',
            status='Shipped',
            delivery_mode='traditional',
        )
        self.client.login(username='admin2', password='adminpass123')

    def test_admin_dashboard_shows_delivery_mode_comparison(self):
        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Delivery Mode Comparison')
        self.assertContains(response, 'SafeCart Secure')
        self.assertContains(response, 'Traditional Delivery')

    def test_admin_can_toggle_delivery_mode(self):
        DeliveryAgent.objects.create(user=self.admin_user)
        order = Order.objects.create(
            user=self.buyer,
            address=self.address,
            payment_type='COD',
            token_value='token-toggle-mode',
            status='Pending',
            delivery_mode='secure',
        )

        response = self.client.post(reverse('toggle_delivery_mode', args=[order.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.delivery_mode, 'traditional')
        self.assertTrue(
            SecurityEventLog.objects.filter(order=order, event_type='delivery_mode_switched').exists()
        )

    def test_admin_cannot_toggle_delivery_mode_after_shipped(self):
        DeliveryAgent.objects.create(user=self.admin_user)
        order = Order.objects.create(
            user=self.buyer,
            address=self.address,
            payment_type='COD',
            token_value='token-toggle-blocked',
            status='Shipped',
            delivery_mode='secure',
        )

        response = self.client.post(reverse('toggle_delivery_mode', args=[order.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.delivery_mode, 'secure')


class TraditionalDeliveryFlowTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username='buyer4',
            email='buyer4@example.com',
            password='buyerpass123',
        )
        self.agent_user = User.objects.create_user(
            username='agent4',
            email='agent4@example.com',
            password='agentpass123',
        )
        delivery_group = Group.objects.get(name='DeliveryAgent')
        self.agent_user.groups.add(delivery_group)
        self.delivery_agent = DeliveryAgent.objects.create(user=self.agent_user)
        self.address = Address.objects.create(
            user=self.buyer,
            street='77 Sample Street',
            city='Hyderabad',
            state='TG',
            pincode='500001',
            is_confirmed=True,
        )
        self.order = Order.objects.create(
            user=self.buyer,
            address=self.address,
            payment_type='COD',
            token_value='token-traditional-flow',
            status='Shipped',
            delivery_mode='traditional',
            delivery_agent=self.delivery_agent,
        )
        self.client.login(username='agent4', password='agentpass123')

    def test_traditional_order_blocks_otp_request(self):
        response = self.client.get(reverse('generate_order_otp', args=[self.order.id]))
        self.assertEqual(response.status_code, 400)
        self.assertIn("Traditional delivery does not require OTP", response.json()["error"])

    def test_traditional_order_can_be_marked_delivered(self):
        response = self.client.post(reverse('mark_order_delivered', args=[self.order.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'Delivered')
