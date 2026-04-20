from django.core.management.base import BaseCommand

from store.models import Address
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Ensure a buyer has a confirmed address for simulation."

    def add_arguments(self, parser):
        parser.add_argument("--buyer-id", type=int, help="Buyer user id.")
        parser.add_argument("--buyer-username", type=str, help="Buyer username.")
        parser.add_argument("--street", type=str, default="Demo Street 1", help="Street name.")
        parser.add_argument("--city", type=str, default="Hyderabad", help="City.")
        parser.add_argument("--state", type=str, default="Telangana", help="State.")
        parser.add_argument("--pincode", type=str, default="500001", help="Pincode.")

    def handle(self, *args, **options):
        buyer_id = options.get("buyer_id")
        buyer_username = (options.get("buyer_username") or "").strip()

        user = None
        if buyer_id:
            user = User.objects.filter(id=buyer_id).first()
        if not user and buyer_username:
            user = User.objects.filter(username=buyer_username).first()

        if not user:
            self.stdout.write(self.style.ERROR("Buyer user not found. Provide valid id or username."))
            return

        address, created = Address.objects.get_or_create(
            user=user,
            street=options["street"],
            city=options["city"],
            state=options["state"],
            pincode=options["pincode"],
            defaults={"is_confirmed": True},
        )

        if not address.is_confirmed:
            address.is_confirmed = True
            address.save(update_fields=["is_confirmed"])

        if created:
            self.stdout.write(self.style.SUCCESS("Confirmed address created for buyer."))
        else:
            self.stdout.write(self.style.SUCCESS("Existing address marked as confirmed."))
