import os

import django
from django.db import transaction


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from investments.models import InvestmentTier


TIERS = [
    {
        'name': 'Standard',
        'level': 1,
        'badge': 'STD',
        'min_amount': 5000,
        'max_amount': 9999,
        'daily_rate': 0.1000,
        'monthly_rate': 3.00,
        'cycle_days': 30,
        'badge_color': '2563EB',
        'icon': 'standard',
        'advantages': [
            'Acces au catalogue de base',
            'Suivi simple des gains',
        ],
    },
    {
        'name': 'Bronze',
        'level': 2,
        'badge': 'BRZ',
        'min_amount': 10000,
        'max_amount': 24999,
        'daily_rate': 0.1000,
        'monthly_rate': 3.00,
        'cycle_days': 30,
        'badge_color': 'B45309',
        'icon': 'bronze',
        'advantages': [
            'Support standard',
            'Historique de souscription detaille',
        ],
    },
    {
        'name': 'Argent',
        'level': 3,
        'badge': 'ARG',
        'min_amount': 25000,
        'max_amount': 49999,
        'daily_rate': 0.1000,
        'monthly_rate': 3.00,
        'cycle_days': 30,
        'badge_color': '6B7280',
        'icon': 'silver',
        'advantages': [
            'Visibilite etendue sur les gains',
            'Traitement prioritaire des demandes',
        ],
    },
    {
        'name': 'Or',
        'level': 4,
        'badge': 'OR',
        'min_amount': 50000,
        'max_amount': 74999,
        'daily_rate': 0.1300,
        'monthly_rate': 3.90,
        'cycle_days': 30,
        'badge_color': 'CA8A04',
        'icon': 'gold',
        'advantages': [
            'Accompagnement renforce',
            'Projection de gains avancee',
        ],
    },
    {
        'name': 'Diamant',
        'level': 5,
        'badge': 'DIA',
        'min_amount': 75000,
        'max_amount': 149999,
        'daily_rate': 0.1300,
        'monthly_rate': 3.90,
        'cycle_days': 30,
        'badge_color': '0EA5E9',
        'icon': 'diamond',
        'advantages': [
            'Parcours premium',
            'Acces prioritaire aux operations',
        ],
    },
    {
        'name': 'VIP',
        'level': 6,
        'badge': 'VIP',
        'min_amount': 150000,
        'max_amount': 1249999,
        'daily_rate': 0.1300,
        'monthly_rate': 3.90,
        'cycle_days': 30,
        'badge_color': '7C3AED',
        'icon': 'vip',
        'advantages': [
            'Support VIP',
            'Suivi renforce des souscriptions',
        ],
    },
    {
        'name': 'Partenaire 1',
        'level': 7,
        'badge': 'P1',
        'min_amount': 1250000,
        'max_amount': 3499999,
        'daily_rate': 0.1500,
        'monthly_rate': 4.50,
        'cycle_days': 30,
        'badge_color': '059669',
        'icon': 'partner-1',
        'advantages': [
            'Bonus partenaire eligible',
            'Pilotage avance du portefeuille',
        ],
    },
    {
        'name': 'Partenaire 2',
        'level': 8,
        'badge': 'P2',
        'min_amount': 3500000,
        'max_amount': None,
        'daily_rate': 0.1500,
        'monthly_rate': 4.50,
        'cycle_days': 30,
        'badge_color': '065F46',
        'icon': 'partner-2',
        'advantages': [
            'Bonus partenaire maximal',
            'Accompagnement prioritaire et dedie',
        ],
    },
]


def seed_tiers():
    with transaction.atomic():
        print("Suppression des anciennes categories...")
        InvestmentTier.objects.all().delete()

        print("Insertion du catalogue conforme au cahier...")
        for data in TIERS:
            tier = InvestmentTier(**data)
            tier.save()
            print(f"Categorie '{tier.name}' inseree.")


if __name__ == '__main__':
    seed_tiers()
    print("Catalogue categories insere.")
