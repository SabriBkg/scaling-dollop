# Captures the ACTOR_SUBSCRIBER choice added in Story 4.4 but never migrated.
# Choices-only AlterField — no DB schema change.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_extend_notification_email_type_choices'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='actor',
            field=models.CharField(
                choices=[
                    ('engine', 'Engine'),
                    ('operator', 'Operator'),
                    ('client', 'Client'),
                    ('subscriber', 'Subscriber'),
                ],
                max_length=20,
            ),
        ),
    ]
