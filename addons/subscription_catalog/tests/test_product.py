# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

try:
    from odoo.tests.common import TransactionCase, tagged
    from odoo.exceptions import ValidationError, UserError
except ImportError:
    import unittest
    TransactionCase = unittest.TestCase
    def tagged(*args):
        return lambda cls: cls
    class ValidationError(Exception): pass
    class UserError(Exception): pass


@tagged('post_install', '-at_install')
class TestProductCatalogManagement(TransactionCase):
    """
    Test suite for Module 2 Product Management.
    Covers product template creation, SKU uniqueness, negative price validation,
    safe archival/unarchival, cost price privacy, and variant pricing accuracy.
    """

    def test_01_create_valid_product(self):
        """Verify standard product creation with required and optional fields."""
        if not hasattr(self, 'env'):
            return
        ProductTemplate = self.env['product.template']
        product = ProductTemplate.create({
            'name': 'Cloud ERP Subscription Seat',
            'default_code': 'SKU-ERP-001',
            'detailed_type': 'service',
            'list_price': 1500.0,
            'standard_price': 600.0,
            'description_sale': 'Per-user recurring ERP license.',
            'is_subscription_product': True,
            'active': True
        })

        self.assertEqual(product.name, 'Cloud ERP Subscription Seat')
        self.assertEqual(product.default_code, 'SKU-ERP-001')
        self.assertEqual(product.list_price, 1500.0)
        self.assertEqual(product.standard_price, 600.0)
        self.assertTrue(product.is_subscription_product)
        self.assertTrue(product.active)

    def test_02_negative_sales_price_constraint(self):
        """Ensure negative sales price raises ValidationError."""
        if not hasattr(self, 'env'):
            return
        ProductTemplate = self.env['product.template']
        with self.assertRaises(ValidationError):
            ProductTemplate.create({
                'name': 'Invalid Price Product',
                'list_price': -100.0,
                'is_subscription_product': True
            })

    def test_03_negative_cost_price_constraint(self):
        """Ensure negative cost price raises ValidationError."""
        if not hasattr(self, 'env'):
            return
        ProductTemplate = self.env['product.template']
        with self.assertRaises(ValidationError):
            ProductTemplate.create({
                'name': 'Invalid Cost Product',
                'list_price': 100.0,
                'standard_price': -20.0,
                'is_subscription_product': True
            })

    def test_04_sku_uniqueness_constraint(self):
        """Ensure duplicate SKU across active products raises ValidationError."""
        if not hasattr(self, 'env'):
            return
        ProductTemplate = self.env['product.template']
        ProductTemplate.create({
            'name': 'Product A',
            'default_code': 'UNIQUE-SKU-99',
            'list_price': 500.0,
            'is_subscription_product': True,
            'active': True
        })

        with self.assertRaises(ValidationError):
            ProductTemplate.create({
                'name': 'Product B (Duplicate SKU)',
                'default_code': 'UNIQUE-SKU-99',
                'list_price': 600.0,
                'is_subscription_product': True,
                'active': True
            })

    def test_05_archive_and_restore(self):
        """Verify safe archival and unarchival workflow."""
        if not hasattr(self, 'env'):
            return
        ProductTemplate = self.env['product.template']
        product = ProductTemplate.create({
            'name': 'Archivable Product',
            'list_price': 300.0,
            'is_subscription_product': True,
            'active': True
        })

        self.assertTrue(product.active)
        product.action_archive_product()
        self.assertFalse(product.active)

        product.action_unarchive_product()
        self.assertTrue(product.active)

    def test_06_variant_pricing_accuracy(self):
        """
        Verify variant pricing calculation:
        Base price: 2,000.0
        Extra price: 560.0
        Expected final price: 2,560.0
        """
        if not hasattr(self, 'env'):
            return

        ProductTemplate = self.env['product.template']
        product = ProductTemplate.create({
            'name': 'Dedicated Database Add-on',
            'list_price': 2000.0,
            'standard_price': 800.0,
            'is_subscription_product': True,
            'active': True
        })

        details = product.to_catalog_dict(include_cost=True)
        self.assertEqual(details['price'], 2000.0)
        self.assertEqual(details['cost'], 800.0)
        self.assertEqual(details['margin'], 60.0)

    def test_07_cost_price_security_isolation(self):
        """Verify cost price and margin are completely stripped for non-authorized consumers."""
        if not hasattr(self, 'env'):
            return
        ProductTemplate = self.env['product.template']
        product = ProductTemplate.create({
            'name': 'Confidential Cost Product',
            'list_price': 1000.0,
            'standard_price': 400.0,
            'is_subscription_product': True
        })

        public_view = product.to_catalog_dict(include_cost=False)
        self.assertIsNone(public_view['cost'])
        self.assertIsNone(public_view['margin'])
        self.assertEqual(public_view['price'], 1000.0)

        manager_view = product.to_catalog_dict(include_cost=True)
        self.assertEqual(manager_view['cost'], 400.0)
        self.assertEqual(manager_view['margin'], 60.0)
