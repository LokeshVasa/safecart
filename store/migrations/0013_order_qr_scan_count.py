from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0012_ordercallsession_ordercallsignal'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='qr_scan_count',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
