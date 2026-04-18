import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from investments.models import InvestmentTier
from django.db import transaction

TIERS = [
    {
        'name': 'Bronze', 'level': 1, 'badge': '🥉', 'min_amount': 6000, 
        'max_amount': 24999, 'daily_rate': 0.0120, 'monthly_rate': 0.36, 
        'cycle_days': 30, 'badge_color': 'CD7F32', 'icon': 'bronze',
        'advantages': [
            'Accès plateforme', 
            'Support standard', 
            'Notifications SMS', 
            'Retrait à partir de 1000 XOF'
        ]
    },
    {
        'name': 'Argent', 'level': 2, 'badge': '🥈', 'min_amount': 25000, 
        'max_amount': 74999, 'daily_rate': 0.0150, 'monthly_rate': 0.45, 
        'cycle_days': 45, 'badge_color': 'C0C0C0', 'icon': 'silver',
        'advantages': [
            'Tous avantages Bronze', 
            'Support prioritaire', 
            'Rapports mensuels détaillés', 
            'Bonus fidélité +10%', 
            'Retrait instantané'
        ]
    },
    {
        'name': 'Or', 'level': 3, 'badge': '🥇', 'min_amount': 75000, 
        'max_amount': 249999, 'daily_rate': 0.0180, 'monthly_rate': 0.54, 
        'cycle_days': 60, 'badge_color': 'FFD700', 'icon': 'gold',
        'advantages': [
            'Tous avantages Argent', 
            'Gestionnaire de compte dédié', 
            'Analyses de marché hebdomadaires', 
            'Bonus fidélité +20%', 
            'Accès produits exclusifs', 
            'Assurance capital'
        ]
    },
    {
        'name': 'Diamant', 'level': 4, 'badge': '💎', 'min_amount': 250000, 
        'max_amount': 999999, 'daily_rate': 0.0200, 'monthly_rate': 0.60, 
        'cycle_days': 90, 'badge_color': 'B9F2FF', 'icon': 'diamond',
        'advantages': [
            'Tous avantages Or', 
            'Conseiller VIP 24/7', 
            'Stratégies personnalisées', 
            'Bonus fidélité +30%', 
            'Événements exclusifs', 
            'Assurance capital + gains 50%', 
            'Retrait sans frais'
        ]
    },
    {
        'name': 'Platine', 'level': 5, 'badge': '👑', 'min_amount': 1000000, 
        'max_amount': None, 'daily_rate': 0.0250, 'monthly_rate': 0.75, 
        'cycle_days': 120, 'badge_color': 'E5E4E2', 'icon': 'crown',
        'advantages': [
            'Tous avantages Diamant', 
            'Équipe dédiée', 
            'Stratégie sur mesure', 
            'Bonus fidélité +50%', 
            'Participation aux décisions', 
            'Assurance totale (capital + gains)', 
            'Retraits illimités sans frais', 
            'Invitations événements internationaux'
        ]
    }
]

def seed_tiers():
    with transaction.atomic():
        print("Suppression des anciens paliers...")
        InvestmentTier.objects.all().delete()
        
        print("Insertion des nouveaux paliers...")
        for data in TIERS:
            # max_amount peut être null pour le dernier niveau, on n'a pas besoin de nettoyage car python gère None -> null.
            tier = InvestmentTier(**data)
            tier.save()
            print(f"✅ Palier '{tier.name}' inséré.")

if __name__ == '__main__':
    seed_tiers()
    print("🚀 Seed complet !")
