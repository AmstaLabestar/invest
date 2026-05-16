from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash, get_user_model
from django.contrib.auth.forms import PasswordChangeForm
User = get_user_model()
from django.contrib import messages
from django.http import JsonResponse
import json
from .models import Investment, Transaction, Booster, UserBooster, SystemSettings, InvestmentTier
from .services import CalculationService, WalletService, YieldRuleService
from users.models import Notification
from django.db.models import Sum
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import uuid

@login_required(login_url='/login/')
def simulate_investment_api(request):
    """API pour simuler un investissement"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            montant = data.get('amount')
            tier_id = data.get('tier_id')
            
            if not montant:
                return JsonResponse({'success': False, 'message': 'Le montant est requis'})
                
            result = CalculationService.simulate_investment(montant, tier_id)
            if 'error' in result:
                return JsonResponse({'success': False, 'message': result['error']})
                
            # Ajouter les données de projection (graphique)
            projection = CalculationService.project_gains(
                result['capital'], 
                result['taux_journalier_pourcent'] / 100, 
                result['duree_jours']
            )
            
            return JsonResponse({
                'success': True,
                'data': {
                    'simulation': result,
                    'projection': projection[:7] # Afficher max 7 points par défaut
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'})

@login_required(login_url='/login/')
def unread_notifications_count(request):
    """Endpoint API pour poll dynamiquement le nombre de notifications non lues"""
    count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'count': count})

@login_required(login_url='/login/')
def home(request):
    """Dashboard Principal Utilisateur"""
    user = request.user
    
    # Agrégation des vraies données depuis la BD
    active_invs = Investment.objects.filter(user=user, status=Investment.Status.ACTIVE)
    investi_total = WalletService.get_total_invested_capital(user)
    produits_actifs = active_invs.values('tier').distinct().count()
    
    # Calcul des gains du mois (Transactions de type ROI validées ce mois-ci)
    from django.utils import timezone
    first_day_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0)
    gains_mois = WalletService.get_realized_gains(user, start_date=first_day_of_month)
    
    # Transactions récentes (max 3)
    transactions = Transaction.objects.filter(user=user).order_by('-created_at')[:3]

    # Progression basée sur les points de fidélité du User (Données Réelles)
    progression_mois = user.points
    progression_max = 100 # Palier par défaut (peut être rendu dynamique plus tard)
    progression_percent = int((progression_mois / progression_max) * 100) if progression_max > 0 else 0
    if progression_percent > 100:
        progression_percent = 100

    active_booster = UserBooster.objects.filter(user=request.user, is_active=True).first()
    
    # Calcul estimé du gain journalier en fonction des investissements actifs
    gains_jour = sum(YieldRuleService.calculate_daily_profit(i) for i in active_invs)

    # Calculate pending withdrawals to show reserved money
    pending_withdrawals = WalletService.get_reserved_balance(user)
    total_balance = WalletService.get_total_balance(user)

    context = {
        'solde_total': "{:,.0f}".format(total_balance).replace(',', '.'),
        'gains_mois': f"+{gains_mois:,.0f}".replace(',', '.'),
        'points': user.points,
        'gains_jour': f"+{gains_jour:,.0f}".replace(',', '.'),
        'active_booster': active_booster,
        'investi_total': "{:,.0f}".format(investi_total).replace(',', '.'),
        'pending_withdrawals': "{:,.0f}".format(pending_withdrawals).replace(',', '.') if pending_withdrawals > 0 else 0,
        'produits_actifs': produits_actifs,
        'progression_mois': progression_mois,
        'progression_max': progression_max,
        'progression_percent': progression_percent,
        'transactions': transactions,
        'produits_populaires': InvestmentTier.objects.filter(is_active=True).order_by('level')[:3]
    }
    return render(request, 'home.html', context)

@login_required(login_url='/login/')
def trade(request):
    """Page d'Investissement / Liste des Produits réels"""
    tiers = InvestmentTier.objects.filter(is_active=True).order_by('level')
    active_investments = Investment.objects.filter(user=request.user, status=Investment.Status.ACTIVE)
    
    if request.method == 'POST':
        montant = request.POST.get('amount')
        tier_id = request.POST.get('tier_id')
        provider = request.POST.get('provider', 'Mobile Money')
        phone = request.POST.get('phone', '')
        
        if montant and tier_id and provider and phone:
            try:
                montant = Decimal(str(montant))
                tier = get_object_or_404(InvestmentTier, id=tier_id)
                if montant >= tier.min_amount:
                    with transaction.atomic():
                        
                        daily_rate = float(tier.daily_rate)
                        cycle_days = tier.cycle_days
                            
                        end_date = timezone.now() + timedelta(days=cycle_days)
                        
                        # Création de l'investissement avec Palier en mode "En Attente de Paiement"
                        inv = Investment.objects.create(
                            user=request.user, 
                            tier=tier,
                            amount_invested=montant,
                            daily_rate_snapshot=daily_rate,
                            end_date=end_date,
                            status=Investment.Status.PENDING
                        )
                        
                        # Génération de la transaction de type Checkout
                        tx_ref = f"PAY-{request.user.id}-{uuid.uuid4().hex[:6].upper()}"
                        Transaction.objects.create(
                            user=request.user, 
                            tx_type=Transaction.TransactionType.PAY_INVEST,
                            amount=montant, 
                            provider=f"{provider} ({phone})", 
                            status=Transaction.Status.PENDING,
                            tx_reference=tx_ref,
                            related_investment=inv
                        )
                            
                        # Notification pour le client
                        Notification.objects.create(
                            user=request.user,
                            title="Paiement en attente",
                            message=f"Votre achat direct de {montant:,.0f} XOF a été initié. Veuillez vérifier votre téléphone pour le code de sécurité.".replace(',', ' ')
                        )
                            
                    messages.warning(request, f"Veuillez finaliser le paiement Mobile Money de {montant} XOF pour activer le palier {tier.name}.")
                else:
                    messages.error(request, f"La mise minimum pour ce palier est de {tier.min_amount} XOF")
            except Exception as e:
                messages.error(request, "Erreur dans le traitement du montant. Veuillez réessayer.")
        return redirect('trade')
        
    return render(request, 'trade.html', {
        'tiers': tiers, 
        'active_investments': active_investments
    })

