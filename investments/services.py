from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.utils import timezone

from .models import Investment, InvestmentTier, Transaction


class WalletService:
    @staticmethod
    def get_available_balance(user):
        return user.balance or Decimal("0")

    @staticmethod
    def get_reserved_balance(user):
        return (
            Transaction.objects.filter(
                user=user,
                tx_type=Transaction.TransactionType.WITHDRAWAL,
                status=Transaction.Status.PENDING,
            ).aggregate(Sum('amount'))['amount__sum']
            or Decimal("0")
        )

    @classmethod
    def get_total_balance(cls, user):
        return cls.get_available_balance(user) + cls.get_reserved_balance(user)

    @staticmethod
    def get_total_invested_capital(user):
        return (
            Investment.objects.filter(
                user=user,
                status=Investment.Status.ACTIVE,
            ).aggregate(Sum('amount_invested'))['amount_invested__sum']
            or Decimal("0")
        )

    @staticmethod
    def get_realized_gains(user, start_date=None):
        queryset = Transaction.objects.filter(
            user=user,
            tx_type__in=[
                Transaction.TransactionType.ROI,
                Transaction.TransactionType.BONUS,
            ],
            status=Transaction.Status.SUCCESS,
        )
        if start_date is not None:
            queryset = queryset.filter(created_at__gte=start_date)
        return queryset.aggregate(Sum('amount'))['amount__sum'] or Decimal("0")

    @staticmethod
    def get_consumed_gains(user):
        return (
            Transaction.objects.filter(
                user=user,
                tx_type=Transaction.TransactionType.WITHDRAWAL,
                status__in=[Transaction.Status.PENDING, Transaction.Status.SUCCESS],
            ).aggregate(Sum('amount'))['amount__sum']
            or Decimal("0")
        )

    @staticmethod
    def get_withdrawal_unlock_at(user):
        latest_investment = (
            Investment.objects.filter(
                user=user,
                status__in=[
                    Investment.Status.PENDING,
                    Investment.Status.ACTIVE,
                    Investment.Status.COMPLETED,
                ],
            )
            .order_by('-start_date')
            .first()
        )
        if latest_investment is None:
            return None
        return latest_investment.start_date + timedelta(days=3)

    @classmethod
    def is_withdrawal_unlocked(cls, user, reference_time=None):
        if reference_time is None:
            reference_time = timezone.now()
        unlock_at = cls.get_withdrawal_unlock_at(user)
        return unlock_at is None or reference_time >= unlock_at

    @classmethod
    def get_withdrawable_amount(cls, user, reference_time=None):
        if not cls.is_withdrawal_unlocked(user, reference_time=reference_time):
            return Decimal("0")

        gain_based_amount = cls.get_realized_gains(user) - cls.get_consumed_gains(user)
        gain_based_amount = max(gain_based_amount, Decimal("0"))
        return min(cls.get_available_balance(user), gain_based_amount)


class YieldRuleService:
    PARTNER_CATEGORY_NAMES = {'Partenaire 1', 'Partenaire 2'}
    PARTNER_FIXED_BONUS = Decimal("50000.00")
    PARTNER_BONUS_INTERVAL_DAYS = 15
    MONEY_QUANTIZER = Decimal("0.01")

    @classmethod
    def quantize_amount(cls, amount):
        return Decimal(amount).quantize(cls.MONEY_QUANTIZER, rounding=ROUND_HALF_UP)

    @staticmethod
    def get_daily_rate(source):
        if isinstance(source, Investment):
            if source.daily_rate_snapshot and source.daily_rate_snapshot > 0:
                return Decimal(source.daily_rate_snapshot)
            if source.tier:
                return Decimal(source.tier.daily_rate)
            return Decimal("0")
        if isinstance(source, InvestmentTier):
            return Decimal(source.daily_rate)
        return Decimal("0")

    @staticmethod
    def get_capped_elapsed_days(investment, reference_time=None):
        if reference_time is None:
            reference_time = timezone.now()
        if reference_time < investment.start_date:
            return 0

        elapsed_days = (reference_time - investment.start_date).days
        if investment.end_date and reference_time > investment.end_date:
            elapsed_days = (investment.end_date - investment.start_date).days

        cycle_days = investment.tier.cycle_days if investment.tier else elapsed_days
        return max(0, min(elapsed_days, cycle_days))

    @classmethod
    def calculate_daily_profit(cls, investment):
        return cls.quantize_amount(investment.amount_invested * cls.get_daily_rate(investment))

    @classmethod
    def calculate_cumulative_gains(cls, investment, reference_time=None):
        elapsed_days = cls.get_capped_elapsed_days(investment, reference_time=reference_time)
        daily_profit = cls.calculate_daily_profit(investment)
        return cls.quantize_amount(daily_profit * elapsed_days)

    @classmethod
    def is_partner_category(cls, tier):
        return bool(tier and tier.name in cls.PARTNER_CATEGORY_NAMES)

    @classmethod
    def get_partner_bonus_checkpoints(cls, investment, reference_time=None):
        if not cls.is_partner_category(investment.tier):
            return []

        elapsed_days = cls.get_capped_elapsed_days(investment, reference_time=reference_time)
        return list(range(cls.PARTNER_BONUS_INTERVAL_DAYS, elapsed_days + 1, cls.PARTNER_BONUS_INTERVAL_DAYS))

    @classmethod
    def calculate_partner_bonus_total(cls, investment, reference_time=None):
        checkpoints = cls.get_partner_bonus_checkpoints(investment, reference_time=reference_time)
        return cls.quantize_amount(cls.PARTNER_FIXED_BONUS * len(checkpoints))


