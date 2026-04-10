import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="account",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "core_account",
            },
        ),
        migrations.CreateModel(
            name="StripeConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("_encrypted_access_token", models.TextField(db_column="encrypted_access_token")),
                ("stripe_user_id", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stripe_connection",
                        to="core.account",
                    ),
                ),
            ],
            options={
                "db_table": "core_stripe_connection",
            },
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subscriber_id", models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                (
                    "actor",
                    models.CharField(
                        choices=[("engine", "Engine"), ("operator", "Operator"), ("client", "Client")],
                        max_length=20,
                    ),
                ),
                ("action", models.CharField(max_length=100)),
                ("outcome", models.CharField(max_length=50)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "account",
                    models.ForeignKey(
                        blank=True,
                        db_index=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.account",
                    ),
                ),
            ],
            options={
                "db_table": "core_audit_log",
            },
        ),
    ]
