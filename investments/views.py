import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from users.models import Notification

from .forms import SupportTicketForm
from .models import Investment, InvestmentTier, SupportTicket, SystemSettings, Transaction
from .payments import PaymentGatewayRegistry, PaymentProviderRegistry
from .services import CalculationService, WalletService, YieldRuleService


User = get_user_model()


@login_required(login_url='/login/')
def simulate_investment_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Methode non autorisee'})

    try:
        data = json.loads(request.body)
        montant = data.get('amount')
        tier_id = data.get('tier_id')
        if not montant:
            return JsonResponse({'success': False, 'message': 'Le montant est requis'})

        result = CalculationService.simulate_investment(montant, tier_id)
        if 'error' in result:
            return JsonResponse({'success': False, 'message': result['error']})

        projection = CalculationService.project_gains(
            result['capital'],
            result['taux_journalier_pourcent'] / 100,
            result['duree_jours'],
        )
        return JsonResponse({
            'success': True,
            'data': {
                'simulation': result,
                'projection': projection[:7],
            },
        })
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'message': 'Requete invalide'})


def public_stats(request):
    stats = (
        Investment.objects.filter(status=Investment.Status.ACTIVE, tier__isnull=False)
        .values('tier__name', 'tier__badge', 'tier__level')
        .annotate(member_count=Count('user', distinct=True))
        .order_by('tier__level')
    )
    total_members = User.objects.filter(is_active=True).count()
    return render(request, 'public_stats.html', {
        'stats': stats,
        'total_members': total_members,
    })


@login_required(login_url='/login/')
def unread_notifications_count(request):
    count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'count': count})


@login_required(login_url='/login/')
def home(request):
    user = request.user
    active_invs = Investment.objects.filter(user=user, status=Investment.Status.ACTIVE)
    invested_total = WalletService.get_total_invested_capital(user)
    active_categories = active_invs.values('tier').distinct().count()
    first_day_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0)
    monthly_gains = WalletService.get_realized_gains(user, start_date=first_day_of_month)
    transactions = Transaction.objects.filter(user=user).order_by('-created_at')[:3]
    progress_current = user.points
    progress_max = 100
    progress_percent = min(int((progress_current / progress_max) * 100), 100) if progress_max else 0
    daily_gains = sum(YieldRuleService.calculate_daily_profit(i) for i in active_invs)
    pending_withdrawals = WalletService.get_reserved_balance(user)
    total_balance = WalletService.get_total_balance(user)
    withdrawable_amount = WalletService.get_withdrawable_amount(user)

    context = {
        'solde_total': "{:,.0f}".format(total_balance).replace(',', '.'),
        'gains_mois': f"+{monthly_gains:,.0f}".replace(',', '.'),
        'points': user.points,
        'gains_jour': f"+{daily_gains:,.0f}".replace(',', '.'),
        'investi_total': "{:,.0f}".format(invested_total).replace(',', '.'),
        'pending_withdrawals': "{:,.0f}".format(pending_withdrawals).replace(',', '.') if pending_withdrawals > 0 else 0,
        'withdrawable_amount': "{:,.0f}".format(withdrawable_amount).replace(',', '.'),
        'produits_actifs': active_categories,
        'progression_mois': progress_current,
        'progression_max': progress_max,
        'progression_percent': progress_percent,
        'transactions': transactions,
        'produits_populaires': InvestmentTier.objects.filter(is_active=True).order_by('level')[:3],
    }
    return render(request, 'home.html', context)


