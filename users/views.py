from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render

from .forms import CustomUserCreationForm


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
            login(request, user)
            return _redirect_authenticated_user(user)

        error = "Identifiants incorrects. Veuillez reessayer."

    return render(request, 'login.html', {'error': error})


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
