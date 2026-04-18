import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

# Trouvons le compte 'directeur' ou l'utilisateur superadmin actuel
superusers = User.objects.filter(is_superuser=True)
if superusers.exists():
    admin = superusers.first()
    admin.set_password('admin1234')
    admin.save()
    print(f"[{admin.username}] {admin.phone_number} / Mot de passe mis a jour: admin1234")
else:
    # Créons-en un nouveau si aucun n'existe
    try:
        admin = User.objects.create_superuser('admin', 'admin@example.com', 'admin1234', phone_number='+22600000000')
        print("Nouvel admin créé. Username: admin / Password: admin1234")
    except Exception as e:
        print(f"Erreur lors de la creation: {e}")
