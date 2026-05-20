from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0010_alter_investment_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='tx_type',
            field=models.CharField(
                choices=[
                    ('PAY_INVEST', 'Achat de categorie'),
                    ('WITHDRAWAL', 'Retrait'),
                    ('ROI', 'Gains Rendement'),
                    ('BONUS', 'Bonus Parrainage'),
                ],
                max_length=15,
            ),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='provider',
            field=models.CharField(
                blank=True,
                help_text='Orange Money, Moov Money, Telecel Money',
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name='paymentconfig',
            name='provider_name',
            field=models.CharField(max_length=50, unique=True, verbose_name='Nom du fournisseur'),
        ),
        migrations.DeleteModel(
            name='UserBooster',
        ),
        migrations.DeleteModel(
            name='Booster',
        ),
    ]
