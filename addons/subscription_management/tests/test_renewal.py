# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
"""
Tests for Subscription Renewal Management (Epic-35).
"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError, AccessError


class TestSubscriptionRenewal(TransactionCase):
    """Test manual renewal, automatic renewal, date calculations, duplicate prevention."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref('base.user_admin'))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Renewal Test Customer',
            'is_subscription_customer': True,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Renewal Product',
            'type': 'service',
            'is_subscription_product': True,
            'list_price': 50.0,
        })
        cls.plan_monthly = cls.env['subscription.plan'].create({
            'name': 'Monthly Renewable',
            'code': 'RENEWMO',
            'billing_interval': 1,
            'billing_period': 'monthly',
            'allow_renewal': True,
            'auto_renewal': False,
        })
        cls.plan_no_renewal = cls.env['subscription.plan'].create({
            'name': 'No Renewal',
            'code': 'NORENE',
            'billing_interval': 1,
            'billing_period': 'monthly',
            'allow_renewal': False,
            'auto_renewal': False,
        })
        cls.plan_auto = cls.env['subscription.plan'].create({
            'name': 'Auto Renewable',
            'code': 'AUTORE',
            'billing_interval': 1,
            'billing_period': 'monthly',
            'allow_renewal': True,
            'auto_renewal': True,
        })

    def _make_active(self, plan=None):
        plan = plan or self.plan_monthly
        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': plan.id,
            'date_quotation': date.today(),
            'date_start': date.today(),
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 50.0,
            })],
        })
        sub.action_set_quotation()
        sub.action_confirm()
        sub.action_activate()
        return sub

    # ---------------------------------------------------------------
    # Manual Renewal
    # ---------------------------------------------------------------

    def test_01_manual_renewal_active_succeeds(self):
        """Active subscription with allow_renewal=True can be manually renewed."""
        sub = self._make_active()
        old_end = sub.date_subscription_end
        sub.action_renew()
        self.assertGreater(sub.date_subscription_end, old_end)
        self.assertEqual(sub.renewal_count, 1)
        self.assertEqual(sub.date_last_renewal, date.today())

    def test_02_manual_renewal_disabled_plan_rejected(self):
        """Renewal raises ValidationError when plan.allow_renewal=False."""
        sub = self._make_active(plan=self.plan_no_renewal)
        with self.assertRaises(ValidationError):
            sub.action_renew()

    def test_03_manual_renewal_closed_rejected(self):
        """Closed subscription cannot be renewed."""
        sub = self._make_active()
        sub.action_close()
        with self.assertRaises(ValidationError):
            sub.action_renew()

    def test_04_manual_renewal_paused_succeeds(self):
        """Paused subscription can be renewed when plan allows it."""
        sub = self._make_active()
        sub.action_pause()
        self.assertEqual(sub.state, 'paused')
        sub.action_renew()
        self.assertEqual(sub.renewal_count, 1)

    def test_05_renewal_updates_expiry_date_correctly(self):
        """New expiry date is exactly one billing interval beyond the old expiry."""
        sub = self._make_active()
        old_end = sub.date_subscription_end
        sub.action_renew()
        expected = old_end + relativedelta(months=1)
        self.assertEqual(sub.date_subscription_end, expected)

    def test_06_renewal_updates_next_billing_date(self):
        """next_billing_date is recalculated after renewal."""
        sub = self._make_active()
        old_end = sub.date_subscription_end
        sub.action_renew()
        self.assertIsNotNone(sub.next_billing_date)
        self.assertGreater(sub.next_billing_date, old_end)

    def test_07_renewal_billing_date_not_beyond_new_end(self):
        """next_billing_date never exceeds the new subscription end date."""
        sub = self._make_active()
        sub.action_renew()
        self.assertLessEqual(sub.next_billing_date, sub.date_subscription_end)

    # ---------------------------------------------------------------
    # Date Calculations
    # ---------------------------------------------------------------

    def test_08_daily_renewal_calculation(self):
        """Daily plan: renewal adds billing_interval days."""
        plan = self.env['subscription.plan'].create({
            'name': 'Daily Plan', 'code': 'DAYRE',
            'billing_interval': 7, 'billing_period': 'daily',
            'allow_renewal': True,
        })
        sub = self._make_active(plan=plan)
        old_end = sub.date_subscription_end
        sub.action_renew()
        self.assertEqual(sub.date_subscription_end, old_end + timedelta(days=7))

    def test_09_weekly_renewal_calculation(self):
        """Weekly plan: renewal adds billing_interval weeks."""
        plan = self.env['subscription.plan'].create({
            'name': 'Weekly Plan', 'code': 'WEEKRE',
            'billing_interval': 2, 'billing_period': 'weekly',
            'allow_renewal': True,
        })
        sub = self._make_active(plan=plan)
        old_end = sub.date_subscription_end
        sub.action_renew()
        self.assertEqual(sub.date_subscription_end, old_end + timedelta(weeks=2))

    def test_10_monthly_renewal_calculation(self):
        """Monthly plan: renewal adds calendar months via relativedelta."""
        sub = self._make_active()
        old_end = sub.date_subscription_end
        sub.action_renew()
        self.assertEqual(sub.date_subscription_end, old_end + relativedelta(months=1))

    def test_11_yearly_renewal_calculation(self):
        """Yearly plan: renewal adds calendar years via relativedelta."""
        plan = self.env['subscription.plan'].create({
            'name': 'Yearly Plan', 'code': 'YEARRE',
            'billing_interval': 1, 'billing_period': 'yearly',
            'allow_renewal': True,
        })
        sub = self._make_active(plan=plan)
        old_end = sub.date_subscription_end
        sub.action_renew()
        self.assertEqual(sub.date_subscription_end, old_end + relativedelta(years=1))

    def test_12_jan_month_end_renewal(self):
        """Monthly renewal from Jan 31 goes to Feb 28/29 (calendar-aware)."""
        sub = self._make_active()
        jan31 = date(2026, 1, 31)
        sub.date_subscription_end = jan31
        sub.last_renewal_period_end = False  # reset duplicate guard
        sub.action_renew()
        expected = jan31 + relativedelta(months=1)  # Feb 28 2026
        self.assertEqual(sub.date_subscription_end, expected)

    def test_13_leap_year_renewal(self):
        """Yearly renewal from Feb 29 (leap year) lands on Feb 28 next year."""
        plan = self.env['subscription.plan'].create({
            'name': 'Leap Year Plan', 'code': 'LEAPRE',
            'billing_interval': 1, 'billing_period': 'yearly',
            'allow_renewal': True,
        })
        sub = self._make_active(plan=plan)
        feb29 = date(2024, 2, 29)
        sub.date_subscription_end = feb29
        sub.last_renewal_period_end = False
        sub.action_renew()
        expected = feb29 + relativedelta(years=1)  # Feb 28 2025
        self.assertEqual(sub.date_subscription_end, expected)

    # ---------------------------------------------------------------
    # Duplicate Prevention
    # ---------------------------------------------------------------

    def test_14_duplicate_renewal_same_period_rejected(self):
        """Renewing twice for the same period raises ValidationError."""
        sub = self._make_active()
        sub.action_renew()
        # Simulate: last_renewal_period_end is now >= current date_subscription_end
        with self.assertRaises(ValidationError):
            sub.action_renew()

    def test_15_renewal_after_period_advances_succeeds(self):
        """After period advances, a second renewal is permitted."""
        sub = self._make_active()
        sub.action_renew()
        # Manually push last_renewal_period_end behind new end to simulate period advance
        sub.last_renewal_period_end = sub.date_subscription_end - relativedelta(months=1)
        # Now renewal should succeed
        sub.action_renew()
        self.assertEqual(sub.renewal_count, 2)

    # ---------------------------------------------------------------
    # Automatic Renewal
    # ---------------------------------------------------------------

    def test_16_cron_renews_auto_renewal_plans(self):
        """Cron auto-renews subscriptions whose plans have auto_renewal=True."""
        sub = self._make_active(plan=self.plan_auto)
        # Force expiry to today so cron picks it up
        sub.date_subscription_end = date.today()
        sub.last_renewal_period_end = False
        self.env['subscription.subscription']._cron_auto_renew_subscriptions()
        self.assertEqual(sub.renewal_count, 1)

    def test_17_cron_skips_non_auto_plans(self):
        """Cron skips subscriptions with auto_renewal=False."""
        sub = self._make_active(plan=self.plan_monthly)
        sub.date_subscription_end = date.today()
        sub.last_renewal_period_end = False
        self.env['subscription.subscription']._cron_auto_renew_subscriptions()
        self.assertEqual(sub.renewal_count, 0)

    def test_18_cron_skips_closed_subscriptions(self):
        """Cron does not renew closed subscriptions."""
        sub = self._make_active(plan=self.plan_auto)
        sub.action_close()
        self.env['subscription.subscription']._cron_auto_renew_subscriptions()
        self.assertEqual(sub.renewal_count, 0)

    def test_19_cron_does_not_duplicate_already_renewed(self):
        """Running cron twice does not renew the same period twice."""
        sub = self._make_active(plan=self.plan_auto)
        sub.date_subscription_end = date.today()
        sub.last_renewal_period_end = False
        self.env['subscription.subscription']._cron_auto_renew_subscriptions()
        count_after_first = sub.renewal_count
        self.env['subscription.subscription']._cron_auto_renew_subscriptions()
        self.assertEqual(sub.renewal_count, count_after_first)

    # ---------------------------------------------------------------
    # Renewal History
    # ---------------------------------------------------------------

    def test_20_renewal_creates_history_entry(self):
        """A renewal history record is created on each successful renewal."""
        sub = self._make_active()
        before = len(sub.renewal_history_ids)
        sub.action_renew()
        self.assertEqual(len(sub.renewal_history_ids), before + 1)

    def test_21_history_records_prev_and_new_dates(self):
        """History entry stores previous and new expiry/billing dates."""
        sub = self._make_active()
        old_end = sub.date_subscription_end
        sub.action_renew()
        hist = sub.renewal_history_ids[0]
        self.assertEqual(hist.prev_subscription_end, old_end)
        self.assertGreater(hist.new_subscription_end, old_end)
        self.assertEqual(hist.renewal_type, 'manual')
        self.assertEqual(hist.renewal_result, 'success')

    def test_22_history_is_immutable(self):
        """Renewal history entries cannot be modified."""
        sub = self._make_active()
        sub.action_renew()
        hist = sub.renewal_history_ids[0]
        with self.assertRaises(UserError):
            hist.write({'notes': 'tampered'})

    def test_23_auto_renewal_history_type_is_automatic(self):
        """Auto-renewal creates history entry with type='automatic'."""
        sub = self._make_active(plan=self.plan_auto)
        sub.date_subscription_end = date.today()
        sub.last_renewal_period_end = False
        self.env['subscription.subscription']._cron_auto_renew_subscriptions()
        hist = sub.renewal_history_ids.filtered(lambda h: h.renewal_type == 'automatic')
        self.assertTrue(hist)

    # ---------------------------------------------------------------
    # Integration / existing lifecycle still works
    # ---------------------------------------------------------------

    def test_24_lifecycle_unaffected_after_renewal(self):
        """Full lifecycle still works after renewal."""
        sub = self._make_active()
        sub.action_renew()
        self.assertEqual(sub.state, 'active')
        sub.action_close()
        self.assertEqual(sub.state, 'closed')

    def test_25_early_closure_prevents_further_renewal(self):
        """After early closure, renewal is rejected."""
        sub = self._make_active()
        sub.action_close_early(reason='Customer quit')
        with self.assertRaises(ValidationError):
            sub.action_renew()
