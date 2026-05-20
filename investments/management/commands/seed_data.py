from django.core.management.base import BaseCommand
from django.db import transaction

from investments.models import InvestmentTier
from seed_tiers import TIERS


class Command(BaseCommand):
    help = 'Peuple la base de donnees avec le catalogue de categories'

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            self.stdout.write('Creation du catalogue de categories...')
            for tier_data in TIERS:
                defaults = tier_data.copy()
                name = defaults.pop('name')
                level = defaults.pop('level')
                tier, created = InvestmentTier.objects.update_or_create(
                    level=level,
                    defaults={'name': name, 'level': level, **defaults},
                )
                action = 'cree' if created else 'mis a jour'
                self.stdout.write(f"- Categorie {tier.name} {action}")

        self.stdout.write(self.style.SUCCESS('Catalogue categories genere avec succes.'))
