from django.utils import timezone
from .models import Investment, InvestmentTier, UserBooster

class CalculationService:
    @staticmethod
    def calculate_daily_returns(investment):
        now = timezone.now()
        start_date = investment.start_date
        end_date = investment.end_date

        if investment.status != 'ACTIVE':
            return {'gains': 0, 'message': 'Investissement non actif'}

        if now < start_date:
            return {'gains': 0, 'message': 'Investissement pas encore commencé'}

        if end_date and now > end_date:
            # S'il y a une end_date et qu'on l'a dépassée, on limite le calcul à la durée max
            days_passed = (end_date - start_date).days
        else:
            days_passed = investment.days_passed

        # Gestion du taux : on utilise en priorité le taux de l'investissement (snapshoté)
        if investment.daily_rate_snapshot and float(investment.daily_rate_snapshot) > 0:
            daily_rate = float(investment.daily_rate_snapshot)
        elif investment.tier:
            daily_rate = float(investment.tier.daily_rate)
        elif investment.product:
            daily_rate = float(investment.product.daily_roi_percentage) / 100.0
        else:
            daily_rate = 0.0
            
        capital = float(investment.amount_invested)

        # Vérifier si un booster est actif
        booster_actif = UserBooster.objects.filter(
            user=investment.user,
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).first()

        multiplicateur = 1.0
        if booster_actif:
            multiplicateur = float(booster_actif.booster.multiplier)

        # Calcul des gains avec intérêts composés
        gains_bruts = capital * ((1 + daily_rate) ** days_passed) - capital
        gains_avec_booster = gains_bruts * multiplicateur

        return {
            'gains': round(gains_avec_booster, 2),
            'jours_ecoules': days_passed,
            'taux_journalier': daily_rate * 100.0,
            'multiplicateur': multiplicateur,
            'booster_actif': bool(booster_actif)
        }

    @staticmethod
    def user_total_gains(user):
        investments = Investment.objects.filter(user=user, status='ACTIVE')
        gains_total = 0.0
        details = []

        for investment in investments:
            result = CalculationService.calculate_daily_returns(investment)
            gains_total += result['gains']
            details.append({
                'investment_id': investment.id,
                **result
            })

        return {
            'gains_total': round(gains_total, 2),
            'nombre_investissements': investments.count(),
            'details': details
        }

    @staticmethod
    def simulate_investment(montant, tier_id=None):
        montant = float(montant)
        tier = None
        
        if tier_id:
            tier = InvestmentTier.objects.filter(id=tier_id).first()
        else:
            tier = InvestmentTier.get_tier_by_amount(montant)

        if not tier:
            return {'error': 'Aucun palier trouvé pour ce montant ou ce montant ne correspond à aucun palier actif.'}

        if montant < float(tier.min_amount):
            return {'error': f'Montant minimum: {tier.min_amount} XOF'}

        if tier.max_amount and montant > float(tier.max_amount):
            return {'error': f'Montant maximum: {tier.max_amount} XOF'}

        duree = tier.cycle_days
        taux = float(tier.daily_rate)
        
        # Formule: Capital × (1 + taux)^jours
        gain_total = montant * ((1 + taux) ** duree)
        gain_net = gain_total - montant
        roi_percent = (gain_net / montant) * 100

        return {
            'tier': {
                'id': tier.id,
                'nom': tier.name,
                'niveau': tier.level,
                'badge': tier.badge,
                'couleur': tier.badge_color,
                'avantages': tier.advantages
            },
            'capital': montant,
            'duree_jours': duree,
            'taux_journalier_pourcent': taux * 100,
            'gain_total': round(gain_total, 2),
            'gain_net': round(gain_net, 2),
            'roi_pourcent': round(roi_percent, 2),
        }

    @staticmethod
    def project_gains(capital, taux_journalier, jours):
        projections = []
        for jour in range(1, jours + 1):
            gain_cumule = capital * ((1 + taux_journalier) ** jour) - capital
            
            if jour == 1:
                gain_jour = capital * taux_journalier
            else:
                gain_jour = (capital * ((1 + taux_journalier) ** jour)) - (capital * ((1 + taux_journalier) ** (jour - 1)))

            projections.append({
                'jour': jour,
                'gain_jour': round(gain_jour, 2),
                'gain_cumule': round(gain_cumule, 2),
                'capital_total': round(capital + gain_cumule, 2)
            })
            
        return projections
