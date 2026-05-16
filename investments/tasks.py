from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Investment, Transaction
from .services import YieldRuleService


User = get_user_model()


@shared_task
def calculate_daily_roi():
    """
    Tache quotidienne.
    Credite les rendements journaliers lineaires sur tous les investissements actifs.
    Les bonus fixes partenaires sont verses tous les 15 jours de maniere idempotente.
    """
    active_investments = Investment.objects.filter(
        status=Investment.Status.ACTIVE
    ).select_related('user', 'tier')
    today = timezone.localdate()

    with transaction.atomic():
        for investment in active_investments:
            user = investment.user

            roi_tx_ref = f"ROI-{investment.id}-{today.strftime('%Y%m%d')}"
            if not Transaction.objects.filter(tx_reference=roi_tx_ref).exists():
                daily_profit = YieldRuleService.calculate_daily_profit(investment)
                user.balance += daily_profit
                user.save(update_fields=['balance'])
                Transaction.objects.create(
                    user=user,
                    tx_type=Transaction.TransactionType.ROI,
                    amount=daily_profit,
                    status=Transaction.Status.SUCCESS,
                    provider='System Daily Yield',
                    tx_reference=roi_tx_ref,
                )

            for checkpoint in YieldRuleService.get_partner_bonus_checkpoints(investment):
                bonus_tx_ref = f"PARTNER-BONUS-{investment.id}-{checkpoint}"
                if Transaction.objects.filter(tx_reference=bonus_tx_ref).exists():
                    continue

                user.balance += YieldRuleService.PARTNER_FIXED_BONUS
                user.save(update_fields=['balance'])
                Transaction.objects.create(
                    user=user,
                    tx_type=Transaction.TransactionType.BONUS,
                    amount=YieldRuleService.PARTNER_FIXED_BONUS,
                    status=Transaction.Status.SUCCESS,
                    provider=f'Partner Bonus Day {checkpoint}',
                    tx_reference=bonus_tx_ref,
                )

    return f"Calculs de ROI termines pour {active_investments.count()} investissements actifs."


# --- ALGORITHME DE PARRAINAGE BINAIRE LEGACY ---
def get_node_volume(user):
    """Calcule recursivement le volume d'investissement total genere par l'arbre sous cet utilisateur."""
    if user is None:
        return 0

    volume = sum(
        inv.amount_invested
        for inv in user.investments.filter(status=Investment.Status.ACTIVE)
    )

    for referral in user.referrals.all():
        volume += get_node_volume(referral)

    return volume


@shared_task
def calculate_binary_bonus():
    """
    Tache legacy pour le bonus binaire.
    Cette logique sera remplacee par le vrai modele de parrainage du cahier.
    """
    binary_bonus_percentage = 10
    users_with_referrals = User.objects.filter(referrals__isnull=False).distinct()

    with transaction.atomic():
        for user in users_with_referrals:
            left_leg_head = user.referrals.filter(binary_position='LEFT').first()
            right_leg_head = user.referrals.filter(binary_position='RIGHT').first()

            left_volume = get_node_volume(left_leg_head) if left_leg_head else 0
            right_volume = get_node_volume(right_leg_head) if right_leg_head else 0
            weak_leg_volume = min(left_volume, right_volume)

            if weak_leg_volume <= 0:
                continue

            bonus_amount = weak_leg_volume * binary_bonus_percentage / 100
            bonus_tx_ref = f"BINARY-BONUS-{user.id}-{timezone.localdate().strftime('%Y%m%d')}"
            if Transaction.objects.filter(tx_reference=bonus_tx_ref).exists():
                continue

            user.balance += bonus_amount
            user.save(update_fields=['balance'])
            Transaction.objects.create(
                user=user,
                tx_type=Transaction.TransactionType.BONUS,
                amount=bonus_amount,
                status=Transaction.Status.SUCCESS,
                provider='Binary Bonus',
                tx_reference=bonus_tx_ref,
            )

    return "Calculs des bonus binaires termines."
