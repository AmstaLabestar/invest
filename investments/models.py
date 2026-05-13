from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class InvestmentTier(models.Model):
    name = models.CharField(max_length=50, verbose_name="Nom (ex: Bronze, Argent)")
    level = models.IntegerField(unique=True, verbose_name="Niveau")
    badge = models.CharField(max_length=50, blank=True, null=True, verbose_name="Emoji Badge (ex: medal)")

    min_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Montant Minimum")
    max_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Montant Maximum")

    daily_rate = models.DecimalField(max_digits=5, decimal_places=4, verbose_name="Taux journalier (ex: 0.012 = 1.2%)")
    monthly_rate = models.DecimalField(max_digits=5, decimal_places=4, verbose_name="Taux mensuel (ex: 0.36 = 36%)")

    cycle_days = models.IntegerField(verbose_name="Duree du cycle (jours)")

    badge_color = models.CharField(max_length=7, blank=True, null=True, verbose_name="Couleur Hexbadge")
    icon = models.CharField(max_length=50, blank=True, null=True, verbose_name="Icone CSS")

    advantages = models.JSONField(default=list, blank=True, verbose_name="Avantages (JSON)")

    is_active = models.BooleanField(default=True, verbose_name="Est actif")
    display_order = models.IntegerField(default=0, verbose_name="Ordre d'affichage")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Categorie d'investissement"
        verbose_name_plural = "Categories d'investissement"
        ordering = ['level']

    def __str__(self):
        return f"Niveau {self.level} - {self.name} ({self.min_amount} XOF)"

    @property
    def daily_rate_percentage(self):
        """Retourne le taux sous forme de pourcentage (ex: 1.50)"""
        if self.daily_rate:
            return self.daily_rate * 100
        return 0

    @classmethod
    def get_tier_by_amount(cls, amount):
        from django.db.models import Q
        return cls.objects.filter(
            Q(min_amount__lte=amount) &
            (Q(max_amount__gte=amount) | Q(max_amount__isnull=True)),
            is_active=True
        ).order_by('-level').first()


class Investment(models.Model):
    class Status(models.TextChoices):
        PENDING = ('PENDING', 'En attente de paiement')
        ACTIVE = ('ACTIVE', 'Actif')
        COMPLETED = ('COMPLETED', 'Termine')

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investments')
    tier = models.ForeignKey(InvestmentTier, on_delete=models.SET_NULL, null=True, blank=True)
    amount_invested = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Montant Investi")
    daily_rate_snapshot = models.DecimalField(max_digits=5, decimal_places=4, default=0.0, verbose_name="Taux journalier fige")
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)

    class Meta:
        verbose_name = "Souscription"
        verbose_name_plural = "Souscriptions"

    @property
    def days_passed(self):
        from django.utils import timezone
        return (timezone.now() - self.start_date).days

    @property
    def accumulated_gains(self):
        # Utilisation de la nouvelle formule des interets composes
        rate = float(self.daily_rate_snapshot) if self.daily_rate_snapshot else (float(self.tier.daily_rate) if self.tier else 0)
        capital = float(self.amount_invested)
        days = self.days_passed
        # Capital x (1 + Taux_Journalier)^Jours - Capital
        gain_total = capital * ((1 + rate) ** days)
        return gain_total - capital

    def __str__(self):
        tier_name = self.tier.name if self.tier else "Inconnu"
        return f"{self.user} - Categorie {tier_name} ({self.amount_invested})"

    @property
    def is_payment_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        PAY_INVEST = ('PAY_INVEST', 'Achat de Palier (Checkout)')
        BOOSTER = ('BOOSTER', 'Achat de Booster')
        WITHDRAWAL = ('WITHDRAWAL', 'Retrait')
        ROI = ('ROI', 'Gains Rendement')
        BONUS = ('BONUS', 'Bonus Parrainage')

    class Status(models.TextChoices):
        PENDING = ('PENDING', 'En attente')
        SUCCESS = ('SUCCESS', 'Valide')
        FAILED = ('FAILED', 'Echoue')

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    tx_type = models.CharField(max_length=15, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    provider = models.CharField(max_length=255, blank=True, help_text="CinetPay, Orange Money, Crypto Wallet...")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    tx_reference = models.CharField(max_length=100, unique=True, blank=True, null=True)
    related_investment = models.ForeignKey('Investment', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_tx')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"

    def __str__(self):
        return f"{self.get_tx_type_display()} - {self.amount} XOF - {self.user}"


class Booster(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nom du Booster (Ex: Speed Boost x1.5)")
    multiplier = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Multiplicateur (Ex: 1.5)")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Prix d'achat (XOF)")
    duration_days = models.IntegerField(default=1, verbose_name="Duree (Jours)")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="Ex: ph-rocket")

    class Meta:
        verbose_name = "Booster"
        verbose_name_plural = "Boosters"

    def __str__(self):
        return f"{self.name} (x{self.multiplier})"


class UserBooster(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='boosters')
    booster = models.ForeignKey(Booster, on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Booster Utilisateur"
        verbose_name_plural = "Boosters Utilisateur"

    def __str__(self):
        return f"{self.user} - {self.booster.name}"


class SystemSettings(models.Model):
    maintenance_mode = models.BooleanField(default=False, verbose_name="Mode Maintenance")
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Frais d'inscription (XOF)")
    default_roi_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.5, verbose_name="Taux de rendement global par defaut (%)")
    sponsor_bonus_level_1 = models.DecimalField(max_digits=5, decimal_places=2, default=5.0, verbose_name="Bonus Parrainage Niveau 1 (%)")
    sponsor_bonus_level_2 = models.DecimalField(max_digits=5, decimal_places=2, default=2.0, verbose_name="Bonus Parrainage Niveau 2 (%)")
    min_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=5000, verbose_name="Retrait Minimum (XOF)")

    def __str__(self):
        return "Parametres Generaux de la Plateforme"


class PaymentConfig(models.Model):
    provider_name = models.CharField(max_length=50, unique=True, verbose_name="Nom du Fournisseur (ex: CinetPay)")
    is_active = models.BooleanField(default=True, verbose_name="Activer ce moyen de paiement")
    api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Cle API Publique")
    secret_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Cle API Secrete / Token")
    environment = models.CharField(max_length=50, choices=[('TEST', 'Sandbox / Test'), ('PROD', 'Production')], default='TEST')
    webhook_url = models.URLField(blank=True, null=True, verbose_name="URL de Webhook")

    def __str__(self):
        return f"Configuration {self.provider_name} ({self.environment})"


class AuditLog(models.Model):
    INFO = 'INFO'
    WARNING = 'WARNING'
    CRITICAL = 'CRITICAL'
    SEVERITY_CHOICES = [
        (INFO, 'Information'),
        (WARNING, 'Alerte'),
        (CRITICAL, 'Critique'),
    ]
    admin_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=255, verbose_name="Action effectuee")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Adresse IP")
    severity = models.CharField(max_length=15, choices=SEVERITY_CHOICES, default=INFO)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.severity}] {self.action} par {self.admin_user} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


# --- SIGNAUX ---
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=InvestmentTier)
def notify_new_tier(sender, instance, created, **kwargs):
    if created:
        from users.models import Notification
        from django.contrib.auth import get_user_model
        UserClass = get_user_model()
        users = UserClass.objects.all()
        notifications = [
            Notification(
                user=user,
                title="Nouvelle categorie disponible",
                message=(
                    f"Decouvrez la categorie '{instance.name}' et ses conditions "
                    "d'investissement."
                )
            ) for user in users
        ]
        Notification.objects.bulk_create(notifications)
