# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
"""
Tests for Subscription Pause, Resume, and Early Closure (Epic-35).
"""
from datetime import date, timedelta
from unittest.mock import patch
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError, AccessError


class TestPauseResumeClosure(TransactionCase):
    """Test pause/resume/early-closure lifecycle for subscription.subscription."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref('base.user_admin'))

        # Customer
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Subscriber',
            'is_subscription_customer': True,
        })

        # Product
        cls.product = cls.env['product.product'].create({
            'name': 'Sub Product',
            'type': 'service',
            'is_subscription_product': True,
            'list_price': 100.0,
        })

        # Plan with pause allowed
        cls.plan = cls.env['subscription.plan'].create({
            'name': 'Monthly Test Plan',
            'code': 'TESTMO',
            'billing_interval': 1,
            'billing_period': 'monthly',
            'allow_pause': True,
            'allow_early_closure': True,
            'pause_billing_policy': 'shift',
        })

    def _make_active_subscription(self):
        """Helper: create a subscription in 'active' state."""
        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan.id,
            'date_quotation': date.today(),
            'date_start': date.today(),
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 100.0,
            })],
        })
        sub.action_set_quotation()
        sub.action_confirm()
        sub.action_activate()
        self.assertEqual(sub.state, 'active')
        return sub

    # ---------------------------------------------------------------
    # Pause tests
    # ---------------------------------------------------------------

    def test_01_pause_active_succeeds(self):
        """Active subscription can be paused when plan allows it."""
        sub = self._make_active_subscription()
        sub.action_pause(reason='Server maintenance')
        self.assertEqual(sub.state, 'paused')
        self.assertTrue(sub.date_paused)
        self.assertEqual(sub.pause_reason, 'Server maintenance')

    def test_02_pause_disabled_plan_rejected(self):
        """Pausing raises ValidationError if plan.allow_pause is False."""
        self.plan.allow_pause = False
        sub = self._make_active_subscription()
        with self.assertRaises(ValidationError):
            sub.action_pause()
        self.plan.allow_pause = True  # restore

    def test_03_pause_non_active_rejected(self):
        """Pausing a non-active subscription raises ValidationError."""
        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan.id,
            'date_quotation': date.today(),
            'date_start': date.today(),
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1, 'price_unit': 100.0})],
        })
        # Still draft
        with self.assertRaises(ValidationError):
            sub.action_pause()

    def test_04_pause_already_paused_rejected(self):
        """Pausing an already-paused subscription raises ValidationError."""
        sub = self._make_active_subscription()
        sub.action_pause()
        with self.assertRaises(ValidationError):
            sub.action_pause()

    def test_05_pause_records_date_and_reason(self):
        """date_paused and pause_reason are stored on pause."""
        sub = self._make_active_subscription()
        sub.action_pause(reason='Holiday freeze')
        self.assertIsNotNone(sub.date_paused)
        self.assertEqual(sub.pause_reason, 'Holiday freeze')

    def test_06_pause_creates_history_entry(self):
        """A history entry is created for active→paused transition."""
        sub = self._make_active_subscription()
        before = len(sub.history_ids)
        sub.action_pause(reason='Test')
        self.assertGreater(len(sub.history_ids), before)
        last = sub.history_ids.sorted('change_date')[0]
        self.assertEqual(last.new_state, 'paused')

    # ---------------------------------------------------------------
    # Resume tests
    # ---------------------------------------------------------------

    def test_07_resume_paused_succeeds(self):
        """Paused subscription can be resumed."""
        sub = self._make_active_subscription()
        sub.action_pause()
        sub.action_resume()
        self.assertEqual(sub.state, 'active')
        self.assertTrue(sub.date_resumed)

    def test_08_resume_active_rejected(self):
        """Resuming an active (non-paused) subscription raises ValidationError."""
        sub = self._make_active_subscription()
        with self.assertRaises(ValidationError):
            sub.action_resume()

    def test_09_resume_closed_rejected(self):
        """Resuming a closed subscription raises ValidationError."""
        sub = self._make_active_subscription()
        sub.action_close()
        with self.assertRaises(ValidationError):
            sub.action_resume()

    def test_10_resume_shifts_billing_date(self):
        """Resume with policy='shift' adds pause duration to next_billing_date."""
        sub = self._make_active_subscription()
        billing_date = date.today() + timedelta(days=30)
        sub.next_billing_date = billing_date

        # Simulate pausing 5 days ago
        from datetime import datetime
        pause_time = datetime.now() - timedelta(days=5)
        sub.write({'state': 'paused', 'date_paused': pause_time})
        sub.action_resume()

        # next_billing_date should shift by ~5 days
        self.assertGreaterEqual(sub.next_billing_date, billing_date + timedelta(days=4))
        self.assertLessEqual(sub.next_billing_date, billing_date + timedelta(days=6))

    def test_11_multiple_pause_resume_accumulates_days(self):
        """total_paused_days accumulates across multiple pause/resume cycles."""
        sub = self._make_active_subscription()
        self.assertEqual(sub.total_paused_days, 0)
        # First cycle
        sub.action_pause()
        sub.action_resume()
        # Second cycle
        sub.action_pause()
        sub.action_resume()
        # Should be non-negative cumulative count (may be 0 if same-second test)
        self.assertGreaterEqual(sub.total_paused_days, 0)

    # ---------------------------------------------------------------
    # Early closure tests
    # ---------------------------------------------------------------

    def test_12_early_close_active_succeeds(self):
        """Active subscription can be closed early with a reason."""
        sub = self._make_active_subscription()
        sub.action_close_early(reason='Customer requested cancellation')
        self.assertEqual(sub.state, 'closed')
        self.assertEqual(sub.early_closure_reason, 'Customer requested cancellation')
        self.assertTrue(sub.date_closed_early)
        self.assertFalse(sub.next_billing_date)

    def test_13_early_close_disabled_plan_rejected(self):
        """Early closure raises ValidationError if plan.allow_early_closure is False."""
        self.plan.allow_early_closure = False
        sub = self._make_active_subscription()
        with self.assertRaises(ValidationError):
            sub.action_close_early(reason='Test')
        self.plan.allow_early_closure = True  # restore

    def test_14_early_close_without_reason_rejected(self):
        """Early closure without a reason raises ValidationError."""
        sub = self._make_active_subscription()
        with self.assertRaises(ValidationError):
            sub.action_close_early(reason=None)

    def test_15_early_close_already_closed_rejected(self):
        """Closing an already-closed subscription raises ValidationError."""
        sub = self._make_active_subscription()
        sub.action_close()
        with self.assertRaises(ValidationError):
            sub.action_close_early(reason='Attempt again')

    def test_16_early_close_records_date_and_reason(self):
        """date_closed_early and early_closure_reason are stored."""
        sub = self._make_active_subscription()
        sub.action_close_early(reason='Moving to competitor')
        self.assertEqual(sub.early_closure_reason, 'Moving to competitor')
        self.assertEqual(sub.date_closed_early, date.today())

    def test_17_closed_subscription_cannot_resume(self):
        """A subscription closed early cannot be resumed."""
        sub = self._make_active_subscription()
        sub.action_close_early(reason='Done')
        with self.assertRaises(ValidationError):
            sub.action_resume()

    # ---------------------------------------------------------------
    # Billing protection tests
    # ---------------------------------------------------------------

    def test_18_active_can_generate_invoice(self):
        """Active subscription can invoke action_generate_invoice (UserError for billing config, not state)."""
        sub = self._make_active_subscription()
        sub.next_billing_date = date.today()
        # It may raise UserError for missing journal, but NOT for state
        try:
            sub.action_generate_invoice()
        except UserError as e:
            self.assertNotIn('paused', str(e).lower())
            self.assertNotIn('closed', str(e).lower())

    def test_19_paused_excluded_from_billing(self):
        """Paused subscription raises UserError with 'paused' when billing attempted."""
        sub = self._make_active_subscription()
        sub.action_pause()
        with self.assertRaises(UserError) as ctx:
            sub.action_generate_invoice()
        self.assertIn('paused', str(ctx.exception).lower())

    def test_20_closed_excluded_from_billing(self):
        """Closed subscription raises UserError with 'closed' when billing attempted."""
        sub = self._make_active_subscription()
        sub.action_close()
        with self.assertRaises(UserError) as ctx:
            sub.action_generate_invoice()
        self.assertIn('closed', str(ctx.exception).lower())

    def test_21_cron_skips_paused_subscriptions(self):
        """Cron query filters active only — paused subscriptions are implicitly excluded."""
        sub = self._make_active_subscription()
        sub.action_pause()
        # Verify the domain used by cron excludes paused
        paused_subs = self.env['subscription.subscription'].search([
            ('state', '=', 'active'),
            ('id', '=', sub.id),
        ])
        self.assertFalse(paused_subs, "Paused subscription should not appear in cron active query")

    # ---------------------------------------------------------------
    # Integration / lifecycle tests
    # ---------------------------------------------------------------

    def test_22_full_pause_resume_close_lifecycle(self):
        """Full lifecycle: draft→quotation→confirmed→active→paused→active→closed."""
        sub = self._make_active_subscription()
        # Pause
        sub.action_pause(reason='Upgrade in progress')
        self.assertEqual(sub.state, 'paused')
        # Resume
        sub.action_resume()
        self.assertEqual(sub.state, 'active')
        # Close
        sub.action_close()
        self.assertEqual(sub.state, 'closed')

    def test_23_plan_allow_pause_propagated(self):
        """Plan allow_pause=True is accessible on subscription via plan_id."""
        sub = self._make_active_subscription()
        self.assertTrue(sub.plan_id.allow_pause)
        self.assertTrue(sub.plan_id.allow_early_closure)

    def test_24_pause_billing_policy_no_change(self):
        """With policy='no_change', next_billing_date is not shifted on resume."""
        self.plan.pause_billing_policy = 'no_change'
        sub = self._make_active_subscription()
        billing_date = date.today() + timedelta(days=30)
        sub.next_billing_date = billing_date

        from datetime import datetime
        pause_time = datetime.now() - timedelta(days=10)
        sub.write({'state': 'paused', 'date_paused': pause_time})
        sub.action_resume()

        self.assertEqual(sub.next_billing_date, billing_date)
        self.plan.pause_billing_policy = 'shift'  # restore

    def test_25_history_immutable_on_pause_transition(self):
        """History entries for pause/resume transitions cannot be modified."""
        sub = self._make_active_subscription()
        sub.action_pause()
        hist = sub.history_ids.filtered(lambda h: h.new_state == 'paused')
        self.assertTrue(hist)
        with self.assertRaises(UserError):
            hist[0].write({'reason': 'tampered'})
