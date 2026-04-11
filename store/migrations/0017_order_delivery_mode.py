from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0016_securityeventlog_duration_ms"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_mode",
            field=models.CharField(
                choices=[("secure", "SafeCart Secure"), ("traditional", "Traditional Delivery")],
                default="secure",
                max_length=20,
            ),
        ),
    ]
