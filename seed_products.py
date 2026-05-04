import os

import django
from django.core.management import call_command


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()


if __name__ == '__main__':
    print("Le script legacy 'seed_products.py' redirige vers la commande 'seed_data'.")
    call_command('seed_data')
