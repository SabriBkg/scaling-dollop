from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="tier",
            field=models.CharField(
                choices=[("free", "Free"), ("mid", "Mid"), ("pro", "Pro")],
                default="mid",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="trial_ends_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
