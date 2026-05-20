from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_notification'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customuser',
            name='binary_position',
        ),
    ]
