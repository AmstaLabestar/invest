from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0011_remove_legacy_boosters'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=160, verbose_name='Sujet')),
                ('message', models.TextField(verbose_name='Message')),
                ('status', models.CharField(choices=[('OPEN', 'Ouvert'), ('IN_PROGRESS', 'En traitement'), ('RESOLVED', 'Resolue'), ('CLOSED', 'Fermee')], default='OPEN', max_length=20)),
                ('priority', models.CharField(choices=[('LOW', 'Faible'), ('NORMAL', 'Normale'), ('HIGH', 'Haute')], default='NORMAL', max_length=15)),
                ('admin_response', models.TextField(blank=True, verbose_name='Reponse admin')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='support_tickets', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Ticket support',
                'verbose_name_plural': 'Tickets support',
                'ordering': ['-updated_at'],
            },
        ),
    ]
