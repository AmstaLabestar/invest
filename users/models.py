from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    # Remplacement de l'identifiant prinicipal par le numéro de téléphone (optionnel en Django natif, ici on le garde simple)
    phone_number = models.CharField(max_length=15, unique=True, verbose_name="Numéro de téléphone")
    
    # Finances & Gamification
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Solde Total")
    points = models.IntegerField(default=0, verbose_name="Points de Fidélité")
    
    # Rôle spécifique métier
    is_platform_admin = models.BooleanField(default=False, verbose_name="Est Admin Plateforme")
    
    # Parrainage MLM (Binaire)
    sponsor = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals', verbose_name="Parrain")
    
    BINARY_CHOICES = [
        ('LEFT', 'Gauche'),
        ('RIGHT', 'Droite'),
    ]
    binary_position = models.CharField(choices=BINARY_CHOICES, max_length=5, null=True, blank=True, verbose_name="Position Binaire (Gauche/Droite)")

    @property
    def unread_notifications_count(self):
        return self.notifications.filter(is_read=False).count()

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

class Notification(models.Model):
    """Modèle pour stocker les alertes et notifications système des utilisateurs"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif: {self.title} pour {self.user.username}"
