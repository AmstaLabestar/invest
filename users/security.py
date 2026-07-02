import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import OTPChallenge


class OTPService:
    CODE_TTL_MINUTES = 10

    @staticmethod
    def generate_code():
        return f"{secrets.randbelow(1_000_000):06d}"

    @classmethod
    def create_challenge(cls, user, purpose):
        code = cls.generate_code()
        challenge = OTPChallenge(
            user=user,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=cls.CODE_TTL_MINUTES),
        )
        challenge.set_code(code)
        challenge.save()
        cls.send_code(user, code)
        return challenge

    @staticmethod
    def send_code(user, code):
        if not user.email:
            raise ValueError("User email is required for OTP")

        send_mail(
            subject="Code de securite NOVARIS",
            message=f"Votre code de securite est : {code}. Il expire dans 10 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

    @staticmethod
    def verify_challenge(challenge, code):
        return challenge.verify(code)
