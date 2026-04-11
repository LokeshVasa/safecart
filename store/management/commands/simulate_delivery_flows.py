import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from django.contrib.auth.models import User

from store.models import Address, Order, OrderItem, Product, SecurityEventLog
from store.services.otp_service import get_or_create_order_otp_payload, verify_order_otp
from store.services.qr_service import claim_order_from_token


class Command(BaseCommand):
    help = "Simulate SafeCart delivery flows for demo and reporting."

    def add_arguments(self, parser):
        parser.add_argument("--orders", type=int, default=10, help="Number of orders to simulate.")
        parser.add_argument("--secure-ratio", type=float, default=0.7, help="Share of secure orders.")
        parser.add_argument("--delivered-ratio", type=float, default=0.7, help="Share of orders delivered.")
        parser.add_argument("--attack-ratio", type=float, default=0.2, help="Share of orders with attack simulation.")
        parser.add_argument("--seed", type=int, default=42, help="Random seed.")
        parser.add_argument("--buyer-id", type=int, help="Buyer user id.")
        parser.add_argument("--agent-id", type=int, help="Delivery agent user id.")
        parser.add_argument("--buyer-username", type=str, help="Buyer username.")
        parser.add_argument("--agent-username", type=str, help="Delivery agent username.")

    def handle(self, *args, **options):
        random.seed(options["seed"])
        orders_count = max(1, options["orders"])
        secure_ratio = min(max(options["secure_ratio"], 0.0), 1.0)
        delivered_ratio = min(max(options["delivered_ratio"], 0.0), 1.0)
        attack_ratio = min(max(options["attack_ratio"], 0.0), 1.0)

        buyer_id = options.get("buyer_id")
        agent_id = options.get("agent_id")
        buyer_username = (options.get("buyer_username") or "").strip()
        agent_username = (options.get("agent_username") or "").strip()

        buyer_user = None
        agent_user = None

        if buyer_id:
            buyer_user = User.objects.filter(id=buyer_id).first()
        if agent_id:
            agent_user = User.objects.filter(id=agent_id).first()

        if not buyer_user and buyer_username:
            buyer_user = User.objects.filter(username=buyer_username).first()
        if not agent_user and agent_username:
            agent_user = User.objects.filter(username=agent_username).first()

        if not buyer_user or not agent_user:
            self.stdout.write(self.style.ERROR("Buyer or agent user not found. Provide valid ids or usernames."))
            return

        if not agent_user.groups.filter(name="DeliveryAgent").exists():
            self.stdout.write(self.style.ERROR("Agent user must be in the DeliveryAgent group."))
            return

        products = list(Product.objects.all()[:5])
        if not products:
            self.stdout.write(self.style.ERROR("No products available to simulate orders."))
            return

        address = Address.objects.filter(user=buyer_user, is_confirmed=True).first()
        if not address:
            self.stdout.write(self.style.ERROR("Buyer must have a confirmed address to simulate orders."))
            return

        self.stdout.write(self.style.SUCCESS("Starting simulation..."))

        created_orders = 0
        delivered_orders = 0
        secure_orders = 0
        traditional_orders = 0
        attack_attempts = 0
        start_time = timezone.now()

        for _ in range(orders_count):
            is_secure = random.random() < secure_ratio
            should_deliver = random.random() < delivered_ratio
            simulate_attack = random.random() < attack_ratio
            delivery_mode = "secure" if is_secure else "traditional"

            with transaction.atomic():
                order = Order.objects.create(
                    user=buyer_user,
                    address=address,
                    payment_type="COD",
                    token_value=str(uuid.uuid4()),
                    expires_at=None,
                    status="Pending",
                    delivery_mode=delivery_mode,
                )

                product = random.choice(products)
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=random.randint(1, 3),
                    price=product.price,
                )

                if is_secure:
                    secure_orders += 1
                    # Simulate QR scan to assign agent.
                    order = claim_order_from_token(token=order.token_value, user=agent_user)
                    order.refresh_from_db(fields=["delivery_agent"])

                    if simulate_attack:
                        attack_attempts += 1
                        # Wrong OTP attempt
                        try:
                            verify_order_otp(
                                order,
                                buyer_user,
                                customer_half="0000",
                                agent_half="9999",
                            )
                        except Exception:
                            pass

                    if should_deliver:
                        payload = get_or_create_order_otp_payload(order, agent_user)
                        verify_order_otp(
                            order,
                            buyer_user,
                            customer_half=payload["customer_half"],
                            agent_half=payload["agent_half"],
                        )
                        verify_order_otp(
                            order,
                            agent_user,
                            customer_half=payload["customer_half"],
                            agent_half=payload["agent_half"],
                        )
                else:
                    traditional_orders += 1
                    if simulate_attack:
                        attack_attempts += 1
                        # Traditional flow should block OTP requests
                        try:
                            get_or_create_order_otp_payload(order, agent_user)
                        except Exception:
                            pass
                    if should_deliver:
                        order.status = "Delivered"
                        order.expires_at = timezone.now()
                        order.save(update_fields=["status", "expires_at"])

            created_orders += 1
            if order.status == "Delivered":
                delivered_orders += 1

        delivered_rate = round((delivered_orders / created_orders) * 100, 1) if created_orders else 0

        event_qs = SecurityEventLog.objects.filter(created_at__gte=start_time)
        qr_blocked = event_qs.filter(event_type="qr_scan_blocked").count()
        otp_failed = event_qs.filter(event_type="otp_verify_failed").count()
        otp_blocked = event_qs.filter(event_type="otp_request_blocked").count()
        mode_switches = event_qs.filter(event_type="delivery_mode_switched").count()

        self.stdout.write(self.style.SUCCESS("Simulation complete."))
        self.stdout.write(f"Total orders: {created_orders}")
        self.stdout.write(f"Secure orders: {secure_orders}")
        self.stdout.write(f"Traditional orders: {traditional_orders}")
        self.stdout.write(f"Delivered orders: {delivered_orders} ({delivered_rate}%)")
        self.stdout.write(f"Attack attempts simulated: {attack_attempts}")
        self.stdout.write(f"QR blocked events: {qr_blocked}")
        self.stdout.write(f"OTP failed events: {otp_failed}")
        self.stdout.write(f"OTP blocked events: {otp_blocked}")
        self.stdout.write(f"Mode switch events: {mode_switches}")
