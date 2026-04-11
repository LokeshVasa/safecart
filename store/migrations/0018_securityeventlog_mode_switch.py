from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0017_order_delivery_mode"),
    ]

    operations = [
        migrations.AlterField(
            model_name="securityeventlog",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("qr_scan", "QR Scan"),
                    ("qr_scan_blocked", "QR Scan Blocked"),
                    ("otp_requested", "OTP Requested"),
                    ("otp_request_blocked", "OTP Request Blocked"),
                    ("otp_verify_success", "OTP Verify Success"),
                    ("otp_verify_failed", "OTP Verify Failed"),
                    ("order_delivered", "Order Delivered"),
                    ("delivery_mode_switched", "Delivery Mode Switched"),
                ],
                max_length=50,
            ),
        ),
    ]
