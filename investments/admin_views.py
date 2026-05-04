from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Sum
from .models import Transaction, Booster, Investment, SystemSettings, PaymentConfig, AuditLog, InvestmentTier
from .forms import SystemSettingsForm, PaymentConfigForm
from django.contrib.auth import get_user_model
from users.forms import CustomUserCreationForm, CustomUserEditForm
from users.models import Notification

User = get_user_model()


def is_manager(user):
    return user.is_authenticated and (
        getattr(user, 'is_platform_admin', False) or user.is_superuser
    )


def is_superadmin(user):
    return user.is_authenticated and user.is_superuser


from django.utils import timezone
from datetime import timedelta


@user_passes_test(is_manager, login_url='/login/')
def manager_dashboard(request):
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = timezone.now() - timedelta(days=30)

    pending_txs = Transaction.objects.filter(status='PENDING').order_by('-created_at')

    total_users = User.objects.count()
    active_users_30d = User.objects.filter(last_login__gte=thirty_days_ago).count()
    activity_rate = int((active_users_30d / total_users * 100) if total_users > 0 else 0)

    # Statistiques d'investissements
    total_invested = Investment.objects.filter().aggregate(Sum('amount_invested'))['amount_invested__sum'] or 0
    new_invested_today = Investment.objects.filter(start_date__gte=today).aggregate(Sum('amount_invested'))['amount_invested__sum'] or 0

    # Statistiques Retraits
    withdrawals_today = Transaction.objects.filter(
        tx_type=Transaction.TransactionType.WITHDRAWAL,
        created_at__gte=today
    )
    withdrawals_today_val = withdrawals_today.aggregate(Sum('amount'))['amount__sum'] or 0

    # Alertes Systeme (Dynamiques basees sur l'etat reel)
    pending_withdrawals_count = pending_txs.filter(
        tx_type=Transaction.TransactionType.WITHDRAWAL
    ).count()
    alerts = []
    if pending_withdrawals_count > 0:
        alerts.append({'type': 'warning', 'message': f'{pending_withdrawals_count} retrait(s) en attente de validation.'})
    failed_txs_today = Transaction.objects.filter(status='FAILED', created_at__gte=today).count()
    if failed_txs_today > 0:
        alerts.append({'type': 'error', 'message': f"{failed_txs_today} transaction(s) echouee(s) aujourd'hui."})
    alerts.append({'type': 'success', 'message': 'Le systeme de paiement est operationnel et synchronise.'})

    stats = {
        'total_users': total_users,
        'new_users': User.objects.filter(date_joined__gte=today).count(),
        'total_invested': total_invested,
        'new_invested_today': new_invested_today,
        'withdrawals_today_amount': withdrawals_today_val,
        'withdrawals_today_count': withdrawals_today.count(),
        'activity_rate': activity_rate,
    }

    recent_users = User.objects.all().order_by('-date_joined')[:5]
    tiers = InvestmentTier.objects.all().order_by('level')
    boosters = Booster.objects.all()

    context = {
        'stats': stats,
        'pending_txs': pending_txs,
        'alerts': alerts,
        'recent_users': recent_users,
        'tiers': tiers,
        'boosters': boosters,
    }

    return render(request, 'manager/dashboard.html', context)


@user_passes_test(is_manager, login_url='/login/')
def process_transaction(request, tx_id, action):
    tx = get_object_or_404(Transaction, id=tx_id, status='PENDING')

    if action == 'approve':
        tx.status = 'SUCCESS'
        if tx.tx_type == Transaction.TransactionType.PAY_INVEST and tx.related_investment:
            inv = tx.related_investment
            inv.status = 'ACTIVE'
            inv.start_date = timezone.now()
            inv.save()

            # Application des points exclusifs au bonus de parrainage
            is_first_investment = Investment.objects.filter(user=tx.user, status='ACTIVE').count() == 1
            if is_first_investment and tx.user.sponsor and inv.amount_invested >= 10000:
                tx.user.sponsor.points += 20
                tx.user.sponsor.save(update_fields=['points'])
                Notification.objects.create(
                    user=tx.user.sponsor,
                    title="Bonus de Parrainage Actif !",
                    message=f"Votre filleul {tx.user.username} a active un palier VIP. Vous gagnez +20 Points VIP !"
                )
            Notification.objects.create(
                user=tx.user,
                title="Palier Active",
                message=f"Votre paiement de {tx.amount:,.0f} XOF a ete confirme. Votre palier est actif !".replace(',', ' ')
            )

        # Pour les retraits, le solde a DEJA ete deduit du client lors de sa demande
        tx.save()
        messages.success(request, f"Transaction de {tx.amount} XOF validee avec succes.")

    elif action == 'reject':
        tx.status = 'FAILED'
        if tx.tx_type == Transaction.TransactionType.WITHDRAWAL:
            tx.user.balance += tx.amount
            tx.user.save(update_fields=['balance'])
        elif tx.tx_type == Transaction.TransactionType.PAY_INVEST and tx.related_investment:
            related_investment = tx.related_investment
            tx.related_investment = None
            related_investment.delete()
        tx.save()
        messages.info(request, "Transaction rejetee. Les fonds lies ont ete restitues si c'etait un retrait.")

    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('manager_dashboard')


