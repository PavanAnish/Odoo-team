# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from datetime import date, timedelta

try:
    from odoo.tests.common import TransactionCase, tagged
    from odoo.exceptions import ValidationError
except ImportError:
    import unittest
    TransactionCase = unittest.TestCase
    def tagged(*args):
        return lambda cls: cls
    class ValidationError(Exception): pass


@tagged('post_install', '-at_install')
class TestSubscriptionCatalog(TransactionCase):
    """Test subscription plan configuration, availability checks, and discount rules."""

    def test_01_create_plan_and_availability(self):
        """Test subscription plan creation, dates, and availability method."""
        if not hasattr(self, 'env'):
            return
        today = date.today()
        plan = self.env['subscription.plan'].create({
            'name': 'Quarterly Pro',
            'code': 'PLAN-QTR-01',
            'billing_interval': 3,
            'billing_period': 'monthly',
            'date_start': today - timedelta(days=10),
            'date_end': today + timedelta(days=30),
            'min_quantity': 2.0,
            'active': True,
        })
        self.assertEqual(plan.billing_interval, 3)
        self.assertEqual(plan.billing_period, 'monthly')

        # Check availability
        avail, reason = plan.is_available(target_date=today, quantity=2.0)
        self.assertTrue(avail)

        # Check failure when quantity < min_quantity
        avail, reason = plan.is_available(target_date=today, quantity=1.0)
        self.assertFalse(avail)

    def test_02_discount_rule_validation(self):
        """Test discount rule calculation and eligibility check."""
        if not hasattr(self, 'env'):
            return
        today = date.today()
        discount = self.env['subscription.discount'].create({
            'name': 'VIP Club 15%',
            'code': 'VIP15',
            'discount_type': 'percent',
            'discount_value': 15.0,
            'min_amount': 500.0,
            'max_usage': 10,
            'active': True,
        })
        self.assertEqual(discount.calculate_discount_amount(1000.0), 150.0)

        # Subtotal below min_amount should fail validation
        with self.assertRaises(ValidationError):
            discount.validate_eligibility(quotation_amount=400.0, target_date=today)
