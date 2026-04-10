from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_add_subscriber_and_subscriber_failure"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stripeconnection",
            name="stripe_user_id",
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
