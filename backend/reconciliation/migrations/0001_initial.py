import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BankTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True)),
                ('description', models.TextField()),
                ('normalized_description', models.TextField(blank=True, default='')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('type', models.CharField(choices=[('credit', 'Credit'), ('debit', 'Debit')], max_length=10)),
                ('bank_reference', models.CharField(db_index=True, max_length=100)),
                ('status', models.CharField(choices=[('suggested', 'Suggested'), ('needs_review', 'Needs Review'), ('reconciled', 'Reconciled'), ('ignored', 'Ignored')], max_length=20)),
                ('needs_review_reason', models.TextField(blank=True, default='')),
                ('raw_file_line', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CapitalCall',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('call_number', models.PositiveIntegerField()),
                ('call_date', models.DateField()),
                ('due_date', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['call_date', 'call_number'],
            },
        ),
        migrations.CreateModel(
            name='InvestorEntity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('normalized_name', models.CharField(db_index=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(unique=True)),
                ('name', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='LineItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wire_reference', models.CharField(db_index=True, max_length=100)),
                ('normalized_reference', models.CharField(db_index=True, max_length=100)),
                ('amount_called', models.DecimalField(decimal_places=2, max_digits=14)),
                ('amount_funded', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14)),
                ('status', models.CharField(choices=[('open', 'Open'), ('partially_funded', 'Partially Funded'), ('funded', 'Funded')], default='open', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('capital_call', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='line_items', to='reconciliation.capitalcall')),
                ('investor_entity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='line_items', to='reconciliation.investorentity')),
            ],
            options={
                'ordering': ['capital_call', 'wire_reference'],
            },
        ),
        migrations.CreateModel(
            name='MatchProposal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('match_status', models.CharField(choices=[('proposed', 'Proposed'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='proposed', max_length=20)),
                ('reason', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('line_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='match_proposals', to='reconciliation.lineitem')),
                ('transaction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='matches', to='reconciliation.banktransaction')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='investorentity',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='investor_entities', to='reconciliation.organization'),
        ),
        migrations.AddField(
            model_name='capitalcall',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='capital_calls', to='reconciliation.organization'),
        ),
        migrations.AddField(
            model_name='banktransaction',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='reconciliation.organization'),
        ),
        migrations.AddConstraint(
            model_name='lineitem',
            constraint=models.UniqueConstraint(fields=('capital_call', 'wire_reference'), name='unique_call_wire_reference'),
        ),
        migrations.AddConstraint(
            model_name='matchproposal',
            constraint=models.UniqueConstraint(fields=('transaction', 'line_item'), name='unique_transaction_line_item'),
        ),
        migrations.AddConstraint(
            model_name='investorentity',
            constraint=models.UniqueConstraint(fields=('organization', 'name'), name='unique_org_investor_name'),
        ),
        migrations.AddConstraint(
            model_name='capitalcall',
            constraint=models.UniqueConstraint(fields=('organization', 'call_number'), name='unique_org_call_number'),
        ),
        migrations.AddConstraint(
            model_name='banktransaction',
            constraint=models.UniqueConstraint(fields=('organization', 'bank_reference'), name='unique_org_bank_reference'),
        ),
    ]
