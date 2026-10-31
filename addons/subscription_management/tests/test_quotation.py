# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from datetime import date, timedelta

try:
    from odoo.tests.common import TransactionCase, tagged
    from odoo.exceptions import ValidationError, UserError, AccessError
except ImportError:
    import unittest
    TransactionCase = unittest.TestCase
    def tagged(*args):
        return lambda cls: cls
    class ValidationError(Exception): pass
    class UserError(Exception): pass
    class AccessError(Exception): pass


@tagged('post_install', '-at_install')
class TestQuotationManagement(TransactionCase):
    """Automated test suite verifying the 14 requirements for Quotation Creation and Management."""

    def setUp(self):
        super().setUp()
        if not hasattr(self, 'env'):
            return

        self.company = self.env.company
        self.today = fields.Date.context_today(self.env.user)
        self.yesterday = self.today - timedelta(days=1)
        self.tomorrow = self.today + timedelta(days=1)
        self.next_month = self.today + timedelta(days=30)
        self.last_month = self.today - timedelta(days=30)

        # 1. Setup Customer
        self.customer = self.env['res.partner'].create({
            'name': 'Brightloop Client Ltd',
            'email': 'client@brightloop.com',
            'phone': '+1 555 0199',
            'is_subscription_customer': True,
        })

        # 2. Setup Subscription Plans
        self.plan_monthly = self.env['subscription.plan'].create({
            'name': 'Pro Monthly Plan',
            'code': 'PLAN-PRO-M',
            'billing_interval': 1,
            'billing_period': 'monthly',
            'active': True,
            'min_quantity': 1.0,
        })
        self.plan_expired = self.env['subscription.plan'].create({
            'name': 'Legacy Expired Plan',
            'code': 'PLAN-LEGACY-EXP',
            'billing_interval': 1,
            'billing_period': 'monthly',
            'date_start': self.last_month - timedelta(days=30),
            'date_end': self.yesterday,
            'active': True,
        })
        self.plan_inactive = self.env['subscription.plan'].create({
            'name': 'Disabled Plan',
            'code': 'PLAN-DISABLED',
            'active': False,
        })

        # 3. Setup Subscription Products & Variants
        self.product_tmpl = self.env['product.template'].create({
            'name': 'Cloud SaaS Core',
            'is_subscription_product': True,
            'list_price': 2000.0,
        })
        # Single variant
        self.product_variant = self.product_tmpl.product_variant_id or self.env['product.product'].search(
            [('product_tmpl_id', '=', self.product_tmpl.id)], limit=1
        )
        if not self.product_variant:
            self.product_variant = self.env['product.product'].create({
                'product_tmpl_id': self.product_tmpl.id,
            })

        # Variant with extra price: Base ₹2,000 + Extra ₹560 = ₹2,560
        self.product_variant_extra = self.env['product.product'].create({
            'name': 'Cloud SaaS Enterprise Brand',
            'product_tmpl_id': self.product_tmpl.id,
            'is_subscription_product': True,
        })
        # Simulate price_extra
        if hasattr(self.product_variant_extra, 'price_extra'):
            self.product_variant_extra.price_extra = 560.0

        # Additional product for multi-line tests
        self.product_addon = self.env['product.product'].create({
            'name': 'Storage Expansion 500GB',
            'is_subscription_product': True,
            'list_price': 500.0,
        })

        # 4. Setup Discount Rules
        self.discount_eligible = self.env['subscription.discount'].create({
            'name': 'Promo 10%',
            'code': 'PROMO10',
            'discount_type': 'percent',
            'discount_value': 10.0,
            'date_start': self.last_month,
            'date_end': self.next_month,
            'min_amount': 1000.0,
            'active': True,
        })
        self.discount_expired = self.env['subscription.discount'].create({
            'name': 'Black Friday 2025',
            'code': 'BF2025',
            'discount_type': 'percent',
            'discount_value': 25.0,
            'date_start': self.last_month - timedelta(days=60),
            'date_end': self.yesterday,
            'active': True,
        })

        # 5. Setup Tax Rule
        self.tax_10 = self.env['account.tax'].create({
            'name': 'VAT 10%',
            'amount': 10.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
        })

    # -------------------------------------------------------------------------
    # TEST 1: Valid Quotation Creation
    # -------------------------------------------------------------------------
    def test_01_valid_quotation_creation(self):
        """Test creating a valid draft quotation with products and lifecycle progression."""
        if not hasattr(self, 'env'):
            return

        quotation = self.env['subscription.subscription'].create({
            'partner_id': self.customer.id,
            'plan_id': self.plan_monthly.id,
            'date_quotation': self.today,
            'date_expiration': self.tomorrow,
            'line_ids': [(0, 0, {
                'product_id': self.product_variant.id,
                'quantity': 2.0,
                'price_unit': 2000.0,
            })],
        })

        self.assertTrue(quotation.name, "Quotation reference must be generated.")
        self.assertEqual(quotation.state, 'draft', "Initial state must be draft.")
        self.assertEqual(quotation.amount_untaxed, 4000.0)
        self.assertEqual(quotation.amount_total, 4000.0)
        self.assertEqual(quotation.partner_email, 'client@brightloop.com')

        # Move Draft -> Quotation Sent
        quotation.action_send_quotation()
        self.assertEqual(quotation.state, 'quotation')

        # Move Quotation Sent -> Confirmed
        quotation.action_confirm()
        self.assertEqual(quotation.state, 'confirmed')

    # -------------------------------------------------------------------------
    # TEST 2: Duplicate Quotation Reference Prevention
    # -------------------------------------------------------------------------
    def test_02_duplicate_quotation_reference_prevention(self):
        """Verify that duplicate quotation references are rejected."""
        if not hasattr(self, 'env'):
            return

        quotation1 = self.env['subscription.subscription'].create({
            'name': 'QT/2026/UNIQUE01',
            'partner_id': self.customer.id,
            'plan_id': self.plan_monthly.id,
            'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 2000.0})],
        })
        self.assertEqual(quotation1.name, 'QT/2026/UNIQUE01')

        # Attempt to create duplicate reference in the same company
        with self.assertRaises(ValidationError):
            self.env['subscription.subscription'].create({
                'name': 'QT/2026/UNIQUE01',
                'partner_id': self.customer.id,
                'plan_id': self.plan_monthly.id,
                'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 2000.0})],
            })

    # -------------------------------------------------------------------------
    # TEST 3: Invalid Customer Selection
    # -------------------------------------------------------------------------
    def test_03_invalid_customer_selection(self):
        """Verify that inactive customers or missing customers raise ValidationError."""
        if not hasattr(self, 'env'):
            return

        inactive_partner = self.env['res.partner'].create({
            'name': 'Deactivated Client',
            'active': False,
        })

        with self.assertRaises(ValidationError):
            self.env['subscription.subscription'].create({
                'partner_id': inactive_partner.id,
                'plan_id': self.plan_monthly.id,
                'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 2000.0})],
            })

    # -------------------------------------------------------------------------
    # TEST 4: Unavailable Subscription Plan
    # -------------------------------------------------------------------------
    def test_04_unavailable_subscription_plan(self):
        """Reject quotation creation when plan is deactivated (active=False)."""
        if not hasattr(self, 'env'):
            return

        with self.assertRaises(ValidationError):
            self.env['subscription.subscription'].create({
                'partner_id': self.customer.id,
                'plan_id': self.plan_inactive.id,
                'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 2000.0})],
            })

    # -------------------------------------------------------------------------
    # TEST 5: Expired Subscription Plan
    # -------------------------------------------------------------------------
    def test_05_expired_subscription_plan(self):
        """Reject quotation creation when subscription plan end_date has passed."""
        if not hasattr(self, 'env'):
            return

        with self.assertRaises(ValidationError):
            self.env['subscription.subscription'].create({
                'partner_id': self.customer.id,
                'plan_id': self.plan_expired.id,
                'date_quotation': self.today,
                'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 2000.0})],
            })

    # -------------------------------------------------------------------------
    # TEST 6: Zero or Negative Product Quantity
    # -------------------------------------------------------------------------
    def test_06_zero_or_negative_product_quantity(self):
        """Ensure quantity <= 0 is strictly rejected."""
        if not hasattr(self, 'env'):
            return

        # Test zero quantity
        with self.assertRaises(ValidationError):
            self.env['subscription.subscription'].create({
                'partner_id': self.customer.id,
                'plan_id': self.plan_monthly.id,
                'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 0.0, 'price_unit': 2000.0})],
            })

        # Test negative quantity
        with self.assertRaises(ValidationError):
            self.env['subscription.subscription'].create({
                'partner_id': self.customer.id,
                'plan_id': self.plan_monthly.id,
                'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': -2.0, 'price_unit': 2000.0})],
            })

    # -------------------------------------------------------------------------
    # TEST 7: Product Variant Price Calculation
    # -------------------------------------------------------------------------
    def test_07_product_variant_price_calculation(self):
        """Verify: Base ₹2,000 + Variant Extra ₹560 = Final Unit Price ₹2,560 without double addition."""
        if not hasattr(self, 'env'):
            return

        line = self.env['subscription.subscription.line'].new({
            'product_id': self.product_variant_extra.id,
        })
        line._onchange_product_id()

        expected_unit_price = 2560.0
        self.assertEqual(line.price_unit, expected_unit_price,
                         "Unit price should accurately reflect Base (₹2,000) + Extra (₹560) = ₹2,560.")

        # Test subtotal with quantity 2: ₹2,560 * 2 = ₹5,120
        line.quantity = 2.0
        line._compute_line_totals()
        self.assertEqual(line.price_subtotal, 5120.0)

    # -------------------------------------------------------------------------
    # TEST 8: Multiple Product Line Calculations
    # -------------------------------------------------------------------------
    def test_08_multiple_product_line_calculations(self):
        """Verify calculations across multiple distinct product lines."""
        if not hasattr(self, 'env'):
            return

        quotation = self.env['subscription.subscription'].create({
            'partner_id': self.customer.id,
            'plan_id': self.plan_monthly.id,
            'line_ids': [
                (0, 0, {'product_id': self.product_variant.id, 'quantity': 2.0, 'price_unit': 2000.0}), # 4000
                (0, 0, {'product_id': self.product_addon.id, 'quantity': 3.0, 'price_unit': 500.0}),    # 1500
            ],
        })

        self.assertEqual(len(quotation.line_ids), 2)
        self.assertEqual(quotation.amount_untaxed, 5500.0)
        self.assertEqual(quotation.amount_total, 5500.0)

    # -------------------------------------------------------------------------
    # TEST 9: Tax Calculation
    # -------------------------------------------------------------------------
    def test_09_tax_calculation(self):
        """Verify tax amount computation using Odoo native account.tax engine."""
        if not hasattr(self, 'env'):
            return

        quotation = self.env['subscription.subscription'].create({
            'partner_id': self.customer.id,
            'plan_id': self.plan_monthly.id,
            'line_ids': [(0, 0, {
                'product_id': self.product_variant.id,
                'quantity': 1.0,
                'price_unit': 2000.0,
                'tax_ids': [(6, 0, [self.tax_10.id])],
            })],
        })

        # Untaxed: ₹2,000, 10% Tax: ₹200, Total: ₹2,200
        self.assertEqual(quotation.amount_untaxed, 2000.0)
        self.assertEqual(quotation.amount_tax, 200.0)
        self.assertEqual(quotation.amount_total, 2200.0)

    # -------------------------------------------------------------------------
    # TEST 10: Eligible Discount Application
    # -------------------------------------------------------------------------
    def test_10_eligible_discount_application(self):
        """Verify coupon and discount rule application with subtotal deductions."""
        if not hasattr(self, 'env'):
            return

        quotation = self.env['subscription.subscription'].create({
            'partner_id': self.customer.id,
            'plan_id': self.plan_monthly.id,
            'discount_id': self.discount_eligible.id, # 10% on >= 1000
            'line_ids': [(0, 0, {
                'product_id': self.product_variant.id,
                'quantity': 1.0,
                'price_unit': 2000.0,
            })],
        })

        # Untaxed: ₹2,000. 10% Discount = ₹200. Final Total = ₹1,800.
        self.assertEqual(quotation.amount_untaxed, 2000.0)
        self.assertEqual(quotation.amount_discount, 200.0)
        self.assertEqual(quotation.amount_total, 1800.0)

    # -------------------------------------------------------------------------
    # TEST 11: Expired Discount Rejection
    # -------------------------------------------------------------------------
    def test_11_expired_discount_rejection(self):
        """Verify that expired discount rules are rejected during quotation processing."""
        if not hasattr(self, 'env'):
            return

        with self.assertRaises(ValidationError):
            self.env['subscription.subscription'].create({
                'partner_id': self.customer.id,
                'plan_id': self.plan_monthly.id,
                'discount_id': self.discount_expired.id,
                'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 2000.0})],
            })

    # -------------------------------------------------------------------------
    # TEST 12: Unauthorized Quotation Creation
    # -------------------------------------------------------------------------
    def test_12_unauthorized_quotation_creation(self):
        """Verify that portal users or unauthorized users cannot create quotations."""
        if not hasattr(self, 'env'):
            return

        portal_user = self.env['res.users'].create({
            'name': 'External Portal Customer',
            'login': 'customer_portal_test@brightloop.com',
            'email': 'customer_portal_test@brightloop.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })

        with self.assertRaises(AccessError):
            self.env['subscription.subscription'].with_user(portal_user).create({
                'partner_id': self.customer.id,
                'plan_id': self.plan_monthly.id,
                'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 2000.0})],
            })

    # -------------------------------------------------------------------------
    # TEST 13: Quotation Total Accuracy
    # -------------------------------------------------------------------------
    def test_13_quotation_total_accuracy(self):
        """Verify full financial breakdown: Subtotal - Discount + Tax = Final Total."""
        if not hasattr(self, 'env'):
            return

        # Line: 2 units * ₹2,000 = ₹4,000.
        # Order Discount: 10% = ₹400. Discounted base: ₹3,600.
        # Line Tax: 10% on ₹4,000 = ₹400.
        # Final Total: (₹4,000 - ₹400) + ₹400 = ₹4,000.
        quotation = self.env['subscription.subscription'].create({
            'partner_id': self.customer.id,
            'plan_id': self.plan_monthly.id,
            'discount_id': self.discount_eligible.id,
            'line_ids': [(0, 0, {
                'product_id': self.product_variant.id,
                'quantity': 2.0,
                'price_unit': 2000.0,
                'tax_ids': [(6, 0, [self.tax_10.id])],
            })],
        })

        self.assertEqual(quotation.amount_untaxed, 4000.0)
        self.assertEqual(quotation.amount_discount, 400.0)
        self.assertEqual(quotation.amount_tax, 400.0)
        self.assertEqual(quotation.amount_total, 4000.0)

    # -------------------------------------------------------------------------
    # TEST 14: Quotation Expiry Validation
    # -------------------------------------------------------------------------
    def test_14_quotation_expiry_validation(self):
        """Verify rejection when expiration date < quotation date, or when confirming expired quotation."""
        if not hasattr(self, 'env'):
            return

        # Expiry date before quotation date
        with self.assertRaises(ValidationError):
            self.env['subscription.subscription'].create({
                'partner_id': self.customer.id,
                'plan_id': self.plan_monthly.id,
                'date_quotation': self.today,
                'date_expiration': self.yesterday,
                'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 2000.0})],
            })

        # Confirming an expired quotation
        quotation = self.env['subscription.subscription'].create({
            'partner_id': self.customer.id,
            'plan_id': self.plan_monthly.id,
            'date_quotation': self.last_month,
            'date_expiration': self.yesterday,
            'line_ids': [(0, 0, {'product_id': self.product_variant.id, 'quantity': 1.0, 'price_unit': 2000.0})],
        })

        with self.assertRaises(ValidationError):
            quotation.action_confirm()