@user_passes_test(is_superadmin, login_url='/login/')
def superadmin_dashboard(request):
    tiers = InvestmentTier.objects.all().order_by('level')
    boosters = Booster.objects.all()

    # Statistiques Tresorerie
    completed_deposits = Transaction.objects.filter(
        tx_type=Transaction.TransactionType.PAY_INVEST,
        status='SUCCESS'
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    completed_withdrawals = Transaction.objects.filter(
        tx_type=Transaction.TransactionType.WITHDRAWAL,
        status='SUCCESS'
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    # Fonds Virtuels & Conversion
    virtual_balance = User.objects.aggregate(Sum('balance'))['balance__sum'] or 0
    total_invested = Investment.objects.filter(status='ACTIVE').aggregate(Sum('amount_invested'))['amount_invested__sum'] or 0

    total_users = User.objects.count()
    users_with_deposit = Transaction.objects.filter(
        tx_type=Transaction.TransactionType.PAY_INVEST,
        status='SUCCESS'
    ).values('user').distinct().count()
    conversion_rate = int((users_with_deposit / total_users * 100) if total_users > 0 else 0)

    # Logs Securite
    audit_logs = AuditLog.objects.all()[:5]

    treasury_stats = {
        'real_deposits': completed_deposits,
        'real_withdrawals': completed_withdrawals,
        'net_real': completed_deposits - completed_withdrawals,
        'virtual_balance': virtual_balance,
        'total_invested': total_invested,
        'conversion_rate': conversion_rate,
    }
    import json

    # --- GRAPHIQUES (7 Derniers Jours) ---
    today_date = timezone.now().date()
    last_7_days_dates = [(today_date - timedelta(days=i)) for i in range(6, -1, -1)]
    dates_labels = [d.strftime("%d %b") for d in last_7_days_dates]

    deposits_data = []
    withdrawals_data = []
    users_data = []

    for d in last_7_days_dates:
        day_start = timezone.make_aware(timezone.datetime.combine(d, timezone.datetime.min.time()))
        day_end = day_start + timedelta(days=1)

        dep_sum = Transaction.objects.filter(
            tx_type=Transaction.TransactionType.PAY_INVEST,
            status='SUCCESS',
            created_at__gte=day_start,
            created_at__lt=day_end
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        with_sum = Transaction.objects.filter(
            tx_type=Transaction.TransactionType.WITHDRAWAL,
            status='SUCCESS',
            created_at__gte=day_start,
            created_at__lt=day_end
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        newUser_count = User.objects.filter(date_joined__gte=day_start, date_joined__lt=day_end).count()

        deposits_data.append(float(dep_sum))
        withdrawals_data.append(float(with_sum))
        users_data.append(newUser_count)

    chart_data = json.dumps({
        'labels': dates_labels,
        'deposits': deposits_data,
        'withdrawals': withdrawals_data,
        'users': users_data
    })

    return render(request, 'superadmin/dashboard.html', {
        'tiers': tiers,
        'boosters': boosters,
        'treasury': treasury_stats,
        'audit_logs': audit_logs,
        'chart_data_json': chart_data
    })


@user_passes_test(is_superadmin, login_url='/login/')
def admin_settings_view(request):
    # singleton pattern handling
    settings_obj, created = SystemSettings.objects.get_or_create(id=1)
    if request.method == 'POST':
        form = SystemSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(admin_user=request.user, action="A modifie les parametres de la plateforme", severity='WARNING')
            return redirect('/superadmin/')
    else:
        form = SystemSettingsForm(instance=settings_obj)
    return render(request, 'superadmin/settings.html', {'form': form, 'title': 'Parametres Plateforme'})


@user_passes_test(is_superadmin, login_url='/login/')
def admin_payment_config_view(request):
    providers = PaymentConfig.objects.all()
    if request.method == 'POST':
        provider_id = request.POST.get('provider_id')
        if provider_id:
            provider = PaymentConfig.objects.get(id=provider_id)
            form = PaymentConfigForm(request.POST, instance=provider)
        else:
            form = PaymentConfigForm(request.POST)

        if form.is_valid():
            p = form.save()
            AuditLog.objects.create(admin_user=request.user, action=f"A configure l'API Mobile Money: {p.provider_name}", severity='WARNING')
            return redirect('/superadmin/mobile-money/')
    else:
        form = PaymentConfigForm()

    return render(request, 'superadmin/payment_config.html', {'providers': providers, 'form': form, 'title': 'Mobile Money API'})


@user_passes_test(is_superadmin, login_url='/login/')
def admin_users_view(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'superadmin/users.html', {'users': users, 'title': 'Gestion des Utilisateurs'})


@user_passes_test(is_superadmin, login_url='/login/')
def admin_user_toggle(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if not u.is_superuser:  # Proteger les super admins
        u.is_active = not u.is_active
        u.save()
        AuditLog.objects.create(admin_user=request.user, action=f"A {'debloque' if u.is_active else 'bloque'} l'utilisateur {u.username}", severity='WARNING')
    return redirect('admin_users')


@user_passes_test(is_superadmin, login_url='/login/')
def admin_user_create_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            u = form.save()
            AuditLog.objects.create(admin_user=request.user, action=f"A cree l'utilisateur {u.username}", severity='INFO')
            return redirect('admin_users')
    else:
        form = CustomUserCreationForm()
        # Modifions les widgets du formulaire par defaut pour qu'ils respectent le design sombre
        for field_name, field in form.fields.items():
            field.widget.attrs['class'] = 'form-input'

    return render(request, 'superadmin/user_form.html', {'form': form, 'title': 'Creer un Utilisateur', 'is_create': True})


@user_passes_test(is_superadmin, login_url='/login/')
def admin_user_edit_view(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = CustomUserEditForm(request.POST, instance=u)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(admin_user=request.user, action=f"A modifie l'utilisateur {u.username}", severity='WARNING')
            return redirect('admin_users')
    else:
        form = CustomUserEditForm(instance=u)
    return render(request, 'superadmin/user_form.html', {'form': form, 'title': f'Modifier {u.username}', 'is_create': False, 'user_obj': u})


@user_passes_test(is_superadmin, login_url='/login/')
def admin_user_delete_view(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if not u.is_superuser and request.method == 'POST':
        username = u.username
        u.delete()
        AuditLog.objects.create(admin_user=request.user, action=f"A supprime definitivement l'utilisateur {username}", severity='CRITICAL')
    return redirect('admin_users')


@user_passes_test(is_superadmin, login_url='/login/')
def admin_transactions_view(request):
    transactions = Transaction.objects.all().order_by('-created_at')
    return render(request, 'superadmin/transactions.html', {'transactions': transactions, 'title': 'Journal des Transactions'})


@user_passes_test(is_superadmin, login_url='/login/')
def admin_products_view(request):
    tiers = InvestmentTier.objects.all().order_by('level')
    boosters = Booster.objects.all()
    return render(request, 'superadmin/products.html', {'tiers': tiers, 'boosters': boosters, 'title': 'Paliers & Boosters'})


@user_passes_test(is_superadmin, login_url='/login/')
def admin_product_toggle(request, prod_id):
    p = get_object_or_404(InvestmentTier, id=prod_id)
    p.is_active = not p.is_active
    p.save()
    AuditLog.objects.create(admin_user=request.user, action=f"A {'active' if p.is_active else 'desactive'} le palier {p.name}", severity='WARNING')
    return redirect('admin_products')
