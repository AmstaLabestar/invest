from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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