@login_required(login_url='/login/')
def booster(request):
    """Page des Boosters réels et Tableau de bord Binaire"""
    if request.method == 'POST':
        booster_id = request.POST.get('booster_id')
        if booster_id:
            try:
                b = get_object_or_404(Booster, id=booster_id)
                if request.user.balance >= b.price:
                    with transaction.atomic():
                        request.user.balance -= b.price
                        request.user.save(update_fields=['balance'])
                        
                        from django.utils import timezone
                        from datetime import timedelta
                        
                        end_d = timezone.now() + timedelta(days=b.duration_days)
                        UserBooster.objects.create(user=request.user, booster=b, end_date=end_d)
                        
                        tx_ref = f"BOOST-{request.user.id}-{uuid.uuid4().hex[:6].upper()}"
                        Transaction.objects.create(
                            user=request.user,
                            tx_type=Transaction.TransactionType.BOOSTER,
                            amount=b.price,
                            provider='INTERNAL',
                            status=Transaction.Status.SUCCESS,
                            tx_reference=tx_ref
                        )
                        
                        Notification.objects.create(
                            user=request.user,
                            title="Booster Activé 🚀",
                            message=f"Le booster {b.name} a été appliqué avec succès ! Vos gains sont accélérés."
                        )
                        
                    messages.success(request, f"Le booster {b.name} a été activé ! Votre solde a été débité de {b.price:,.0f} XOF.".replace(',', ' '))
                else:
                    messages.error(request, "Votre solde est insuffisant pour activer ce booster.")
            except Exception as e:
                messages.error(request, "Une erreur s'est produite lors de l'activation.")
        return redirect('booster')

    boosters = Booster.objects.filter(is_active=True)
    user_boosters = UserBooster.objects.filter(user=request.user, is_active=True)
    
    # Parrainage Binaire (Real Data)
    user = request.user
    left_count = user.referrals.filter(binary_position='LEFT').count()
    right_count = user.referrals.filter(binary_position='RIGHT').count()
    
    # Progress Calculation matching the "5G + 5D" target
    target_leg = 5
    progress_left = min(left_count, target_leg)
    progress_right = min(right_count, target_leg)
    bonus_progress_percent = int(((progress_left + progress_right) / (target_leg * 2)) * 100)
    
    # Génération d'un faux code de parrainage dynamique basé sur le vrai user (Pour l'interface)
    referral_code = f"INV-{user.username[:3].upper()}-{user.id}"
    
    # pending withdrawals for booster view
    pending_withdrawals = WalletService.get_reserved_balance(user)

    context = {
        'boosters': boosters,
        'user_boosters': user_boosters,
        'left_count': left_count,
        'right_count': right_count,
        'target_leg': target_leg,
        'bonus_progress_percent': bonus_progress_percent,
        'referral_code': referral_code,
        'pending_withdrawals': "{:,.0f}".format(pending_withdrawals).replace(',', '.') if pending_withdrawals > 0 else 0,
    }
    
    return render(request, 'booster.html', context)

