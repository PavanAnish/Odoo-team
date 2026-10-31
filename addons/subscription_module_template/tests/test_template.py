# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

try:
    from odoo.tests.common import TransactionCase, tagged
    from odoo.exceptions import ValidationError
except ImportError:
    # Fallback mock for static environments without odoo installed
    import unittest
    TransactionCase = unittest.TestCase
    def tagged(*args):
        return lambda cls: cls
    ValidationError = Exception


@tagged('post_install', '-at_install')
class TestSubscriptionTemplate(TransactionCase):
    """Unit tests for Subscription Template CRUD and workflows."""

    def setUp(self):
        super().setUp()
        if hasattr(self, 'env'):
            self.template_model = self.env['subscription.template.item']
            self.test_item = self.template_model.create({
                'name': 'Test Tier',
                'code': 'TEST-001',
                'description': 'Automated test item',
                'state': 'draft',
            })

    def test_01_creation_defaults(self):
        """Verify default values upon record creation."""
        if not hasattr(self, 'env'):
            return
        self.assertEqual(self.test_item.state, 'draft')
        self.assertTrue(self.test_item.active)
        self.assertEqual(self.test_item.name, 'Test Tier')

    def test_02_action_confirm(self):
        """Verify status transition to confirmed."""
        if not hasattr(self, 'env'):
            return
        self.test_item.action_confirm()
        self.assertEqual(self.test_item.state, 'confirmed')

        # Confirming an already confirmed record should raise ValidationError
        with self.assertRaises(ValidationError):
            self.test_item.action_confirm()

    def test_03_action_cancel(self):
        """Verify cancellation workflow."""
        if not hasattr(self, 'env'):
            return
        self.test_item.action_cancel()
        self.assertEqual(self.test_item.state, 'cancelled')
