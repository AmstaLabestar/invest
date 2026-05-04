from django.core.management.base import BaseCommand
from django.db import transaction

from investments.models import Booster, InvestmentTier
from seed_tiers import TIERS


BOOSTERS = [
    {
        'name': 'Booster Bronze',
        'multiplier': 1.5,
        'price': 2000,
        'duration_days': 7,
        'icon': 'ph ph-rocket',
        'is_active': True,
    },
    {
        'name': 'Turbo Flash',
        'multiplier': 2.0,
        'price': 5000,
        'duration_days': 3,
        'icon': 'ph ph-lightning',
        'is_active': True,
    },
]


class Command(BaseCommand):
    help = 'Peuple la base de donnees avec les paliers et boosters initiaux'

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            self.stdout.write('Creation des paliers...')
            for tier_data in TIERS:
                defaults = tier_data.copy()
                name = defaults.pop('name')
                level = defaults.pop('level')
                tier, created = InvestmentTier.objects.update_or_create(
                    level=level,
                    defaults={'name': name, 'level': level, **defaults},
                )
                action = 'cree' if created else 'mis a jour'
                self.stdout.write(f"- Palier {tier.name} {action}")

            self.stdout.write('Creation des boosters...')
            for booster_data in BOOSTERS:
                defaults = booster_data.copy()
                name = defaults.pop('name')
                booster, created = Booster.objects.update_or_create(
                    name=name,
                    defaults={'name': name, **defaults},
                )
                action = 'cree' if created else 'mis a jour'
                self.stdout.write(f"- Booster {booster.name} {action}")

        self.stdout.write(self.style.SUCCESS('Paliers et boosters generes avec succes.'))
