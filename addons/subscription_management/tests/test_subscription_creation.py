# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
"""
Comprehensive Automated Test Suite for Subscription Creation & Unique Identification.

Covers the 20 testing requirements:
TC-01: Convert a valid confirmed quotation into a subscription.
TC-02: Attempt to convert a draft quotation.
TC-03: Attempt to convert an expired quotation.
TC-04: Generate unique subscription numbers.
TC-05: Create multiple subscriptions and verify unique references.
TC-06: Verify correct customer assignment.
TC-07: Verify correct plan assignment.
TC-08: Verify subscription start date.
TC-09: Verify expiry date calculation for daily plans.
TC-10: Verify expiry date calculation for weekly plans.
TC-11: Verify month-end date calculations.
TC-12: Verify leap-year calculations.
TC-13: Verify payment terms configuration and transfer.
TC-14: Verify product line transfer.
TC-15: Verify product variant pricing preservation.
TC-16: Verify taxes and discounts preservation.
TC-17: Verify quotation and subscription total matching.
TC-18: Attempt duplicate subscription creation prevention.
TC-19: Test concurrent conversion requests and uniqueness constraints.
TC-20: Verify unauthorized users cannot create subscriptions.
"""

from datetime import date, timedelta

try:
    from odoo import fields
    from odoo.tests.common import TransactionCase, tagged
    from odoo.exceptions import ValidationError, UserError, AccessError
    from dateutil.relativedelta import relativedelta
except ImportError:
    import unittest
    TransactionCase = unittest.TestCase
    def tagged(*args):
        return lambda cls: cls
    class ValidationError(Exception): pass
    class UserError(Exception): pass
    class AccessError(Exception): pass
    fields = None
    relativedelta = None


