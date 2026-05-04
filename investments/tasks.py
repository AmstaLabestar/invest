from celery import shared_task
from django.utils import timezone
from .models import Investment, Transaction
from django.contrib.auth import get_user_model
from django.db import transaction
import uuid

User = get_user_model()

@shared_task
def calculate_daily_roi():
    """
    Tâche CRON quotidienne.
    Distribue les pourcentages de ROI (daily_roi_percentage) sur le solde des utilisateurs pour tous les investissements actifs.
    """
    active_investments = Investment.objects.filter(
        status=Investment.Status.ACTIVE
    ).select_related('user', 'tier')
    
    with transaction.atomic():
        for inv in active_investments:
            user = inv.user
            tier = inv.tier
            
            # Calcul du rendement du jour
            daily_profit = inv.amount_invested * inv.daily_rate_snapshot
            
            # Vérification et Application du Booster
            from .models import UserBooster
            active_booster = UserBooster.objects.filter(user=user, is_active=True).first()
            if active_booster:
                if active_booster.end_date >= timezone.now():
                    daily_profit = daily_profit * active_booster.booster.multiplier
                else:
                    # Le booster est expiré
                    active_booster.is_active = False
                    active_booster.save(update_fields=['is_active'])
            
            # Créditer le solde de l'utilisateur
            user.balance += daily_profit
            user.save(update_fields=['balance'])
            
            # Enregistrer la transaction pour l'historique
            tx_ref = f"ROI-{user.id}-{uuid.uuid4().hex[:8].upper()}"
            Transaction.objects.create(
                user=user,
                tx_type=Transaction.TransactionType.ROI,
                amount=daily_profit,
                status=Transaction.Status.SUCCESS,
                provider='System',
                tx_reference=tx_ref
            )
            
    return f"Calculs de ROI terminés pour {active_investments.count()} investissements actifs."


# --- ALGORITHME DE PARRAINAGE BINAIRE ---
def get_node_volume(user):
    """Calcule de manière récursive le volume d'investissement total généré par l'arbre sous cet utilisateur."""
    # Note : Sur un vrai serveur en production à très haute charge, on préférera une structure MPTT (Modified Preorder Tree Traversal)
    # pour optimiser la requête SQL de l'arbre, mais cette récursion fait le travail pour la maquette.
    
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
    Tâche CRON hebdomadaire ou quotidienne.
    Parcourt tous les utilisateurs ayant des filleuls, calcule le volume Gauche vs Droite,
    identifie la "patte faible" et octroie un bonus binaire.
    """
    # Pourcentage du bonus binaire (souvent 10% dans les MLM classiques)
    BINARY_BONUS_PERCENTAGE = 10
    
    users_with_referrals = User.objects.filter(referrals__isnull=False).distinct()
    
    with transaction.atomic():
        for user in users_with_referrals:
            # Identifier les têtes de branche Gauche et Droite
            left_leg_head = user.referrals.filter(binary_position='LEFT').first()
            right_leg_head = user.referrals.filter(binary_position='RIGHT').first()
            
            left_volume = get_node_volume(left_leg_head) if left_leg_head else 0
            right_volume = get_node_volume(right_leg_head) if right_leg_head else 0
            
            # Déterminer la patte faible
            weak_leg_volume = min(left_volume, right_volume)
            
            if weak_leg_volume > 0:
                bonus_amount = (weak_leg_volume * BINARY_BONUS_PERCENTAGE) / 100
                
                # NOTE: Dans un vrai module MLM, on stocke le "volume déjà payé" pour ne pas repayer sur l'ancien volume.
                # Pour cette maquette interactive, on laisse la logique de base.
                
                # Créditer le bonus
                user.balance += bonus_amount
                user.save(update_fields=['balance'])
                
                tx_ref = f"BONUS-{user.id}-{uuid.uuid4().hex[:8].upper()}"
                Transaction.objects.create(
                    user=user,
                    tx_type=Transaction.TransactionType.BONUS,
                    amount=bonus_amount,
                    status=Transaction.Status.SUCCESS,
                    provider='Binary Bonus',
                    tx_reference=tx_ref
                )
                
    return f"Calculs des bonus binaires terminés."
