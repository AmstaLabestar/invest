from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CustomUserCreationForm
from .models import OTPChallenge
from .security import OTPService


def _redirect_authenticated_user(user):
    """Route users to the appropriate dashboard for their role."""
    if user.is_superuser:
        return redirect('/superadmin/')
    if getattr(user, 'is_platform_admin', False):
        return redirect('/manager/')
    return redirect('/')


def custom_login(request):
    # Si deja connecte, on redirige intelligemment
    if request.user.is_authenticated:
        return _redirect_authenticated_user(request.user)

    error = None
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')

        # 1. Tentative avec le nom d'utilisateur (Pseudo) classique
        user = authenticate(request, username=u, password=p)

        # 2. Si echec, systeme robuste : recherche par email ou telephone
        if user is None:
            from django.contrib.auth import get_user_model
            from django.db.models import Q

            user_model = get_user_model()
            try:
                user_obj = user_model.objects.get(Q(email=u) | Q(phone_number=u))
                user = authenticate(request, username=user_obj.username, password=p)
            except (user_model.DoesNotExist, user_model.MultipleObjectsReturned):
                pass

        if user is not None:
            if user.otp_enabled:
                try:
                    challenge = OTPService.create_challenge(user, OTPChallenge.Purpose.LOGIN)
                except Exception:
                    error = "Impossible d'envoyer le code de securite pour le moment."
                    return render(request, 'login.html', {'error': error})
                request.session['otp_user_id'] = user.id
                request.session['otp_challenge_id'] = challenge.id
                return redirect('otp_verify')

            login(request, user)
            return _redirect_authenticated_user(user)

        error = "Identifiants incorrects. Veuillez reessayer."

    return render(request, 'login.html', {'error': error})


def otp_verify(request):
    challenge_id = request.session.get('otp_challenge_id')
    user_id = request.session.get('otp_user_id')
    if not challenge_id or not user_id:
        return redirect('login')

    challenge = get_object_or_404(
        OTPChallenge.objects.select_related('user'),
        id=challenge_id,
        user_id=user_id,
        purpose=OTPChallenge.Purpose.LOGIN,
    )

    error = None
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        if OTPService.verify_challenge(challenge, code):
            user = challenge.user
            request.session.pop('otp_user_id', None)
            request.session.pop('otp_challenge_id', None)
            login(request, user)
            return _redirect_authenticated_user(user)
        error = "Code invalide ou expire."

    return render(request, 'otp_verify.html', {'error': error})


def custom_logout(request):
    """Deconnexion gerant la requete GET pour eviter l'erreur 405."""
    from django.contrib.auth import logout

    logout(request)
    return redirect('login')


def custom_register(request):
    """Gere l'inscription d'un nouvel utilisateur."""
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('/')
    else:
        sponsor_ref = request.GET.get('ref', '')
        form = CustomUserCreationForm(initial={'sponsor_code': sponsor_ref})

    return render(request, 'register.html', {'form': form})


@login_required(login_url='/login/')
def settings_security(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'send_otp':
            try:
                challenge = OTPService.create_challenge(request.user, OTPChallenge.Purpose.ENABLE)
            except Exception:
                messages.error(request, "Impossible d'envoyer le code de securite.")
                return redirect('settings_security')
            request.session['enable_otp_challenge_id'] = challenge.id
            messages.success(request, "Code de securite envoye.")
            return redirect('settings_security')

        if action == 'confirm_otp':
            challenge_id = request.session.get('enable_otp_challenge_id')
            challenge = OTPChallenge.objects.filter(
                id=challenge_id,
                user=request.user,
                purpose=OTPChallenge.Purpose.ENABLE,
            ).first()
            code = request.POST.get('code', '').strip()
            if challenge and OTPService.verify_challenge(challenge, code):
                request.user.otp_enabled = True
                request.user.save(update_fields=['otp_enabled'])
                request.session.pop('enable_otp_challenge_id', None)
                messages.success(request, "OTP active.")
                return redirect('settings_security')
            messages.error(request, "Code invalide ou expire.")
            return redirect('settings_security')

        if action == 'disable_otp':
            request.user.otp_enabled = False
            request.user.save(update_fields=['otp_enabled'])
            messages.success(request, "OTP desactive.")
            return redirect('settings_security')

    pending_challenge = None
    challenge_id = request.session.get('enable_otp_challenge_id')
    if challenge_id:
        pending_challenge = OTPChallenge.objects.filter(
            id=challenge_id,
            user=request.user,
            purpose=OTPChallenge.Purpose.ENABLE,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).first()

    return render(request, 'settings_security.html', {
        'pending_challenge': pending_challenge,
    })
