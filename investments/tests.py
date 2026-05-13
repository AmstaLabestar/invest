from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.models import Notification

from .models import Booster, Investment, InvestmentTier, SystemSettings, Transaction
from .services import WalletService


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
        self.assertEqual(tx.status, Transaction.Status.PENDING)
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
            status=Investment.Status.PENDING,
        )
        tx = Transaction.objects.create(
            user=self.client_user,
            tx_type=Transaction.TransactionType.PAY_INVEST,
            amount=Decimal("10000"),
            status=Transaction.Status.PENDING,
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

        self.assertEqual(tx.status, Transaction.Status.SUCCESS)
        self.assertEqual(investment.status, Investment.Status.ACTIVE)
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
            status=Transaction.Status.PENDING,
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

        self.assertEqual(tx.status, Transaction.Status.FAILED)
        self.assertEqual(self.client_user.balance, Decimal("10000"))

    def test_manager_rejects_pay_invest_and_deletes_pending_investment(self):
        investment = Investment.objects.create(
            user=self.client_user,
            tier=self.tier,
            amount_invested=Decimal("15000"),
            daily_rate_snapshot=Decimal("0.0120"),
            status=Investment.Status.PENDING,
        )
        tx = Transaction.objects.create(
            user=self.client_user,
            tx_type=Transaction.TransactionType.PAY_INVEST,
            amount=Decimal("15000"),
            status=Transaction.Status.PENDING,
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

        self.assertEqual(tx.status, Transaction.Status.FAILED)
        self.assertFalse(Investment.objects.filter(id=investment.id).exists())
        self.assertIsNone(tx.related_investment)


class WalletServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="wallet-user",
            password="TestPass123!",
            phone_number="+22670000015",
            balance=Decimal("8000"),
        )
        self.tier = InvestmentTier.objects.create(
            name="Foundation",
            level=2,
            min_amount=Decimal("5000"),
            max_amount=Decimal("50000"),
            daily_rate=Decimal("0.0150"),
            monthly_rate=Decimal("0.4500"),
            cycle_days=45,
        )
        Investment.objects.create(
            user=self.user,
            tier=self.tier,
            amount_invested=Decimal("12000"),
            daily_rate_snapshot=Decimal("0.0150"),
            status=Investment.Status.ACTIVE,
        )
        Transaction.objects.create(
            user=self.user,
            tx_type=Transaction.TransactionType.WITHDRAWAL,
            amount=Decimal("2000"),
            status=Transaction.Status.PENDING,
            tx_reference='WALLET-PENDING-001',
        )
        Transaction.objects.create(
            user=self.user,
            tx_type=Transaction.TransactionType.ROI,
            amount=Decimal("1500"),
            status=Transaction.Status.SUCCESS,
            tx_reference='WALLET-ROI-001',
        )
        Transaction.objects.create(
            user=self.user,
            tx_type=Transaction.TransactionType.BONUS,
            amount=Decimal("500"),
            status=Transaction.Status.SUCCESS,
            tx_reference='WALLET-BONUS-001',
        )
        Transaction.objects.create(
            user=self.user,
            tx_type=Transaction.TransactionType.ROI,
            amount=Decimal("999"),
            status=Transaction.Status.FAILED,
            tx_reference='WALLET-FAILED-001',
        )

    def test_wallet_service_exposes_current_balance_breakdown(self):
        self.assertEqual(WalletService.get_available_balance(self.user), Decimal("8000"))
        self.assertEqual(WalletService.get_reserved_balance(self.user), Decimal("2000"))
        self.assertEqual(WalletService.get_total_balance(self.user), Decimal("10000"))
        self.assertEqual(WalletService.get_withdrawable_amount(self.user), Decimal("8000"))

    def test_wallet_service_aggregates_invested_capital_and_realized_gains(self):
        self.assertEqual(WalletService.get_total_invested_capital(self.user), Decimal("12000"))
        self.assertEqual(WalletService.get_realized_gains(self.user), Decimal("2000"))


class CategoryCatalogTests(TestCase):
    def setUp(self):
        call_command('seed_data', stdout=StringIO())

    def test_seed_data_creates_catalog_matching_cahier_thresholds(self):
        expected_catalog = [
            ('Standard', Decimal('5000'), Decimal('9999')),
            ('Bronze', Decimal('10000'), Decimal('24999')),
            ('Argent', Decimal('25000'), Decimal('49999')),
            ('Or', Decimal('50000'), Decimal('74999')),
            ('Diamant', Decimal('75000'), Decimal('149999')),
            ('VIP', Decimal('150000'), Decimal('1249999')),
            ('Partenaire 1', Decimal('1250000'), Decimal('3499999')),
            ('Partenaire 2', Decimal('3500000'), None),
        ]

        tiers = list(
            InvestmentTier.objects.order_by('level').values_list(
                'name',
                'min_amount',
                'max_amount',
            )
        )

        self.assertEqual(tiers, expected_catalog)
        self.assertEqual(InvestmentTier.objects.count(), 8)
        self.assertFalse(InvestmentTier.objects.filter(name='Platine').exists())

    def test_amount_lookup_resolves_to_expected_category(self):
        expected_mapping = {
            Decimal('5000'): 'Standard',
            Decimal('10000'): 'Bronze',
            Decimal('25000'): 'Argent',
            Decimal('50000'): 'Or',
            Decimal('75000'): 'Diamant',
            Decimal('150000'): 'VIP',
            Decimal('1250000'): 'Partenaire 1',
            Decimal('3500000'): 'Partenaire 2',
        }

        for amount, expected_name in expected_mapping.items():
            with self.subTest(amount=amount):
                tier = InvestmentTier.get_tier_by_amount(amount)
                self.assertIsNotNone(tier)
                self.assertEqual(tier.name, expected_name)
