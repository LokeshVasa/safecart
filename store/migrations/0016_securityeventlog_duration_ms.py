from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0015_securityeventlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityeventlog",
            name="duration_ms",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