class CalculationService:
    @staticmethod
    def calculate_daily_returns(investment):
        now = timezone.now()

        if investment.status != Investment.Status.ACTIVE:
            return {'gains': 0, 'message': 'Investissement non actif'}

        if now < investment.start_date:
            return {'gains': 0, 'message': 'Investissement pas encore commence'}

        days_passed = YieldRuleService.get_capped_elapsed_days(investment, reference_time=now)
        daily_rate = float(YieldRuleService.get_daily_rate(investment))
        cumulative_gains = YieldRuleService.calculate_cumulative_gains(investment, reference_time=now)
        partner_bonus_total = YieldRuleService.calculate_partner_bonus_total(investment, reference_time=now)
        total_gains = YieldRuleService.quantize_amount(cumulative_gains + partner_bonus_total)

        return {
            'gains': float(total_gains),
            'jours_ecoules': days_passed,
            'taux_journalier': daily_rate * 100.0,
            'multiplicateur': 1.0,
            'booster_actif': False,
            'bonus_partenaire_total': float(partner_bonus_total),
        }

    @staticmethod
    def user_total_gains(user):
        investments = Investment.objects.filter(user=user, status=Investment.Status.ACTIVE)
        gains_total = Decimal("0")
        details = []

        for investment in investments:
            result = CalculationService.calculate_daily_returns(investment)
            gains_total += Decimal(str(result['gains']))
            details.append({
                'investment_id': investment.id,
                **result,
            })

        return {
            'gains_total': float(YieldRuleService.quantize_amount(gains_total)),
            'nombre_investissements': investments.count(),
            'details': details,
        }

    @staticmethod
    def simulate_investment(montant, tier_id=None):
        montant = Decimal(str(montant))
        tier = None

        if tier_id:
            tier = InvestmentTier.objects.filter(id=tier_id).first()
        else:
            tier = InvestmentTier.get_tier_by_amount(montant)

        if not tier:
            return {'error': 'Aucune categorie active ne correspond a ce montant.'}

        if montant < tier.min_amount:
            return {'error': f'Montant minimum: {tier.min_amount} XOF'}

        if tier.max_amount and montant > tier.max_amount:
            return {'error': f'Montant maximum: {tier.max_amount} XOF'}

        duree = tier.cycle_days
        taux = YieldRuleService.get_daily_rate(tier)
        gain_brut = YieldRuleService.quantize_amount(montant * taux * duree)

        bonus_partenaire_total = Decimal("0")
        if YieldRuleService.is_partner_category(tier):
            bonus_count = duree // YieldRuleService.PARTNER_BONUS_INTERVAL_DAYS
            bonus_partenaire_total = YieldRuleService.quantize_amount(
                YieldRuleService.PARTNER_FIXED_BONUS * bonus_count
            )

        gain_net = YieldRuleService.quantize_amount(gain_brut + bonus_partenaire_total)
        gain_total = YieldRuleService.quantize_amount(montant + gain_net)
        roi_percent = YieldRuleService.quantize_amount((gain_net / montant) * 100)

        return {
            'tier': {
                'id': tier.id,
                'nom': tier.name,
                'niveau': tier.level,
                'badge': tier.badge,
                'couleur': tier.badge_color,
                'avantages': tier.advantages,
            },
            'capital': float(montant),
            'duree_jours': duree,
            'taux_journalier_pourcent': float(taux * 100),
            'gain_total': float(gain_total),
            'gain_net': float(gain_net),
            'roi_pourcent': float(roi_percent),
            'bonus_partenaire_total': float(bonus_partenaire_total),
        }

    @staticmethod
    def project_gains(capital, taux_journalier, jours):
        projections = []
        capital = Decimal(str(capital))
        taux_journalier = Decimal(str(taux_journalier))
        gain_jour = YieldRuleService.quantize_amount(capital * taux_journalier)

        for jour in range(1, jours + 1):
            gain_cumule = YieldRuleService.quantize_amount(gain_jour * jour)
            projections.append({
                'jour': jour,
                'gain_jour': float(gain_jour),
                'gain_cumule': float(gain_cumule),
                'capital_total': float(YieldRuleService.quantize_amount(capital + gain_cumule)),
            })

        return projections
