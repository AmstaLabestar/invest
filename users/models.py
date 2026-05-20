from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=15, unique=True, verbose_name="Numero de telephone")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Solde total")
    points = models.IntegerField(default=0, verbose_name="Points de fidelite")
    is_platform_admin = models.BooleanField(default=False, verbose_name="Admin plateforme")
    otp_enabled = models.BooleanField(default=False, verbose_name="OTP actif")
    sponsor = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals', verbose_name="Parrain")

    @property
    def unread_notifications_count(self):
        return self.notifications.filter(is_read=False).count()

    @property
    def referral_code(self):
        return self.username

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"


class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif: {self.title} pour {self.user.username}"


class OTPChallenge(models.Model):
    class Purpose(models.TextChoices):
        LOGIN = ('LOGIN', 'Connexion')
        ENABLE = ('ENABLE', 'Activation OTP')

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='otp_challenges')
    purpose = models.CharField(max_length=15, choices=Purpose.choices)
    code_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    def set_code(self, code):
        self.code_hash = make_password(code)

    def verify(self, code):
        if self.is_used or self.is_expired or self.attempts >= 5:
            return False
        self.attempts += 1
        if check_password(code, self.code_hash):
            self.used_at = timezone.now()
            self.save(update_fields=['attempts', 'used_at'])
            return True
        self.save(update_fields=['attempts'])
        return False
