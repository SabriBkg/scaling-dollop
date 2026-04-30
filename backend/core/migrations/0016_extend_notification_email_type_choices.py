# Generated for Story 3.3 v1 — extends NotificationLog.email_type choices to
# cover the client-manual dunning email types (update_payment, retry_reminder).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_add_dpa_version_to_account'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notificationlog',
            name='email_type',
            field=models.CharField(
                choices=[
                    ('failure_notice', 'Failure Notice'),
                    ('update_payment', 'Update Payment'),
                    ('retry_reminder', 'Retry Reminder'),
                    ('final_notice', 'Final Notice'),
                    ('recovery_confirmation', 'Recovery Confirmation'),
                ],
                max_length=30,
            ),
        ),
    ]
