from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "List buyer and delivery agent users for simulation commands."

    def handle(self, *args, **options):
        buyer_group, _ = Group.objects.get_or_create(name="Buyer")
        delivery_group, _ = Group.objects.get_or_create(name="DeliveryAgent")

        buyers = User.objects.filter(groups=buyer_group).order_by("id")
        agents = User.objects.filter(groups=delivery_group).order_by("id")

        self.stdout.write(self.style.SUCCESS("Buyers:"))
        if buyers.exists():
            for user in buyers:
                self.stdout.write(f"- {user.username} (id={user.id})")
        else:
            self.stdout.write("  No buyers found.")

        self.stdout.write(self.style.SUCCESS("\nDelivery Agents:"))
        if agents.exists():
            for user in agents:
                self.stdout.write(f"- {user.username} (id={user.id})")
        else:
            self.stdout.write("  No delivery agents found.")