@tagged('post_install', '-at_install')
class TestSubscriptionCreation(TransactionCase):
    """Test suite verifying subscription creation from confirmed quotations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not hasattr(cls, 'env'):
            return

        cls.company = cls.env.company
        today = fields.Date.context_today(cls.env.user)

        # 1. Customer Partner
        cls.customer = cls.env['res.partner'].create({
            'name': 'Global Tech Enterprise',
            'email': 'tech@globalenterprise.example',
            'phone': '+1 555 7890',
            'is_subscription_customer': True,
        })

        # 2. Payment Terms
        cls.payment_term = cls.env['account.payment.term'].create({
            'name': 'Immediate Payment - Subscription Test',
            'line_ids': [(0, 0, {
                'value': 'percent',
                'value_amount': 100,
                'days': 0,
            })],
        })

        # 3. Plans
        cls.plan_monthly = cls.env['subscription.plan'].create({
            'name': 'Monthly Pro Cloud',
            'code': 'PLAN-PRO-M',
            'billing_interval': 1,
            'billing_period': 'monthly',
            'active': True,
            'min_quantity': 1.0,
        })

        cls.plan_daily = cls.env['subscription.plan'].create({
            'name': 'Daily Micro Plan',
            'code': 'PLAN-MICRO-D',
            'billing_interval': 7,
            'billing_period': 'daily',
            'active': True,
        })

        cls.plan_weekly = cls.env['subscription.plan'].create({
            'name': 'Bi-Weekly Plan',
            'code': 'PLAN-BI-W',
            'billing_interval': 2,
            'billing_period': 'weekly',
            'active': True,
        })

        cls.plan_yearly = cls.env['subscription.plan'].create({
            'name': 'Annual Enterprise Plan',
            'code': 'PLAN-ANNUAL-Y',
            'billing_interval': 1,
            'billing_period': 'yearly',
            'active': True,
        })

        # 4. Tax
        cls.tax_10 = cls.env['account.tax'].create({
            'name': 'Sales Tax 10% Sub Test',
            'amount': 10.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
        })

        # 5. Products
        cls.product_tmpl = cls.env['product.template'].create({
            'name': 'Cloud Hosting Server',
            'type': 'service',
            'list_price': 2000.0,
            'is_subscription_product': True,
            'subscription_plan_id': cls.plan_monthly.id,
            'taxes_id': [(6, 0, cls.tax_10.ids)],
        })
        cls.product_variant = cls.product_tmpl.product_variant_ids[0]

        cls.product_tmpl_extra = cls.env['product.template'].create({
            'name': 'Database Backup Service',
            'type': 'service',
            'list_price': 500.0,
            'is_subscription_product': True,
        })
        cls.product_variant_extra = cls.product_tmpl_extra.product_variant_ids[0]

    def _create_and_confirm_quotation(self, plan=None, lines=None, date_start=None, payment_term=None):
        """Helper to create and confirm a valid quotation."""
        target_plan = plan or self.plan_monthly
        today = fields.Date.context_today(self.env.user)
        line_vals = lines or [{
            'product_id': self.product_variant.id,
            'quantity': 1.0,
            'price_unit': 2000.0,
            'tax_ids': [(6, 0, self.tax_10.ids)],
        }]

        quotation = self.env['subscription.subscription'].create({
            'partner_id': self.customer.id,
            'plan_id': target_plan.id,
            'date_quotation': today,
            'date_expiration': today + timedelta(days=30),
            'date_start': date_start or today,
            'payment_term_id': payment_term.id if payment_term else self.payment_term.id,
            'line_ids': [(0, 0, l) for l in line_vals],
        })
        quotation.action_set_quotation()
        quotation.action_confirm()
        return quotation

    # -------------------------------------------------------------------------
    # 1. Convert a valid confirmed quotation into a subscription
    # -------------------------------------------------------------------------
    def test_01_convert_valid_confirmed_quotation(self):
        """TC-01: Successfully convert a confirmed quotation into an active subscription."""
        quotation = self._create_and_confirm_quotation()
        self.assertEqual(quotation.state, 'confirmed')
        self.assertFalse(quotation.is_converted)

        sub = quotation.action_create_subscription()
        self.assertTrue(sub, "A subscription record must be returned.")
        self.assertEqual(sub.state, 'active', "Converted subscription must be active.")
        self.assertTrue(quotation.is_converted, "Quotation must be flagged as converted.")
        self.assertEqual(quotation.subscription_id, sub, "Quotation must link to generated subscription.")
        self.assertEqual(sub.quotation_id, quotation, "Subscription must link to originating quotation.")
        self.assertTrue(sub.name.startswith('SUB/'), "Subscription number must follow SUB/ format.")

    # -------------------------------------------------------------------------
    # 2. Attempt to convert a draft quotation
    # -------------------------------------------------------------------------
    def test_02_attempt_convert_draft_quotation(self):
        """TC-02: Converting a draft quotation must be blocked by validation."""
        today = fields.Date.context_today(self.env.user)
        draft_quotation = self.env['subscription.subscription'].create({
            'partner_id': self.customer.id,
            'plan_id': self.plan_monthly.id,
            'date_quotation': today,
            'date_expiration': today + timedelta(days=30),
            'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 2000.0})],
        })
        self.assertEqual(draft_quotation.state, 'draft')

        with self.assertRaises(ValidationError):
            draft_quotation.action_create_subscription()

    # -------------------------------------------------------------------------
    # 3. Attempt to convert an expired quotation
    # -------------------------------------------------------------------------
    def test_03_attempt_convert_expired_quotation(self):
        """TC-03: Converting an expired quotation must be strictly rejected."""
        today = fields.Date.context_today(self.env.user)
        # Create a confirmed quotation then simulate expiry passing before conversion
        quotation = self._create_and_confirm_quotation()
        quotation.write({'date_expiration': today - timedelta(days=1)})

        with self.assertRaises(ValidationError):
            quotation.action_create_subscription()

    # -------------------------------------------------------------------------
    # 4. Generate unique subscription numbers
    # -------------------------------------------------------------------------
    def test_04_generate_unique_subscription_numbers(self):
        """TC-04: Verify subscription reference format and ir.sequence generation."""
        quotation = self._create_and_confirm_quotation()
        sub = quotation.action_create_subscription()

        year_str = str(fields.Date.context_today(self.env.user).year)
        self.assertTrue(sub.subscription_ref, "subscription_ref must not be empty.")
        self.assertTrue(sub.subscription_ref.startswith(f"SUB/{year_str}/"),
                        f"Expected reference starting with SUB/{year_str}/, got {sub.subscription_ref}")

    # -------------------------------------------------------------------------
    # 5. Create multiple subscriptions and verify unique references
    # -------------------------------------------------------------------------
    def test_05_create_multiple_subscriptions_unique_references(self):
        """TC-05: Multiple generated subscriptions must all possess distinct references."""
        subs = []
        for _ in range(3):
            q = self._create_and_confirm_quotation()
            s = q.action_create_subscription()
            subs.append(s.subscription_ref)

        self.assertEqual(len(subs), 3)
        self.assertEqual(len(set(subs)), 3, "Subscription reference numbers must be globally unique.")

    # -------------------------------------------------------------------------
    # 6. Verify correct customer assignment
    # -------------------------------------------------------------------------
    def test_06_verify_correct_customer_assignment(self):
        """TC-06: Customer details must be faithfully assigned to the subscription."""
        quotation = self._create_and_confirm_quotation()
        sub = quotation.action_create_subscription()

        self.assertEqual(sub.partner_id, self.customer)
        self.assertEqual(sub.partner_email, 'tech@globalenterprise.example')
        self.assertEqual(sub.partner_phone, '+1 555 7890')

    # -------------------------------------------------------------------------
    # 7. Verify correct plan assignment
    # -------------------------------------------------------------------------
    def test_07_verify_correct_plan_assignment(self):
        """TC-07: Subscription plan must match the plan chosen on the quotation."""
        quotation = self._create_and_confirm_quotation(plan=self.plan_yearly)
        sub = quotation.action_create_subscription()

        self.assertEqual(sub.plan_id, self.plan_yearly)

    # -------------------------------------------------------------------------
    # 8. Verify subscription start date
    # -------------------------------------------------------------------------
    def test_08_verify_subscription_start_date(self):
        """TC-08: Subscription start date is preserved separately from quotation date."""
        custom_start = fields.Date.context_today(self.env.user) + timedelta(days=10)
        quotation = self._create_and_confirm_quotation(date_start=custom_start)
        sub = quotation.action_create_subscription()

        self.assertEqual(sub.date_start, custom_start)
        self.assertEqual(sub.date_quotation, quotation.date_quotation)
        self.assertNotEqual(sub.date_start, sub.date_quotation)

    # -------------------------------------------------------------------------
    # 9. Verify expiry date calculation for daily plans
    # -------------------------------------------------------------------------
    def test_09_verify_expiry_daily_plans(self):
        """TC-09: Expiry calculation for daily plans (e.g., 7 days interval)."""
        start_date = date(2026, 5, 1)
        quotation = self._create_and_confirm_quotation(plan=self.plan_daily, date_start=start_date)
        sub = quotation.action_create_subscription()

        expected_expiry = start_date + timedelta(days=7)
        self.assertEqual(sub.date_subscription_end, expected_expiry)

    # -------------------------------------------------------------------------
    # 10. Verify expiry date calculation for weekly plans
    # -------------------------------------------------------------------------
    def test_10_verify_expiry_weekly_plans(self):
        """TC-10: Expiry calculation for weekly plans (e.g., 2 weeks interval)."""
        start_date = date(2026, 6, 1)
        quotation = self._create_and_confirm_quotation(plan=self.plan_weekly, date_start=start_date)
        sub = quotation.action_create_subscription()

        expected_expiry = start_date + timedelta(weeks=2)
        self.assertEqual(sub.date_subscription_end, expected_expiry)

    # -------------------------------------------------------------------------
    # 11. Verify month-end date calculations
    # -------------------------------------------------------------------------
    def test_11_verify_month_end_date_calculations(self):
        """TC-11: Calendar-aware calculation handles month-end (Jan 31 -> Feb 28/29)."""
        # 2024 is a leap year (Feb has 29 days)
        start_leap = date(2024, 1, 31)
        quotation = self._create_and_confirm_quotation(plan=self.plan_monthly, date_start=start_leap)
        sub = quotation.action_create_subscription()
        self.assertEqual(sub.date_subscription_end, date(2024, 2, 29), "Jan 31 leap year should advance to Feb 29.")

        # 2025 is a non-leap year (Feb has 28 days)
        start_non_leap = date(2025, 1, 31)
        quotation_non = self._create_and_confirm_quotation(plan=self.plan_monthly, date_start=start_non_leap)
        sub_non = quotation_non.action_create_subscription()
        self.assertEqual(sub_non.date_subscription_end, date(2025, 2, 28), "Jan 31 regular year should advance to Feb 28.")

    # -------------------------------------------------------------------------
    # 12. Verify leap-year calculations
    # -------------------------------------------------------------------------
    def test_12_verify_leap_year_calculations(self):
        """TC-12: Leap year yearly plan from Feb 29 2024 calculates to Feb 28 2025."""
        start_date = date(2024, 2, 29)
        quotation = self._create_and_confirm_quotation(plan=self.plan_yearly, date_start=start_date)
        sub = quotation.action_create_subscription()

        self.assertEqual(sub.date_subscription_end, date(2025, 2, 28), "1 year from Feb 29 leap day must be Feb 28.")

    # -------------------------------------------------------------------------
    # 13. Verify payment terms
    # -------------------------------------------------------------------------
    def test_13_verify_payment_terms(self):
        """TC-13: Payment terms configured on the quotation must be assigned to subscription."""
        quotation = self._create_and_confirm_quotation(payment_term=self.payment_term)
        sub = quotation.action_create_subscription()

        self.assertEqual(sub.payment_term_id, self.payment_term)

    # -------------------------------------------------------------------------
    # 14. Verify product line transfer
    # -------------------------------------------------------------------------
    def test_14_verify_product_line_transfer(self):
        """TC-14: All product lines, variants, and quantities transfer faithfully."""
        lines = [
            {'product_id': self.product_variant.id, 'quantity': 2.0, 'price_unit': 2000.0},
            {'product_id': self.product_variant_extra.id, 'quantity': 3.0, 'price_unit': 500.0},
        ]
        quotation = self._create_and_confirm_quotation(lines=lines)
        sub = quotation.action_create_subscription()

        self.assertEqual(len(sub.line_ids), 2, "Subscription must have exactly 2 product lines.")
        sub_products = sub.line_ids.mapped('product_id')
        self.assertIn(self.product_variant, sub_products)
        self.assertIn(self.product_variant_extra, sub_products)

        line_1 = sub.line_ids.filtered(lambda l: l.product_id == self.product_variant)
        self.assertEqual(line_1.quantity, 2.0)
        self.assertEqual(line_1.price_unit, 2000.0)

    # -------------------------------------------------------------------------
    # 15. Verify product variant pricing
    # -------------------------------------------------------------------------
    def test_15_verify_product_variant_pricing(self):
        """TC-15: Additional variant prices are preserved on subscription product lines."""
        lines = [
            {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 2560.0},
        ]
        quotation = self._create_and_confirm_quotation(lines=lines)
        sub = quotation.action_create_subscription()

        self.assertEqual(sub.line_ids[0].price_unit, 2560.0, "Unit price with variant extra must match.")

    # -------------------------------------------------------------------------
    # 16. Verify taxes and discounts
    # -------------------------------------------------------------------------
    def test_16_verify_taxes_and_discounts(self):
        """TC-16: Taxes and line discounts transfer accurately without loss."""
        lines = [
            {
                'product_id': self.product_variant.id,
                'quantity': 1.0,
                'price_unit': 1000.0,
                'discount': 15.0,
                'tax_ids': [(6, 0, self.tax_10.ids)],
            },
        ]
        quotation = self._create_and_confirm_quotation(lines=lines)
        sub = quotation.action_create_subscription()

        sub_line = sub.line_ids[0]
        self.assertEqual(sub_line.discount, 15.0)
        self.assertEqual(sub_line.tax_ids, self.tax_10)

    # -------------------------------------------------------------------------
    # 17. Verify quotation and subscription total matching
    # -------------------------------------------------------------------------
    def test_17_verify_quotation_and_subscription_total_matching(self):
        """TC-17: Subtotal, taxes, discounts, and total of subscription must equal quotation."""
        lines = [
            {
                'product_id': self.product_variant.id,
                'quantity': 2.0,
                'price_unit': 2000.0,
                'discount': 10.0,
                'tax_ids': [(6, 0, self.tax_10.ids)],
            },
        ]
        quotation = self._create_and_confirm_quotation(lines=lines)
        sub = quotation.action_create_subscription()

        self.assertEqual(sub.amount_untaxed, quotation.amount_untaxed)
        self.assertEqual(sub.amount_discount, quotation.amount_discount)
        self.assertEqual(sub.amount_tax, quotation.amount_tax)
        self.assertEqual(sub.amount_total, quotation.amount_total)

    # -------------------------------------------------------------------------
    # 18. Attempt duplicate subscription creation
    # -------------------------------------------------------------------------
    def test_18_attempt_duplicate_subscription_creation(self):
        """TC-18: Converting an already-converted quotation raises UserError."""
        quotation = self._create_and_confirm_quotation()
        sub = quotation.action_create_subscription()
        self.assertTrue(sub)

        # Second attempt must be rejected
        with self.assertRaises(UserError):
            quotation.action_create_subscription()

    # -------------------------------------------------------------------------
    # 19. Test concurrent conversion requests and uniqueness constraints
    # -------------------------------------------------------------------------
    def test_19_test_concurrent_conversion_requests(self):
        """TC-19: Uniqueness constraint blocks multiple subscriptions for same quotation."""
        quotation = self._create_and_confirm_quotation()
        sub1 = quotation.action_create_subscription()

        # Attempt to bypass quotation action and create second subscription directly pointing to same quotation
        with self.assertRaises(ValidationError):
            self.env['subscription.subscription'].create({
                'name': 'SUB/2026/99999',
                'subscription_ref': 'SUB/2026/99999',
                'partner_id': self.customer.id,
                'plan_id': self.plan_monthly.id,
                'quotation_id': quotation.id,
                'state': 'active',
                'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 1000.0})],
            })

    # -------------------------------------------------------------------------
    # 20. Verify unauthorized users cannot create subscriptions
    # -------------------------------------------------------------------------
    def test_20_verify_unauthorized_users_cannot_create_subscriptions(self):
        """TC-20: Users lacking subscription user group cannot create subscriptions."""
        unauth_user = self.env['res.users'].create({
            'name': 'External Portal User',
            'login': 'unauthorized_sub_portal@example.com',
            'email': 'unauth@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })

        quotation = self._create_and_confirm_quotation()
        with self.assertRaises(AccessError):
            quotation.with_user(unauth_user).action_create_subscription()