@login_required(login_url='/login/')
def trade(request):
    tiers = InvestmentTier.objects.filter(is_active=True).order_by('level')
    active_investments = Investment.objects.filter(user=request.user, status=Investment.Status.ACTIVE)

    if request.method == 'POST':
        amount_value = request.POST.get('amount')
        tier_id = request.POST.get('tier_id')
        provider = request.POST.get('provider', '')
        phone = request.POST.get('phone', '').strip()

        if not amount_value or not tier_id or not provider or not phone:
            messages.error(request, "Veuillez renseigner toutes les informations de paiement.")
            return redirect('trade')

        provider_label = PaymentProviderRegistry.get_label(provider)
        if provider_label is None:
            messages.error(request, "Moyen de paiement non disponible.")
            return redirect('trade')

        try:
            amount = Decimal(str(amount_value))
            tier = get_object_or_404(InvestmentTier, id=tier_id)
            amount_is_valid = amount >= tier.min_amount and (tier.max_amount is None or amount <= tier.max_amount)
            if not amount_is_valid:
                messages.error(request, "Le montant ne correspond pas aux limites de cette categorie.")
                return redirect('trade')

            tx_ref = f"PAY-{request.user.id}-{uuid.uuid4().hex[:6].upper()}"
            payment_intent = PaymentGatewayRegistry.get_gateway(provider).initiate_payment(
                amount=amount,
                phone=phone,
                reference=tx_ref,
                user=request.user,
            )

            with transaction.atomic():
                investment = Investment.objects.create(
                    user=request.user,
                    tier=tier,
                    amount_invested=amount,
                    daily_rate_snapshot=tier.daily_rate,
                    end_date=timezone.now() + timedelta(days=tier.cycle_days),
                    status=Investment.Status.PENDING,
                )
                Transaction.objects.create(
                    user=request.user,
                    tx_type=Transaction.TransactionType.PAY_INVEST,
                    amount=amount,
                    provider=f"{payment_intent.provider_label} ({payment_intent.phone})",
                    status=Transaction.Status.PENDING,
                    tx_reference=tx_ref,
                    related_investment=investment,
                )
                Notification.objects.create(
                    user=request.user,
                    title="Paiement en attente",
                    message=(
                        f"Votre souscription de {amount:,.0f} XOF est en attente "
                        "de validation."
                    ).replace(',', ' '),
                )

            messages.warning(request, f"Paiement en attente pour la categorie {tier.name}.")
        except (ValueError, TypeError):
            messages.error(request, "Montant invalide.")
        return redirect('trade')

    return render(request, 'trade.html', {
        'tiers': tiers,
        'active_investments': active_investments,
        'payment_providers': PaymentProviderRegistry.ACTIVE_PROVIDERS,
    })


@login_required(login_url='/login/')
def actions(request):
    user = request.user
    referral_bonus_total = (
        Transaction.objects.filter(
            user=user,
            tx_type=Transaction.TransactionType.BONUS,
            status=Transaction.Status.SUCCESS,
            tx_reference__startswith='REF-BONUS-',
        ).aggregate(Sum('amount'))['amount__sum']
        or Decimal("0")
    )
    referral_link = request.build_absolute_uri(f"{reverse('register')}?ref={user.referral_code}")
    pending_withdrawals = WalletService.get_reserved_balance(user)
    withdrawable_amount = WalletService.get_withdrawable_amount(user)
    withdraw_unlock_at = WalletService.get_withdrawal_unlock_at(user)

    context = {
        'referral_code': user.referral_code,
        'referral_link': referral_link,
        'referral_count': user.referrals.count(),
        'referral_bonus_total': "{:,.0f}".format(referral_bonus_total).replace(',', '.'),
        'pending_withdrawals': "{:,.0f}".format(pending_withdrawals).replace(',', '.') if pending_withdrawals > 0 else 0,
        'withdrawable_amount': "{:,.0f}".format(withdrawable_amount).replace(',', '.'),
        'withdraw_unlock_at': withdraw_unlock_at,
        'payment_providers': PaymentProviderRegistry.ACTIVE_PROVIDERS,
    }
    return render(request, 'actions.html', context)