@login_required(login_url='/login/')
def withdraw_request(request):
    """Traitement de la demande de retrait depuis l'interface client (Booster/Ramasser)"""
    if request.method == 'POST':
        amount_str = request.POST.get('amount')
        provider = request.POST.get('provider', 'Mobile Money')
        phone = request.POST.get('phone', request.user.phone_number)
        
        try:
            amount = Decimal(str(amount_str))
            if amount <= 0:
                raise ValueError("Withdrawal amount must be positive")
            settings = SystemSettings.objects.first()
            min_withdraw = settings.min_withdrawal if settings else Decimal('5000')
            
            if amount < min_withdraw:
                messages.error(request, f"Le montant minimum de retrait est de {min_withdraw:,.0f} XOF.".replace(',', ' '))
            else:
                with transaction.atomic():
                    # Verrouillage de la ligne Utilisateur pour éviter le double-spend (Faille de course)
                    safe_user = User.objects.select_for_update().get(id=request.user.id)
                    
                    if amount > WalletService.get_withdrawable_amount(safe_user):
                        messages.error(request, "Solde insuffisant pour ce retrait.")
                        next_url = request.META.get('HTTP_REFERER', 'booster')
                        return redirect(next_url)
                    else:
                        # Déduire le solde protégé
                        safe_user.balance -= amount
                        safe_user.save(update_fields=['balance'])
                        
                        # Créer la transaction de Retrait
                    tx_ref = f"RET-{request.user.id}-{uuid.uuid4().hex[:6].upper()}"
                    Transaction.objects.create(
                        user=request.user,
                        tx_type=Transaction.TransactionType.WITHDRAWAL,
                        amount=amount,
                        status=Transaction.Status.PENDING,
                        provider=f"{provider} ({phone})",
                        tx_reference=tx_ref
                    )
                    
                    # Notification client
                    Notification.objects.create(
                        user=request.user,
                        title="Demande de retrait reçue",
                        message=f"Votre demande de retrait de {amount:,.0f} XOF via {provider} est en cours de validation par nos services.".replace(',', ' ')
                    )
                
                messages.success(request, f"Votre demande de retrait de {amount:,.0f} XOF a été enregistrée avec succès.".replace(',', ' '))
        except Exception as e:
            messages.error(request, "Veuillez entrer un montant valide.")
            
    # On redirige vers la source de la requête si possible, sinon vers booster
    next_url = request.META.get('HTTP_REFERER', 'booster')
    return redirect(next_url)

@login_required(login_url='/login/')
def profile(request):
    """Profil Utilisateur réel"""
    user = request.user
    return render(request, 'profile.html', {'user': user})

@login_required(login_url='/login/')
def settings_password(request):
    """Mise à jour sécurisée du mot de passe"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user) # Évite la déconnexion après maj mdp
            messages.success(request, 'Votre mot de passe a été mis à jour avec succès.')
            return redirect('profile')
        else:
            messages.error(request, 'Veuillez corriger les erreurs encadrées en rouge.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'settings_password.html', {'form': form})

@login_required(login_url='/login/')
def settings_theme(request):
    """Vue statique présentant le Thème Actif"""
    return render(request, 'settings_theme.html')

@login_required(login_url='/login/')
def settings_points(request):
    """Logique et affichage des Points de Fidélité et mécanisme d'échange"""
    user = request.user
    
    # Calcul dynamique du niveau
    niveau = "Bronze"
    color_class = "text-yellow-600"
    if user.points >= 500:
        niveau = "Or"
        color_class = "text-yellow-400"
    elif user.points >= 100:
        niveau = "Argent"
        color_class = "text-gray-400"
        
    if request.method == 'POST':
        # Conversion : 1 Point = 100 XOF Bonus
        if user.points > 0:
            montant_gagné = user.points * 100
            user.balance += montant_gagné
            
            # Enregistrement de la transaction
            Transaction.objects.create(
                user=user,
                tx_type=Transaction.TransactionType.BONUS,
                amount=montant_gagné,
                provider='SYSTEM_CONVERSION',
                status=Transaction.Status.SUCCESS,
                tx_reference=f"CONV-{user.id}-{user.points}"
            )
            
            user.points = 0
            user.save()
            messages.success(request, f"Félicitations ! Vos points ont été convertis en {montant_gagné} XOF.")
            return redirect('settings_points')
        else:
            messages.error(request, "Vous n'avez pas de points à échanger.")
            return redirect('settings_points')

    context = {
        'user': user,
        'niveau': niveau,
        'color_class': color_class
    }
    return render(request, 'settings_points.html', context)

@login_required(login_url='/login/')
def settings_info(request):
    """Mise à jour des informations personnelles"""
    user = request.user
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        messages.success(request, 'Vos informations ont été mises à jour.')
        return redirect('profile')
    return render(request, 'settings_info.html', {'user': user})

@login_required(login_url='/login/')
def settings_history(request):
    """Affiche toutes les transactions de l'utilisateur chronologiquement"""
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'settings_history.html', {'transactions': transactions})

@login_required(login_url='/login/')
def settings_support(request):
    """FAQ Dynamique et Contact"""
    return render(request, 'settings_support.html')

@login_required(login_url='/login/')
def notifications_list(request):
    """Liste des notifications (Marque automatiquement comme lu à l'ouverture)"""
    notifications = Notification.objects.filter(user=request.user)
    
    # Marquer toutes les non-lues comme lues
    unread_notifs = notifications.filter(is_read=False)
    if unread_notifs.exists():
        unread_notifs.update(is_read=True)
        
    return render(request, 'notifications.html', {'notifications': notifications})
