from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login

def custom_login(request):
    # Si déjà connecté, on redirige intelligemment
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('/superadmin/')
        elif getattr(request.user, 'is_platform_admin', False):
            return redirect('/manager/')
        return redirect('/')

    error = None
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        # 1. Tentative avec le nom d'utilisateur (Pseudo) classique
        user = authenticate(request, username=u, password=p)
        
        # 2. Si échoue, système robuste : on cherche par Email OU Téléphone
        if user is None:
            from django.contrib.auth import get_user_model
            from django.db.models import Q
            User = get_user_model()
            try:
                # Cherche l'utilisateur qui match l'email ou le tel saisi
                user_obj = User.objects.get(Q(email=u) | Q(phone_number=u))
                # Ré-authentifie avec le "vrai" pseudo en arrière-plan
                user = authenticate(request, username=user_obj.username, password=p)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                pass
                
        
        if user is not None:
            login(request, user)
            # Redirection post-connexion
            if user.is_superuser:
                return redirect('/superadmin/')
            elif getattr(user, 'is_platform_admin', False):
                return redirect('/manager/')
            return redirect('/')
        else:
            error = "Identifiants incorrects. Veuillez réessayer."
            
    return render(request, 'login.html', {'error': error})

def custom_logout(request):
    """Déconnexion métier robuste gérant la requête GET (Évite l'erreur 405)"""
    from django.contrib.auth import logout
    logout(request)
    return redirect('login')

from .forms import CustomUserCreationForm

def custom_register(request):
    """Gère l'inscription d'un nouvel utilisateur."""
    if request.user.is_authenticated:
        return redirect('/')
        
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Connexion automatique après création
            login(request, user)
            return redirect('/')
    else:
        # On peut pré-remplir le parrain si ?ref=pseudo est dans l'URL
        sponsor_ref = request.GET.get('ref', '')
        form = CustomUserCreationForm(initial={'sponsor_code': sponsor_ref})
        
    return render(request, 'register.html', {'form': form})
