from django.core.management.base import BaseCommand
from investments.models import Product, Booster

class Command(BaseCommand):
    help = 'Peuple la base de données avec les produits et boosters initiaux'

    def handle(self, *args, **kwargs):
        self.stdout.write('Création des Produits...')
        
        # 1. Produits d'investissement
        Product.objects.get_or_create(
            name='Pétrole Brut',
            defaults={
                'min_investment': 5000,
                'daily_roi_percentage': 0.50,  # ~15% par mois
                'duration_months': 10,
                'icon': 'ph ph-drop',
                'is_active': True
            }
        )
        Product.objects.get_or_create(
            name='Or Massif',
            defaults={
                'min_investment': 10000,
                'daily_roi_percentage': 0.40,  # ~12% par mois
                'duration_months': 10,
                'icon': 'ph-fill ph-medal',
                'is_active': True
            }
        )
        Product.objects.get_or_create(
            name='Diamant Premium',
            defaults={
                'min_investment': 5000,
                'daily_roi_percentage': 0.66,  # ~20% par mois
                'duration_months': 10,
                'icon': 'ph ph-diamond',
                'is_active': True
            }
        )

        self.stdout.write('Création des Boosters...')
        
        # 2. Boosters
        Booster.objects.get_or_create(
            name='Booster Bronze',
            defaults={
                'multiplier': 1.5,
                'price': 2000,
                'duration_days': 7,
                'icon': 'ph ph-rocket',
                'is_active': True
            }
        )
        Booster.objects.get_or_create(
            name='Turbo Flash',
            defaults={
                'multiplier': 2.0,
                'price': 5000,
                'duration_days': 3,
                'icon': 'ph ph-lightning',
                'is_active': True
            }
        )

        self.stdout.write(self.style.SUCCESS("Génial ! Les Produits et Boosters ont bien été générés dans votre base de données avec succès."))
