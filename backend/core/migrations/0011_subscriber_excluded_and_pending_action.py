from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_add_payment_method_fingerprint"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriber",
            name="excluded_from_automation",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="PendingAction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "recommended_action",
                    models.CharField(max_length=50),
                ),
                (
                    "recommended_retry_cap",
                    models.IntegerField(),
                ),
                (
                    "recommended_payday_aware",
                    models.BooleanField(),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("excluded", "Excluded"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.account",
                    ),
                ),
                (
                    "failure",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pending_actions",
                        to="core.subscriberfailure",
                    ),
                ),
                (
                    "subscriber",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pending_actions",
                        to="core.subscriber",
                    ),
                ),
            ],
            options={
                "db_table": "core_pending_action",
            },
        ),
    ]