@login_required(login_url='/login/')
def withdraw_request(request):
    if request.method == 'POST':
        amount_value = request.POST.get('amount')
        provider = request.POST.get('provider', '')
        phone = request.POST.get('phone', request.user.phone_number)

        provider_label = PaymentProviderRegistry.get_label(provider)
        if provider_label is None:
            messages.error(request, "Moyen de retrait non disponible.")
            return redirect(request.META.get('HTTP_REFERER', 'actions'))

        try:
            amount = Decimal(str(amount_value))
            if amount <= 0:
                raise ValueError("Amount must be positive")

            settings = SystemSettings.objects.first()
            min_withdraw = settings.min_withdrawal if settings else Decimal('5000')
            if amount < min_withdraw:
                messages.error(request, f"Le montant minimum de retrait est de {min_withdraw:,.0f} XOF.".replace(',', ' '))
                return redirect(request.META.get('HTTP_REFERER', 'actions'))

            with transaction.atomic():
                safe_user = User.objects.select_for_update().get(id=request.user.id)
                unlock_at = WalletService.get_withdrawal_unlock_at(safe_user)
                if not WalletService.is_withdrawal_unlocked(safe_user):
                    unlock_label = unlock_at.strftime('%d/%m/%Y %H:%M') if unlock_at else 'plus tard'
                    messages.error(request, f"Prochain retrait possible le {unlock_label}.")
                    return redirect(request.META.get('HTTP_REFERER', 'actions'))

                if amount > WalletService.get_withdrawable_amount(safe_user):
                    messages.error(request, "Montant superieur aux gains actuellement retirables.")
                    return redirect(request.META.get('HTTP_REFERER', 'actions'))

                safe_user.balance -= amount
                safe_user.save(update_fields=['balance'])
                tx_ref = f"RET-{request.user.id}-{uuid.uuid4().hex[:6].upper()}"
                Transaction.objects.create(
                    user=request.user,
                    tx_type=Transaction.TransactionType.WITHDRAWAL,
                    amount=amount,
                    status=Transaction.Status.PENDING,
                    provider=f"{provider_label} ({phone})",
                    tx_reference=tx_ref,
                )
                Notification.objects.create(
                    user=request.user,
                    title="Demande de retrait recue",
                    message=f"Votre demande de retrait de {amount:,.0f} XOF est en cours de validation.".replace(',', ' '),
                )

            messages.success(request, f"Votre demande de retrait de {amount:,.0f} XOF a ete enregistree.".replace(',', ' '))
        except (ValueError, TypeError):
            messages.error(request, "Veuillez entrer un montant valide.")

    return redirect(request.META.get('HTTP_REFERER', 'actions'))


@login_required(login_url='/login/')
def profile(request):
    return render(request, 'profile.html', {'user': request.user})


@login_required(login_url='/login/')
def settings_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Votre mot de passe a ete mis a jour.')
            return redirect('profile')
        messages.error(request, 'Veuillez corriger les erreurs encadrees en rouge.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'settings_password.html', {'form': form})


@login_required(login_url='/login/')
def settings_theme(request):
    return render(request, 'settings_theme.html')


@login_required(login_url='/login/')
def settings_points(request):
    user = request.user
    level = "Bronze"
    color_class = "text-yellow-600"
    if user.points >= 500:
        level = "Or"
        color_class = "text-yellow-400"
    elif user.points >= 100:
        level = "Argent"
        color_class = "text-gray-400"

    if request.method == 'POST':
        if user.points <= 0:
            messages.error(request, "Vous n'avez pas de points a echanger.")
            return redirect('settings_points')

        converted_amount = user.points * 100
        user.balance += converted_amount
        Transaction.objects.create(
            user=user,
            tx_type=Transaction.TransactionType.BONUS,
            amount=converted_amount,
            provider='SYSTEM_CONVERSION',
            status=Transaction.Status.SUCCESS,
            tx_reference=f"CONV-{user.id}-{user.points}",
        )
        user.points = 0
        user.save()
        messages.success(request, f"Vos points ont ete convertis en {converted_amount} XOF.")
        return redirect('settings_points')

    return render(request, 'settings_points.html', {
        'user': user,
        'niveau': level,
        'color_class': color_class,
    })


@login_required(login_url='/login/')
def settings_info(request):
    user = request.user
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        messages.success(request, 'Vos informations ont ete mises a jour.')
        return redirect('profile')
    return render(request, 'settings_info.html', {'user': user})


@login_required(login_url='/login/')
def settings_history(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'settings_history.html', {'transactions': transactions})


@login_required(login_url='/login/')
def settings_support(request):
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.user = request.user
            ticket.save()
            Notification.objects.create(
                user=request.user,
                title="Ticket support ouvert",
                message=f"Votre demande #{ticket.id} a ete enregistree.",
            )
            messages.success(request, "Votre demande a ete envoyee au support.")
            return redirect('settings_support')
    else:
        form = SupportTicketForm()

    tickets = SupportTicket.objects.filter(user=request.user).order_by('-updated_at')
    return render(request, 'settings_support.html', {
        'form': form,
        'tickets': tickets,
    })


@login_required(login_url='/login/')
def notifications_list(request):
    notifications = Notification.objects.filter(user=request.user)
    unread_notifs = notifications.filter(is_read=False)
    if unread_notifs.exists():
        unread_notifs.update(is_read=True)
    return render(request, 'notifications.html', {'notifications': notifications})
