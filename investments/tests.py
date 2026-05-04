from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.models import Notification

from .models import Booster, Investment, InvestmentTier, SystemSettings, Transaction


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


class ManagerTransactionFlowTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_superuser(
            username="superadmin",
            password="AdminPass123!",
            email="admin@example.com",
            phone_number="+22670000012",
        )
        self.sponsor = User.objects.create_user(
            username="sponsor",
            password="TestPass123!",
            phone_number="+22670000013",
            points=0,
        )
        self.client_user = User.objects.create_user(
            username="investor",
            password="TestPass123!",
            phone_number="+22670000014",
            sponsor=self.sponsor,
            balance=Decimal("4000"),
        )
        self.tier = InvestmentTier.objects.create(
            name="Starter",
            level=1,
            min_amount=Decimal("10000"),
            max_amount=Decimal("50000"),
            daily_rate=Decimal("0.0120"),
            monthly_rate=Decimal("0.3600"),
            cycle_days=30,
        )

    def test_manager_approval_activates_investment_and_rewards_sponsor(self):
        investment = Investment.objects.create(
            user=self.client_user,
            tier=self.tier,
            amount_invested=Decimal("10000"),
            daily_rate_snapshot=Decimal("0.0120"),
            status='PENDING',
        )
        tx = Transaction.objects.create(
            user=self.client_user,
            tx_type=Transaction.TransactionType.PAY_INVEST,
            amount=Decimal("10000"),
            status='PENDING',
            tx_reference='INVEST-APPROVE-001',
            related_investment=investment,
        )

        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('process_transaction', args=[tx.id, 'approve']),
            HTTP_REFERER=reverse('manager_dashboard'),
        )

        self.assertRedirects(response, reverse('manager_dashboard'))

        tx.refresh_from_db()
        investment.refresh_from_db()
        self.sponsor.refresh_from_db()

        self.assertEqual(tx.status, 'SUCCESS')
        self.assertEqual(investment.status, 'ACTIVE')
        self.assertEqual(self.sponsor.points, 20)
        self.assertTrue(
            Notification.objects.filter(
                user=self.sponsor,
                title__icontains='Parrainage',
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                title__icontains='Palier',
            ).exists()
        )

    def test_manager_rejects_withdrawal_and_refunds_reserved_balance(self):
        tx = Transaction.objects.create(
            user=self.client_user,
            tx_type=Transaction.TransactionType.WITHDRAWAL,
            amount=Decimal("6000"),
            status='PENDING',
            tx_reference='WITHDRAW-REJECT-001',
            provider='Orange Money (+22670000014)',
        )

        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('process_transaction', args=[tx.id, 'reject']),
            HTTP_REFERER=reverse('manager_dashboard'),
        )

        self.assertRedirects(response, reverse('manager_dashboard'))

        tx.refresh_from_db()
        self.client_user.refresh_from_db()

        self.assertEqual(tx.status, 'FAILED')
        self.assertEqual(self.client_user.balance, Decimal("10000"))

    def test_manager_rejects_pay_invest_and_deletes_pending_investment(self):
        investment = Investment.objects.create(
            user=self.client_user,
            tier=self.tier,
            amount_invested=Decimal("15000"),
            daily_rate_snapshot=Decimal("0.0120"),
            status='PENDING',
        )
        tx = Transaction.objects.create(
            user=self.client_user,
            tx_type=Transaction.TransactionType.PAY_INVEST,
            amount=Decimal("15000"),
            status='PENDING',
            tx_reference='INVEST-REJECT-001',
            related_investment=investment,
        )

        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('process_transaction', args=[tx.id, 'reject']),
            HTTP_REFERER=reverse('manager_dashboard'),
        )

        self.assertRedirects(response, reverse('manager_dashboard'))

        tx.refresh_from_db()

        self.assertEqual(tx.status, 'FAILED')
        self.assertFalse(Investment.objects.filter(id=investment.id).exists())
        self.assertIsNone(tx.related_investment)
