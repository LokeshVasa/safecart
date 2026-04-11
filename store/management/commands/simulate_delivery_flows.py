import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from django.contrib.auth.models import User

from store.models import Address, Order, OrderItem, Product
from store.services.otp_service import get_or_create_order_otp_payload, verify_order_otp
from store.services.qr_service import claim_order_from_token


class Command(BaseCommand):
    help = "Simulate SafeCart delivery flows for demo and reporting."

    def add_arguments(self, parser):
        parser.add_argument("--orders", type=int, default=10, help="Number of orders to simulate.")
        parser.add_argument("--secure-ratio", type=float, default=0.7, help="Share of secure orders.")
        parser.add_argument("--delivered-ratio", type=float, default=0.7, help="Share of orders delivered.")
        parser.add_argument("--seed", type=int, default=42, help="Random seed.")
        parser.add_argument("--buyer-id", type=int, required=True, help="Buyer user id.")
        parser.add_argument("--agent-id", type=int, required=True, help="Delivery agent user id.")

    def handle(self, *args, **options):
        random.seed(options["seed"])
        orders_count = max(1, options["orders"])
        secure_ratio = min(max(options["secure_ratio"], 0.0), 1.0)
        delivered_ratio = min(max(options["delivered_ratio"], 0.0), 1.0)

        buyer_id = options["buyer_id"]
        agent_id = options["agent_id"]

        try:
            buyer_user = User.objects.get(id=buyer_id)
            agent_user = User.objects.get(id=agent_id)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR("Buyer or agent user id not found."))
            return

        if not agent_user.groups.filter(name="DeliveryAgent").exists():
            self.stdout.write(self.style.ERROR("Agent user must be in the DeliveryAgent group."))
            return

        products = list(Product.objects.all()[:5])
        if not products:
            self.stdout.write(self.style.ERROR("No products available to simulate orders."))
            return

        address = Address.objects.filter(user_id=buyer_id, is_confirmed=True).first()
        if not address:
            self.stdout.write(self.style.ERROR("Buyer must have a confirmed address to simulate orders."))
            return

        self.stdout.write(self.style.SUCCESS("Starting simulation..."))

        created_orders = 0
        delivered_orders = 0

        for _ in range(orders_count):
            is_secure = random.random() < secure_ratio
            should_deliver = random.random() < delivered_ratio
            delivery_mode = "secure" if is_secure else "traditional"

            with transaction.atomic():
                order = Order.objects.create(
                    user_id=buyer_id,
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
                    # Simulate QR scan to assign agent.
                    claim_order_from_token(token=order.token_value, user=agent_user)

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
                    if should_deliver:
                        order.status = "Delivered"
                        order.expires_at = timezone.now()
                        order.save(update_fields=["status", "expires_at"])

            created_orders += 1
            if order.status == "Delivered":
                delivered_orders += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Simulation complete. Created {created_orders} orders, delivered {delivered_orders}."
            )
        )
