from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.models import Notification

from .models import Booster, SystemSettings, Transaction


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


class WithdrawalRequestTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="withdraw-user",
            password="TestPass123!",
            phone_number="+22670000011",
            balance=Decimal("10000"),
        )
        SystemSettings.objects.create(min_withdrawal=Decimal("5000"))

    def test_withdraw_request_creates_pending_transaction_and_reserves_balance(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('withdraw_request'),
            {
                'amount': '6000',
                'provider': 'Orange Money',
                'phone': '+22670000011',
            },
            HTTP_REFERER=reverse('booster'),
        )

        self.assertRedirects(response, reverse('booster'))

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("4000"))

        tx = Transaction.objects.get(user=self.user, tx_reference__startswith='RET-')
        self.assertEqual(tx.tx_type, Transaction.TransactionType.WITHDRAWAL)
        self.assertEqual(tx.status, 'PENDING')
        self.assertEqual(tx.amount, Decimal("6000"))
        self.assertEqual(tx.provider, 'Orange Money (+22670000011)')
        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                title__icontains='retrait',
            ).exists()
        )

    def test_withdraw_request_with_insufficient_balance_creates_no_transaction(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('withdraw_request'),
            {
                'amount': '15000',
                'provider': 'Orange Money',
                'phone': '+22670000011',
            },
            HTTP_REFERER=reverse('booster'),
        )

        self.assertRedirects(response, reverse('booster'))

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("10000"))
        self.assertFalse(
            Transaction.objects.filter(
                user=self.user,
                tx_type=Transaction.TransactionType.WITHDRAWAL,
            ).exists()
        )
