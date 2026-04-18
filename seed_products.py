import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from investments.models import Product

# Réinitialiser ou simplement ajouter
products = [
    {
        'name': 'Pétrole Brut',
        'min_investment': 5000,
        'daily_roi_percentage': 0.5, # 15% mensuel / 30
        'duration_months': 1,
        'icon': 'ph-barrel'
    },
    {
        'name': 'Diamant Premium',
        'min_investment': 10000,
        'daily_roi_percentage': 0.67, # 20% mensuel / 30
        'duration_months': 2,
        'icon': 'ph-diamond'
    },
    {
        'name': 'Or Massif',
        'min_investment': 5000,
        'daily_roi_percentage': 0.4, # 12% mensuel / 30
        'duration_months': 1,
        'icon': 'ph-medal'
    },
    {
        'name': 'Agriculture Bio',
        'min_investment': 5000,
        'daily_roi_percentage': 0.6, # 18% mensuel / 30
        'duration_months': 2, # Pour 45 jours (arrondi)
        'icon': 'ph-plant'
    }
]

# Create or Update
for p_data in products:
    Product.objects.update_or_create(
        name=p_data['name'],
        defaults=p_data
    )

print("Produits créés avec succès !")
