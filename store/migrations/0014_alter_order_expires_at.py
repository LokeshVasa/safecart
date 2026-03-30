from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0013_order_qr_scan_count'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
