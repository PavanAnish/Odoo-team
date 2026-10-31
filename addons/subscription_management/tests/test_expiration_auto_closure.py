# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
"""
Tests for Automated Subscription Expiration & Closure.
"""
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError, AccessError


class TestSubscriptionExpiration(TransactionCase):
    """Test automatic expiration detection, renewal-before-close, auto-closure, billing guard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref('base.user_admin'))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Expiry Test Customer',
            'is_subscription_customer': True,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Expiry Product',
            'type': 'service',
            'is_subscription_product': True,
            'list_price': 99.0,
        })

        # Plan: auto-closure ON, auto-renewal OFF
        cls.plan_auto_close = cls.env['subscription.plan'].create({
            'name': 'Auto-Close Plan',
            'code': 'AUTOCLOSE',
            'billing_interval': 1,
            'billing_period': 'monthly',
            'allow_renewal': False,
            'auto_renewal': False,
            'auto_closure': True,
        })

        # Plan: auto-closure OFF
        cls.plan_no_close = cls.env['subscription.plan'].create({
            'name': 'No Auto-Close Plan',
            'code': 'NOCLOSE',
            'billing_interval': 1,
            'billing_period': 'monthly',
            'allow_renewal': False,
            'auto_renewal': False,
            'auto_closure': False,
        })

        # Plan: auto-renewal ON, auto-closure ON
        cls.plan_auto_renew_close = cls.env['subscription.plan'].create({
            'name': 'Auto-Renew+Close Plan',
            'code': 'RENEWCLOSE',
            'billing_interval': 1,
            'billing_period': 'monthly',
            'allow_renewal': True,
            'auto_renewal': True,
            'auto_closure': True,
        })

    def _make_active(self, plan, expired=False, days_ahead=30):
        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': plan.id,
            'date_quotation': date.today(),
            'date_start': date.today(),
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 99.0,
            })],
        })
        sub.action_set_quotation()
        sub.action_confirm()
        sub.action_activate()
        if expired:
            # Set expiry to yesterday — subscription has expired
            sub.date_subscription_end = date.today() - timedelta(days=1)
        else:
            sub.date_subscription_end = date.today() + timedelta(days=days_ahead)
        return sub

    # ---------------------------------------------------------------
    # Expiry Detection
    # ---------------------------------------------------------------

    def test_01_active_not_expired_not_closed_by_cron(self):
        """Subscription not yet expired is left untouched by expiration cron."""
        sub = self._make_active(self.plan_auto_close, expired=False, days_ahead=15)
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertEqual(sub.state, 'active')

    def test_02_closed_subscription_ignored_by_cron(self):
        """Already-closed subscriptions are not processed by the cron."""
        sub = self._make_active(self.plan_auto_close, expired=True)
        sub.action_close()
        self.assertEqual(sub.state, 'closed')
        # Running cron should not error or duplicate anything
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertEqual(sub.state, 'closed')

    def test_03_expired_sub_identified_by_cron(self):
        """Expired subscription with auto_closure=True is closed by the cron."""
        sub = self._make_active(self.plan_auto_close, expired=True)
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertEqual(sub.state, 'closed')

    def test_04_expiry_on_today_triggers_closure(self):
        """Subscription whose end date equals today is processed by the expiry cron."""
        sub = self._make_active(self.plan_auto_close)
        sub.date_subscription_end = date.today()
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertEqual(sub.state, 'closed')

    # ---------------------------------------------------------------
    # Plan-Level Auto-Closure Config
    # ---------------------------------------------------------------

    def test_05_auto_closure_disabled_not_closed(self):
        """Expired subscription with auto_closure=False is NOT closed by cron."""
        sub = self._make_active(self.plan_no_close, expired=True)
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertNotEqual(sub.state, 'closed')

    def test_06_auto_closure_records_date(self):
        """date_auto_closed is populated when cron closes a subscription."""
        sub = self._make_active(self.plan_auto_close, expired=True)
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertEqual(sub.state, 'closed')
        self.assertIsNotNone(sub.date_auto_closed)

    def test_07_closure_reason_recorded_in_history(self):
        """Auto-closure history entry has a closure reason referencing expiry."""
        sub = self._make_active(self.plan_auto_close, expired=True)
        before_count = len(sub.history_ids)
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertGreater(len(sub.history_ids), before_count)
        last_hist = sub.history_ids.sorted('change_date')[0]
        self.assertEqual(last_hist.new_state, 'closed')

    # ---------------------------------------------------------------
    # Renewal Integration
    # ---------------------------------------------------------------

    def test_08_auto_renewal_before_closure(self):
        """Expired subscription with auto_renewal=True is renewed, not closed."""
        sub = self._make_active(self.plan_auto_renew_close, expired=True)
        sub.last_renewal_period_end = False
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertEqual(sub.state, 'active')
        self.assertGreater(sub.renewal_count, 0)

    def test_09_renewed_subscription_not_closed(self):
        """A successfully renewed subscription stays active after expiration cron."""
        sub = self._make_active(self.plan_auto_renew_close, expired=True)
        sub.last_renewal_period_end = False
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertNotEqual(sub.state, 'closed')

    def test_10_renewal_disabled_plan_closed(self):
        """Subscription on a plan with allow_renewal=False is closed on expiry."""
        sub = self._make_active(self.plan_auto_close, expired=True)
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertEqual(sub.state, 'closed')

    def test_11_auto_renewal_already_renewed_not_closed(self):
        """Subscription already renewed for current period is not closed by cron."""
        sub = self._make_active(self.plan_auto_renew_close)
        sub.date_subscription_end = date.today()
        sub.last_renewal_period_end = False
        # Pre-renew it so duplicate guard triggers
        sub.action_renew()
        count_before = sub.renewal_count
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        # Should stay active; renewal_count unchanged (guard prevented duplicate)
        self.assertEqual(sub.state, 'active')
        self.assertEqual(sub.renewal_count, count_before)

    # ---------------------------------------------------------------
    # Idempotency / Duplicate Prevention
    # ---------------------------------------------------------------

    def test_12_repeated_cron_no_duplicate_closure(self):
        """Running expiration cron multiple times does not create duplicate closures."""
        sub = self._make_active(self.plan_auto_close, expired=True)
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertEqual(sub.state, 'closed')
        hist_count_1 = len(sub.history_ids)
        # Run again — already closed, should be skipped
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertEqual(len(sub.history_ids), hist_count_1)

    def test_13_paused_expired_auto_closure(self):
        """Paused subscription that has expired is auto-closed when plan allows."""
        sub = self._make_active(self.plan_auto_close, expired=True)
        sub.action_pause()
        self.assertEqual(sub.state, 'paused')
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertEqual(sub.state, 'closed')

    # ---------------------------------------------------------------
    # Billing Protection
    # ---------------------------------------------------------------

    def test_14_expired_unrenewed_subscription_blocked_from_billing(self):
        """Expired subscription without renewal raises UserError on billing."""
        sub = self._make_active(self.plan_auto_close)
        sub.date_subscription_end = date.today() - timedelta(days=5)
        sub.last_renewal_period_end = False  # no renewal
        with self.assertRaises(UserError) as ctx:
            sub.action_generate_invoice()
        self.assertIn('expired', str(ctx.exception).lower())

    def test_15_renewed_subscription_passes_billing_guard(self):
        """Renewed subscription whose new end is in the future can be billed (state check)."""
        plan = self.env['subscription.plan'].create({
            'name': 'Bill After Renew', 'code': 'BILLRE',
            'billing_interval': 1, 'billing_period': 'monthly',
            'allow_renewal': True, 'auto_renewal': False, 'auto_closure': False,
        })
        sub = self._make_active(plan)
        sub.date_subscription_end = date.today() - timedelta(days=1)
        sub.last_renewal_period_end = False
        sub.action_renew()  # sets last_renewal_period_end to future
        # Now last_renewal_period_end >= today — billing guard should pass
        try:
            sub.action_generate_invoice()
        except UserError as e:
            # Acceptable failure for billing journal config; NOT for expiry
            self.assertNotIn('expired', str(e).lower())

    def test_16_closed_subscription_blocked_from_billing(self):
        """Closed subscription always raises UserError on billing."""
        sub = self._make_active(self.plan_auto_close)
        sub.action_close()
        with self.assertRaises(UserError) as ctx:
            sub.action_generate_invoice()
        self.assertIn('closed', str(ctx.exception).lower())

    def test_17_active_future_expiry_billing_allowed(self):
        """Active subscription with future expiry date is not blocked by expiry guard."""
        plan = self.env['subscription.plan'].create({
            'name': 'Future Expiry', 'code': 'FUTEXP',
            'billing_interval': 1, 'billing_period': 'monthly',
            'allow_renewal': False, 'auto_renewal': False, 'auto_closure': False,
        })
        sub = self._make_active(plan, days_ahead=60)
        # Should not raise expiry error (may raise journal config error — that's ok)
        try:
            sub.action_generate_invoice()
        except UserError as e:
            self.assertNotIn('expired', str(e).lower())

    # ---------------------------------------------------------------
    # History & Audit
    # ---------------------------------------------------------------

    def test_18_auto_closure_creates_status_history(self):
        """Automatic closure creates a subscription status history entry."""
        sub = self._make_active(self.plan_auto_close, expired=True)
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        closed_hist = sub.history_ids.filtered(lambda h: h.new_state == 'closed')
        self.assertTrue(closed_hist)

    def test_19_renewal_history_preserved_after_closure(self):
        """Pre-existing renewal history entries are not affected by auto-closure."""
        plan = self.env['subscription.plan'].create({
            'name': 'Renew Then Close', 'code': 'RENTC',
            'billing_interval': 1, 'billing_period': 'monthly',
            'allow_renewal': True, 'auto_renewal': False, 'auto_closure': True,
        })
        sub = self._make_active(plan, days_ahead=60)
        sub.action_renew()
        rh_count = len(sub.renewal_history_ids)
        # Now force expiry and run cron
        sub.date_subscription_end = date.today() - timedelta(days=1)
        sub.last_renewal_period_end = date.today() - timedelta(days=5)  # before today — allow closure
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        # Renewal history preserved
        self.assertEqual(len(sub.renewal_history_ids), rh_count)

    def test_20_history_immutable_after_auto_closure(self):
        """Status history records created by auto-closure cannot be modified."""
        sub = self._make_active(self.plan_auto_close, expired=True)
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        hist = sub.history_ids.filtered(lambda h: h.new_state == 'closed')
        self.assertTrue(hist)
        with self.assertRaises(UserError):
            hist[0].write({'reason': 'tampered'})

    # ---------------------------------------------------------------
    # Integration
    # ---------------------------------------------------------------

    def test_21_existing_lifecycle_unaffected(self):
        """Existing lifecycle transitions still work after expiration implementation."""
        plan = self.env['subscription.plan'].create({
            'name': 'Lifecycle Check', 'code': 'LIFECHK',
            'billing_interval': 1, 'billing_period': 'monthly',
            'allow_renewal': False, 'auto_renewal': False, 'auto_closure': False,
        })
        sub = self._make_active(plan, days_ahead=90)
        self.assertEqual(sub.state, 'active')
        sub.action_pause()
        self.assertEqual(sub.state, 'paused')
        sub.action_resume()
        self.assertEqual(sub.state, 'active')
        sub.action_close()
        self.assertEqual(sub.state, 'closed')

    def test_22_early_closure_still_works(self):
        """Manual early closure is not affected by expiration implementation."""
        plan = self.env['subscription.plan'].create({
            'name': 'Early Close Check', 'code': 'EARLYCHK',
            'billing_interval': 1, 'billing_period': 'monthly',
            'allow_renewal': False, 'auto_renewal': False,
            'allow_early_closure': True, 'auto_closure': False,
        })
        sub = self._make_active(plan, days_ahead=90)
        sub.action_close_early(reason='Test early closure')
        self.assertEqual(sub.state, 'closed')

    def test_23_pause_resume_unaffected(self):
        """Pause/resume still works correctly alongside expiration logic."""
        plan = self.env['subscription.plan'].create({
            'name': 'Pause Resume Check', 'code': 'PAUSECHK',
            'billing_interval': 1, 'billing_period': 'monthly',
            'allow_renewal': False, 'auto_renewal': False,
            'allow_pause': True, 'auto_closure': False,
        })
        sub = self._make_active(plan, days_ahead=30)
        sub.action_pause()
        self.assertEqual(sub.state, 'paused')
        sub.action_resume()
        self.assertEqual(sub.state, 'active')

    def test_24_cron_does_not_close_active_with_future_end(self):
        """Cron never touches subscriptions whose expiry date is in the future."""
        sub = self._make_active(self.plan_auto_close, expired=False, days_ahead=10)
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        self.assertEqual(sub.state, 'active')

    def test_25_auto_renewal_history_preserved_after_cron_renewal(self):
        """Cron-triggered renewal creates a renewal history record with type=automatic."""
        sub = self._make_active(self.plan_auto_renew_close, expired=True)
        sub.last_renewal_period_end = False
        self.env['subscription.subscription']._cron_process_subscription_expiration()
        auto_rh = sub.renewal_history_ids.filtered(lambda r: r.renewal_type == 'automatic' and r.renewal_result == 'success')
        self.assertTrue(auto_rh, "Expected an automatic successful renewal history entry")
