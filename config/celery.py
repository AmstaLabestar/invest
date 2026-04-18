import os
from celery import Celery

# Définissez le module de paramètres Django par défaut pour le programme 'celery'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('investplatform')

# Utilisez une chaîne ici signifie que le worker n'a pas à sérialiser
# l'objet de configuration en objets enfants.
# - namespace='CELERY' signifie que toutes les clés de configuration
#   liées à celery doivent avoir un préfixe `CELERY_`.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Chargez automatiquement les modules de tâches à partir de toutes les applications Django enregistrées.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
