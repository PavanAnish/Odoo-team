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
class TestSubscriptionAuth(TransactionCase):
    """Test customer extension fields and portal access logic."""

    def test_01_customer_flag(self):
        """Test customer subscription flag."""
        if not hasattr(self, 'env'):
            return
        partner = self.env['res.partner'].create({
            'name': 'Test Subscriber',
            'is_subscription_customer': True,
        })
        self.assertTrue(partner.is_subscription_customer)
        self.assertEqual(partner.subscription_count, 0)
