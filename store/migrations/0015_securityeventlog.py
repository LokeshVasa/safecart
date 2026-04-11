from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0014_alter_order_expires_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SecurityEventLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("qr_scan", "QR Scan"), ("qr_scan_blocked", "QR Scan Blocked"), ("otp_requested", "OTP Requested"), ("otp_request_blocked", "OTP Request Blocked"), ("otp_verify_success", "OTP Verify Success"), ("otp_verify_failed", "OTP Verify Failed"), ("order_delivered", "Order Delivered")], max_length=50)),
                ("outcome", models.CharField(choices=[("success", "Success"), ("blocked", "Blocked"), ("failed", "Failed")], default="success", max_length=20)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="security_events", to="store.order")),
            ],
            options={
                "db_table": "security_event_logs",
            },
        ),
    ]
