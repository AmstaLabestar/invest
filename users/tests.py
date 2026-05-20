from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from .models import OTPChallenge


User = get_user_model()


class RoleAccessTests(TestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.manager = User.objects.create_user(
            username="manager",
            password=self.password,
            phone_number="+22670000001",
            is_platform_admin=True,
        )
        self.standard_user = User.objects.create_user(
            username="client",
            password=self.password,
            phone_number="+22670000002",
        )
        self.superadmin = User.objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password=self.password,
            phone_number="+22670000003",
        )

    def test_manager_can_access_manager_dashboard(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('manager_dashboard'))

        self.assertEqual(response.status_code, 200)

    def test_standard_user_is_redirected_from_manager_dashboard(self):
        self.client.force_login(self.standard_user)

        response = self.client.get(reverse('manager_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(f"{reverse('login')}?next="))

    def test_manager_login_redirects_to_manager_dashboard(self):
        response = self.client.post(
            reverse('login'),
            {'username': self.manager.username, 'password': self.password},
        )

        self.assertRedirects(response, '/manager/')

    def test_superadmin_login_redirects_to_superadmin_dashboard(self):
        response = self.client.post(
            reverse('login'),
            {'username': self.superadmin.username, 'password': self.password},
        )

        self.assertRedirects(response, '/superadmin/')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_otp_enabled_user_must_confirm_code_after_password(self):
        self.standard_user.email = "client@example.com"
        self.standard_user.otp_enabled = True
        self.standard_user.save(update_fields=['email', 'otp_enabled'])

        response = self.client.post(
            reverse('login'),
            {'username': self.standard_user.username, 'password': self.password},
        )

        self.assertRedirects(response, reverse('otp_verify'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            OTPChallenge.objects.filter(
                user=self.standard_user,
                purpose=OTPChallenge.Purpose.LOGIN,
            ).exists()
        )
