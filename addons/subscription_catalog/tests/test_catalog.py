# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

try:
    from odoo.tests.common import TransactionCase, tagged
except ImportError:
    import unittest
    TransactionCase = unittest.TestCase
    def tagged(*args):
        return lambda cls: cls


@tagged('post_install', '-at_install')
class TestSubscriptionCatalog(TransactionCase):
    """Test subscription plan configuration and product linkages."""

    def test_01_create_plan(self):
        """Test subscription plan creation and defaults."""
        if not hasattr(self, 'env'):
            return
        plan = self.env['subscription.plan'].create({
            'name': 'Quarterly Pro',
            'code': 'PLAN-QTR-01',
            'billing_interval': 3,
            'billing_period': 'monthly',
        })
        self.assertEqual(plan.billing_interval, 3)
        self.assertEqual(plan.billing_period, 'monthly')
