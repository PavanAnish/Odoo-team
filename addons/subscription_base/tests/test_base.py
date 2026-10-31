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
class TestSubscriptionBase(TransactionCase):
    """Test subscription base configuration and settings."""

    def test_01_groups_exist(self):
        """Ensure security groups are created properly."""
        if not hasattr(self, 'env'):
            return
        user_group = self.env.ref('subscription_base.group_subscription_user', raise_if_not_found=False)
        manager_group = self.env.ref('subscription_base.group_subscription_manager', raise_if_not_found=False)
        self.assertIsNotNone(user_group, "Subscription User group should exist")
        self.assertIsNotNone(manager_group, "Subscription Manager group should exist")
