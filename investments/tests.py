from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Booster, Transaction


User = get_user_model()


class TransactionTypeTests(TestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.user = User.objects.create_user(
            username="client",
            password=self.password,
            phone_number="+22670000010",
            balance=10000,
        )
        self.booster = Booster.objects.create(
            name="Booster Bronze",
            multiplier="1.50",
            price="2000",
            duration_days=7,
            is_active=True,
        )

    def test_booster_purchase_creates_booster_transaction_type(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('booster'),
            {'booster_id': self.booster.id},
        )

        self.assertRedirects(response, reverse('booster'))
        tx = Transaction.objects.get(user=self.user, tx_reference__startswith='BOOST-')
        self.assertEqual(tx.tx_type, Transaction.TransactionType.BOOSTER)

    def test_supported_transaction_types_are_canonical(self):
        self.assertEqual(
            set(Transaction.TransactionType.values),
            {'PAY_INVEST', 'BOOSTER', 'WITHDRAWAL', 'ROI', 'BONUS'},
        )
