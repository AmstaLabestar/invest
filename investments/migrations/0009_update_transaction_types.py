from django.db import migrations, models


def normalize_transaction_types(apps, schema_editor):
    Transaction = apps.get_model('investments', 'Transaction')
    Transaction.objects.filter(tx_type='DEPOSIT').update(tx_type='PAY_INVEST')
    Transaction.objects.filter(tx_type='INVESTMENT').update(tx_type='BOOSTER')


class Migration(migrations.Migration):
    dependencies = [
        ('investments', '0008_transaction_related_investment_and_more'),
    ]

    operations = [
        migrations.RunPython(normalize_transaction_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='transaction',
            name='tx_type',
            field=models.CharField(
                choices=[
                    ('PAY_INVEST', 'Achat de Palier (Checkout)'),
                    ('BOOSTER', 'Achat de Booster'),
                    ('WITHDRAWAL', 'Retrait'),
                    ('ROI', 'Gains Rendement'),
                    ('BONUS', 'Bonus Parrainage'),
                ],
                max_length=15,
            ),
        ),
    ]
