from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_remove_customuser_binary_position'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='otp_enabled',
            field=models.BooleanField(default=False, verbose_name='OTP actif'),
        ),
        migrations.CreateModel(
            name='OTPChallenge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('purpose', models.CharField(choices=[('LOGIN', 'Connexion'), ('ENABLE', 'Activation OTP')], max_length=15)),
                ('code_hash', models.CharField(max_length=255)),
                ('expires_at', models.DateTimeField()),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='otp_challenges', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
