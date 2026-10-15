from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='banktransaction',
            name='airtable_error',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='banktransaction',
            name='airtable_record_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='banktransaction',
            name='airtable_sync_status',
            field=models.CharField(choices=[('not_synced', 'Not Synced'), ('synced', 'Synced'), ('sync_failed', 'Sync Failed')], default='not_synced', max_length=20),
        ),
    ]
