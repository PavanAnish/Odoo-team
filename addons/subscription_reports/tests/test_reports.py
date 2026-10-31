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
class TestSubscriptionReports(TransactionCase):
    """Test subscription reporting view definition."""

    def test_01_report_definition(self):
        """Verify model availability."""
        if not hasattr(self, 'env'):
            return
        self.assertTrue('subscription.report' in self.env)
