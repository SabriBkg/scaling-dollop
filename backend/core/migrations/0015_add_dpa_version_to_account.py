from django.db import migrations, models


def backfill_legacy_dpa_version(apps, schema_editor):
    """Stamp pre-existing accepted DPAs with the v0-legacy sentinel.

    Carry-forward per Story 3.1 v1 AC3: any account that signed the v0
    DPA (pre-2026-04-29) is honored without re-acceptance. The version
    column was added in this migration and defaults to "" — we mark
    rows where dpa_accepted_at is non-null so the Settings page can
    display "Version v0-legacy" for them.
    """
    Account = apps.get_model("core", "Account")
    Account.objects.filter(dpa_accepted_at__isnull=False).update(
        dpa_version="v0-legacy"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_notification_unique_sent_per_failure'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='dpa_version',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.RunPython(
            backfill_legacy_dpa_version,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
