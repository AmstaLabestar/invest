from decimal import Decimal
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from users.models import Notification

from .models import Booster, Investment, InvestmentTier, SystemSettings, Transaction, UserBooster
from .services import CalculationService, WalletService, YieldRuleService
from .tasks import calculate_binary_bonus, calculate_daily_roi, process_referral_bonuses


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
        self.tier = InvestmentTier.objects.create(
            name="Bronze",
            level=2,
            min_amount=Decimal("10000"),
            max_amount=Decimal("24999"),
            daily_rate=Decimal("0.1000"),
            monthly_rate=Decimal("3.0000"),
            cycle_days=30,
        )
        self.investment = Investment.objects.create(
            user=self.user,
            tier=self.tier,
            amount_invested=Decimal("10000"),
            daily_rate_snapshot=Decimal("0.1000"),
            status=Investment.Status.ACTIVE,
            end_date=timezone.now() + timedelta(days=30),
        )
        Investment.objects.filter(id=self.investment.id).update(
            start_date=timezone.now() - timedelta(days=4)
        )

    def test_withdraw_request_creates_pending_transaction_and_reserves_balance(self):
        self.client.force_login(self.user)
        Transaction.objects.create(
            user=self.user,
            tx_type=Transaction.TransactionType.ROI,
            amount=Decimal("10000"),
            status=Transaction.Status.SUCCESS,
            tx_reference='WITHDRAW-ROI-001',
            provider='System Daily Yield',
        )

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
                'amount': '5000',
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

    def test_withdraw_request_is_blocked_for_three_days_after_purchase(self):
        Investment.objects.filter(id=self.investment.id).update(start_date=timezone.now() - timedelta(days=1))
        Transaction.objects.create(
            user=self.user,
            tx_type=Transaction.TransactionType.ROI,
            amount=Decimal("10000"),
            status=Transaction.Status.SUCCESS,
            tx_reference='WITHDRAW-ROI-LOCKED-001',
            provider='System Daily Yield',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('withdraw_request'),
            {
                'amount': '5000',
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

    def test_manager_approval_activates_investment_and_notifies_sponsor(self):
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
        self.assertEqual(self.sponsor.points, 0)
        self.assertTrue(
            Notification.objects.filter(
                user=self.sponsor,
                title__icontains='parrainage',
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                title__icontains='Souscription',
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
        self.investment = Investment.objects.create(
            user=self.user,
            tier=self.tier,
            amount_invested=Decimal("12000"),
            daily_rate_snapshot=Decimal("0.0150"),
            status=Investment.Status.ACTIVE,
            end_date=timezone.now() + timedelta(days=45),
        )
        Investment.objects.filter(id=self.investment.id).update(
            start_date=timezone.now() - timedelta(days=5)
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
        self.assertEqual(WalletService.get_withdrawable_amount(self.user), Decimal("0"))
        self.assertTrue(WalletService.is_withdrawal_unlocked(self.user))

    def test_wallet_service_aggregates_invested_capital_and_realized_gains(self):
        self.assertEqual(WalletService.get_total_invested_capital(self.user), Decimal("12000"))
        self.assertEqual(WalletService.get_realized_gains(self.user), Decimal("2000"))
        self.assertEqual(WalletService.get_consumed_gains(self.user), Decimal("2000"))

    def test_wallet_service_limits_withdrawable_amount_to_realized_gains(self):
        eligible_user = User.objects.create_user(
            username="wallet-eligible",
            password="TestPass123!",
            phone_number="+22670000018",
            balance=Decimal("5000"),
        )
        eligible_tier = InvestmentTier.objects.create(
            name="Wallet Bronze",
            level=9,
            min_amount=Decimal("10000"),
            max_amount=Decimal("19999"),
            daily_rate=Decimal("0.1000"),
            monthly_rate=Decimal("3.0000"),
            cycle_days=30,
        )
        eligible_investment = Investment.objects.create(
            user=eligible_user,
            tier=eligible_tier,
            amount_invested=Decimal("10000"),
            daily_rate_snapshot=Decimal("0.1000"),
            status=Investment.Status.ACTIVE,
            end_date=timezone.now() + timedelta(days=30),
        )
        Investment.objects.filter(id=eligible_investment.id).update(
            start_date=timezone.now() - timedelta(days=4)
        )
        Transaction.objects.create(
            user=eligible_user,
            tx_type=Transaction.TransactionType.ROI,
            amount=Decimal("2500"),
            status=Transaction.Status.SUCCESS,
            tx_reference='WALLET-ELIGIBLE-ROI-001',
        )

        self.assertEqual(WalletService.get_withdrawable_amount(eligible_user), Decimal("2500"))

    def test_wallet_service_blocks_withdrawal_during_three_day_lock(self):
        locked_user = User.objects.create_user(
            username="wallet-locked",
            password="TestPass123!",
            phone_number="+22670000019",
            balance=Decimal("5000"),
        )
        locked_investment = Investment.objects.create(
            user=locked_user,
            tier=self.tier,
            amount_invested=Decimal("12000"),
            daily_rate_snapshot=Decimal("0.0150"),
            status=Investment.Status.ACTIVE,
            end_date=timezone.now() + timedelta(days=45),
        )
        Investment.objects.filter(id=locked_investment.id).update(
            start_date=timezone.now() - timedelta(days=1)
        )
        Transaction.objects.create(
            user=locked_user,
            tx_type=Transaction.TransactionType.ROI,
            amount=Decimal("3000"),
            status=Transaction.Status.SUCCESS,
            tx_reference='WALLET-LOCKED-ROI-001',
        )

        self.assertFalse(WalletService.is_withdrawal_unlocked(locked_user))
        self.assertEqual(WalletService.get_withdrawable_amount(locked_user), Decimal("0"))


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


class YieldRuleTests(TestCase):
    def setUp(self):
        self.or_tier = InvestmentTier.objects.create(
            name="Or",
            level=4,
            min_amount=Decimal("50000"),
            max_amount=Decimal("74999"),
            daily_rate=Decimal("0.1300"),
            monthly_rate=Decimal("3.9000"),
            cycle_days=30,
        )
        self.partner_tier = InvestmentTier.objects.create(
            name="Partenaire 1",
            level=7,
            min_amount=Decimal("1250000"),
            max_amount=Decimal("3499999"),
            daily_rate=Decimal("0.1500"),
            monthly_rate=Decimal("4.5000"),
            cycle_days=30,
        )

    def test_simulation_uses_linear_daily_gains_for_standard_categories(self):
        result = CalculationService.simulate_investment(Decimal("50000"), self.or_tier.id)

        self.assertEqual(result['taux_journalier_pourcent'], 13.0)
        self.assertEqual(result['gain_net'], 195000.0)
        self.assertEqual(result['gain_total'], 245000.0)
        self.assertEqual(result['bonus_partenaire_total'], 0.0)

    def test_simulation_includes_fixed_partner_bonus(self):
        result = CalculationService.simulate_investment(Decimal("1250000"), self.partner_tier.id)

        self.assertEqual(result['taux_journalier_pourcent'], 15.0)
        self.assertEqual(result['bonus_partenaire_total'], 100000.0)
        self.assertEqual(result['gain_net'], 5725000.0)
        self.assertEqual(result['gain_total'], 6975000.0)

    def test_daily_roi_task_is_idempotent_and_pays_partner_bonus_by_checkpoint(self):
        user = User.objects.create_user(
            username="partner-user",
            password="TestPass123!",
            phone_number="+22670000016",
            balance=Decimal("0"),
        )
        investment = Investment.objects.create(
            user=user,
            tier=self.partner_tier,
            amount_invested=Decimal("1250000"),
            daily_rate_snapshot=Decimal("0.1500"),
            status=Investment.Status.ACTIVE,
            end_date=timezone.now() + timedelta(days=30),
        )
        Investment.objects.filter(id=investment.id).update(
            start_date=timezone.now() - timedelta(days=16)
        )
        investment.refresh_from_db()

        calculate_daily_roi()
        user.refresh_from_db()

        self.assertEqual(user.balance, Decimal("237500.00"))
        self.assertEqual(
            Transaction.objects.filter(
                user=user,
                tx_type=Transaction.TransactionType.ROI,
            ).count(),
            1,
        )
        self.assertEqual(
            Transaction.objects.filter(
                user=user,
                tx_type=Transaction.TransactionType.BONUS,
                provider__startswith='Partner Bonus Day',
            ).count(),
            1,
        )

        calculate_daily_roi()
        user.refresh_from_db()

        self.assertEqual(user.balance, Decimal("237500.00"))
        self.assertEqual(
            Transaction.objects.filter(
                user=user,
                tx_type=Transaction.TransactionType.ROI,
            ).count(),
            1,
        )
        self.assertEqual(
            Transaction.objects.filter(
                user=user,
                tx_type=Transaction.TransactionType.BONUS,
                provider__startswith='Partner Bonus Day',
            ).count(),
            1,
        )

    def test_calculate_daily_returns_reports_linear_gains(self):
        user = User.objects.create_user(
            username="yield-user",
            password="TestPass123!",
            phone_number="+22670000017",
            balance=Decimal("0"),
        )
        investment = Investment.objects.create(
            user=user,
            tier=self.or_tier,
            amount_invested=Decimal("50000"),
            daily_rate_snapshot=Decimal("0.1300"),
            status=Investment.Status.ACTIVE,
            end_date=timezone.now() + timedelta(days=30),
        )
        Investment.objects.filter(id=investment.id).update(
            start_date=timezone.now() - timedelta(days=10)
        )
        investment.refresh_from_db()

        result = CalculationService.calculate_daily_returns(investment)

        self.assertEqual(result['jours_ecoules'], 10)
        self.assertEqual(result['bonus_partenaire_total'], 0.0)
        self.assertEqual(result['gains'], 65000.0)
        self.assertEqual(
            YieldRuleService.calculate_cumulative_gains(investment),
            Decimal("65000.00"),
        )


class ReferralModelTests(TestCase):
    def setUp(self):
        self.sponsor = User.objects.create_user(
            username="ref-sponsor",
            password="TestPass123!",
            phone_number="+22670000020",
            balance=Decimal("0"),
            points=0,
        )
        self.referred_user = User.objects.create_user(
            username="ref-user",
            password="TestPass123!",
            phone_number="+22670000021",
            sponsor=self.sponsor,
            balance=Decimal("0"),
        )
        self.standard_tier = InvestmentTier.objects.create(
            name="Bronze",
            level=20,
            min_amount=Decimal("10000"),
            max_amount=Decimal("24999"),
            daily_rate=Decimal("0.1000"),
            monthly_rate=Decimal("3.0000"),
            cycle_days=30,
        )
        self.partner_tier = InvestmentTier.objects.create(
            name="Partenaire 1",
            level=21,
            min_amount=Decimal("1250000"),
            max_amount=Decimal("3499999"),
            daily_rate=Decimal("0.1500"),
            monthly_rate=Decimal("4.5000"),
            cycle_days=30,
        )

    def test_process_referral_bonuses_credits_standard_referral_after_24_hours(self):
        investment = Investment.objects.create(
            user=self.referred_user,
            tier=self.standard_tier,
            amount_invested=Decimal("10000"),
            daily_rate_snapshot=Decimal("0.1000"),
            status=Investment.Status.ACTIVE,
        )
        payment_tx = Transaction.objects.create(
            user=self.referred_user,
            tx_type=Transaction.TransactionType.PAY_INVEST,
            amount=Decimal("10000"),
            status=Transaction.Status.SUCCESS,
            tx_reference='REF-STD-PAY-001',
            related_investment=investment,
        )
        Transaction.objects.filter(id=payment_tx.id).update(
            created_at=timezone.now() - timedelta(hours=25)
        )

        process_referral_bonuses()
        self.sponsor.refresh_from_db()

        self.assertEqual(self.sponsor.balance, Decimal("1000.00"))
        self.assertEqual(self.sponsor.points, 0)
        self.assertTrue(
            Transaction.objects.filter(
                user=self.sponsor,
                tx_reference=f'REF-BONUS-{payment_tx.id}',
                amount=Decimal("1000.00"),
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.sponsor,
                title__icontains='parrainage',
            ).exists()
        )

    def test_process_referral_bonuses_uses_partner_rate_for_partner_categories(self):
        investment = Investment.objects.create(
            user=self.referred_user,
            tier=self.partner_tier,
            amount_invested=Decimal("1250000"),
            daily_rate_snapshot=Decimal("0.1500"),
            status=Investment.Status.ACTIVE,
        )
        payment_tx = Transaction.objects.create(
            user=self.referred_user,
            tx_type=Transaction.TransactionType.PAY_INVEST,
            amount=Decimal("1250000"),
            status=Transaction.Status.SUCCESS,
            tx_reference='REF-PARTNER-PAY-001',
            related_investment=investment,
        )
        Transaction.objects.filter(id=payment_tx.id).update(
            created_at=timezone.now() - timedelta(hours=25)
        )

        process_referral_bonuses()
        self.sponsor.refresh_from_db()

        self.assertEqual(self.sponsor.balance, Decimal("187500.00"))
        self.assertTrue(
            Transaction.objects.filter(
                user=self.sponsor,
                tx_reference=f'REF-BONUS-{payment_tx.id}',
                amount=Decimal("187500.00"),
            ).exists()
        )

    def test_process_referral_bonuses_is_idempotent_and_waits_24_hours(self):
        investment = Investment.objects.create(
            user=self.referred_user,
            tier=self.standard_tier,
            amount_invested=Decimal("10000"),
            daily_rate_snapshot=Decimal("0.1000"),
            status=Investment.Status.ACTIVE,
        )
        payment_tx = Transaction.objects.create(
            user=self.referred_user,
            tx_type=Transaction.TransactionType.PAY_INVEST,
            amount=Decimal("10000"),
            status=Transaction.Status.SUCCESS,
            tx_reference='REF-IDEMPOTENT-001',
            related_investment=investment,
        )

        process_referral_bonuses()
        self.sponsor.refresh_from_db()
        self.assertEqual(self.sponsor.balance, Decimal("0"))

        Transaction.objects.filter(id=payment_tx.id).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        process_referral_bonuses()
        process_referral_bonuses()
        self.sponsor.refresh_from_db()

        self.assertEqual(self.sponsor.balance, Decimal("1000.00"))
        self.assertEqual(
            Transaction.objects.filter(
                user=self.sponsor,
                tx_reference=f'REF-BONUS-{payment_tx.id}',
            ).count(),
            1,
        )

    def test_legacy_binary_bonus_task_is_neutralized(self):
        self.sponsor.binary_position = 'LEFT'
        self.sponsor.save(update_fields=['binary_position'])

        result = calculate_binary_bonus()

        self.sponsor.refresh_from_db()
        self.assertEqual(self.sponsor.balance, Decimal("0"))
        self.assertIn('desactive', result)


class ClientJourneySmokeTests(TestCase):
    def setUp(self):
        self.password = "ClientPass123!"
        self.user = User.objects.create_user(
            username="mobile-client",
            password=self.password,
            first_name="Awa",
            last_name="Traore",
            email="awa@example.com",
            phone_number="+22670000030",
            balance=Decimal("30000"),
            points=25,
        )
        self.tier = InvestmentTier.objects.create(
            name="Bronze",
            level=2,
            min_amount=Decimal("10000"),
            max_amount=Decimal("24999"),
            daily_rate=Decimal("0.1000"),
            monthly_rate=Decimal("3.0000"),
            cycle_days=30,
            badge="B",
            is_active=True,
        )
        self.booster = Booster.objects.create(
            name="Boost Start",
            multiplier=Decimal("1.50"),
            price=Decimal("2000"),
            duration_days=7,
            is_active=True,
        )
        self.investment = Investment.objects.create(
            user=self.user,
            tier=self.tier,
            amount_invested=Decimal("10000"),
            daily_rate_snapshot=Decimal("0.1000"),
            status=Investment.Status.ACTIVE,
            end_date=timezone.now() + timedelta(days=30),
        )
        Investment.objects.filter(id=self.investment.id).update(
            start_date=timezone.now() - timedelta(days=5)
        )
        Transaction.objects.create(
            user=self.user,
            tx_type=Transaction.TransactionType.ROI,
            amount=Decimal("2500"),
            status=Transaction.Status.SUCCESS,
            tx_reference="CLIENT-ROI-001",
            provider="System Daily Yield",
        )
        Transaction.objects.create(
            user=self.user,
            tx_type=Transaction.TransactionType.BONUS,
            amount=Decimal("1000"),
            status=Transaction.Status.SUCCESS,
            tx_reference="CLIENT-BONUS-001",
            provider="Referral Bonus",
        )
        Notification.objects.create(
            user=self.user,
            title="Bonus parrainage",
            message="Votre bonus de parrainage est disponible.",
        )

    def test_public_auth_pages_render(self):
        for route_name in ("login", "register"):
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_register_flow_creates_client_and_opens_home(self):
        response = self.client.post(
            reverse("register"),
            {
                "first_name": "Fatou",
                "last_name": "Ouedraogo",
                "username": "new-mobile-client",
                "phone_number": "70000031",
                "password1": "NewClientPass123!",
                "password2": "NewClientPass123!",
            },
        )

        self.assertRedirects(response, reverse("home"))
        self.assertTrue(User.objects.filter(username="new-mobile-client").exists())

    def test_authenticated_client_pages_render_with_real_data(self):
        self.client.force_login(self.user)
        route_names = [
            "home",
            "trade",
            "booster",
            "profile",
            "notifications",
            "settings_history",
            "settings_info",
            "settings_password",
            "settings_points",
            "settings_support",
            "settings_theme",
        ]

        for route_name in route_names:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_trade_post_creates_pending_payment_flow(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("trade"),
            {
                "tier_id": self.tier.id,
                "amount": "10000",
                "provider": "Orange Money",
                "phone": "70000030",
            },
        )

        self.assertRedirects(response, reverse("trade"))
        tx = Transaction.objects.get(tx_reference__startswith="PAY-", user=self.user)
        self.assertEqual(tx.tx_type, Transaction.TransactionType.PAY_INVEST)
        self.assertEqual(tx.status, Transaction.Status.PENDING)
        self.assertEqual(tx.related_investment.status, Investment.Status.PENDING)

    def test_booster_purchase_keeps_client_flow_renderable(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("booster"),
            {"booster_id": self.booster.id},
        )

        self.assertRedirects(response, reverse("booster"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("28000"))
        self.assertTrue(UserBooster.objects.filter(user=self.user, booster=self.booster).exists())

        follow_up = self.client.get(reverse("booster"))
        self.assertEqual(follow_up.status_code, 200)
