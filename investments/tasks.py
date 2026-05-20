from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Investment, Transaction
from users.models import Notification

from .services import ReferralService, YieldRuleService


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


@shared_task
def process_referral_bonuses():
    """
    Verse les bonus de parrainage 24h apres la validation d'un achat filleul.
    La regle applique 10% par defaut et 15% sur les categories partenaires.
    """
    reference_time = timezone.now()
    eligible_transactions = (
        Transaction.objects.filter(
            tx_type=Transaction.TransactionType.PAY_INVEST,
            status=Transaction.Status.SUCCESS,
            user__sponsor__isnull=False,
            related_investment__isnull=False,
        )
        .select_related('user', 'user__sponsor', 'related_investment', 'related_investment__tier')
        .order_by('created_at')
    )
    processed = 0

    with transaction.atomic():
        for payment_tx in eligible_transactions:
            if not ReferralService.is_bonus_due(payment_tx, reference_time=reference_time):
                continue

            bonus_tx_ref = ReferralService.build_bonus_reference(payment_tx)
            if Transaction.objects.filter(tx_reference=bonus_tx_ref).exists():
                continue

            sponsor = payment_tx.user.sponsor
            bonus_amount = ReferralService.calculate_bonus_amount(payment_tx)
            sponsor.balance += bonus_amount
            sponsor.save(update_fields=['balance'])
            Transaction.objects.create(
                user=sponsor,
                tx_type=Transaction.TransactionType.BONUS,
                amount=bonus_amount,
                status=Transaction.Status.SUCCESS,
                provider=f"Referral Bonus for {payment_tx.user.username}",
                tx_reference=bonus_tx_ref,
            )
            Notification.objects.create(
                user=sponsor,
                title="Bonus de parrainage credite",
                message=(
                    f"Votre bonus de parrainage de {bonus_amount:,.0f} XOF pour "
                    f"{payment_tx.user.username} a ete credite."
                ).replace(',', ' '),
            )
            processed += 1

    return f"{processed} bonus de parrainage traites."
