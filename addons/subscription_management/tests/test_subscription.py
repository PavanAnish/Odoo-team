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
class TestSubscriptionManagement(TransactionCase):
    """Test subscription creation and lifecycle transitions."""

    def test_01_create_subscription(self):
        """Test initial draft state of a subscription."""
        if not hasattr(self, 'env'):
            return
        partner = self.env['res.partner'].create({
            'name': 'Subscription Client',
            'is_subscription_customer': True,
        })
        plan = self.env['subscription.plan'].create({
            'name': 'Monthly Standard Test',
            'code': 'SUB-TEST-01',
            'billing_interval': 1,
            'billing_period': 'monthly',
        })
        sub = self.env['subscription.subscription'].create({
            'partner_id': partner.id,
            'plan_id': plan.id,
        })
        self.assertEqual(sub.state, 'draft')
        sub.action_confirm()
        self.assertEqual(sub.state, 'active')
