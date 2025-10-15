from django.apps import AppConfig
from django.db.models.signals import post_migrate

class StoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'

    def ready(self):
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import Product, Order

        def create_user_groups_and_permissions(sender, **kwargs):
            # --- Groups ---
            buyer_group, _ = Group.objects.get_or_create(name='Buyer')
            delivery_group, _ = Group.objects.get_or_create(name='DeliveryAgent')
            admin_group, _ = Group.objects.get_or_create(name='Admin')

            # --- Product permissions ---
            product_ct = ContentType.objects.get_for_model(Product)
            manage_products_perm, _ = Permission.objects.get_or_create(
                codename='can_manage_products',
                name='Can manage products',
                content_type=product_ct
            )
            if manage_products_perm not in admin_group.permissions.all():
                admin_group.permissions.add(manage_products_perm)


            # --- Order permissions ---
            order_ct = ContentType.objects.get_for_model(Order)
            admin_perm, _ = Permission.objects.get_or_create(
                codename='can_perform_admin_actions',
                name='Can perform admin actions',
                content_type=order_ct
            )
            deliver_order_perm, _ = Permission.objects.get_or_create(
                codename='can_deliver_order',
                name='Can deliver assigned orders',
                content_type=order_ct
            )
               # Assign permissions only if missing
            if admin_perm not in admin_group.permissions.all():
                admin_group.permissions.add(admin_perm)
            if deliver_order_perm not in delivery_group.permissions.all():
                delivery_group.permissions.add(deliver_order_perm)

        post_migrate.connect(create_user_groups_and_permissions, sender=self)