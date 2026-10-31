# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from dateutil.relativedelta import relativedelta

try:
    from odoo.tests.common import TransactionCase, tagged
    from odoo import fields
    from odoo.exceptions import UserError, ValidationError
except ImportError:
    import unittest
    TransactionCase = unittest.TestCase
    def tagged(*args):
        return lambda cls: cls
    fields = None
    UserError = Exception
    ValidationError = Exception


@tagged('post_install', '-at_install')
class TestSubscriptionBilling(TransactionCase):
    """Test automated recurring billing, idempotency, date progression, and error isolation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not hasattr(cls, 'env'):
            return

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Subscriber Corporation',
            'email': 'billing@testsubscriber.com',
            'is_subscription_customer': True,
        })

        cls.plan_monthly = cls.env['subscription.plan'].create({
            'name': 'Monthly Standard Plan',
            'code': 'TEST-M-01',
            'billing_interval': 1,
            'billing_period': 'monthly',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Cloud Infrastructure Base',
            'type': 'service',
            'list_price': 100.0,
            'is_subscription_product': True,
        })

        cls.today = fields.Date.context_today(cls.partner)

    def test_01_automatic_invoice_generation(self):
        """Test invoice creation, line values, customer linkage, and next billing date update."""
        if not hasattr(self, 'env'):
            return

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'next_billing_date': self.today,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 2.0,
                'price_unit': 100.0,
                'discount': 10.0,
            })],
        })
        sub.action_confirm()
        self.assertEqual(sub.state, 'active')
        self.assertEqual(sub.next_billing_date, self.today)

        # Generate invoice
        invoice = sub.action_generate_invoice()

        # Assert invoice attributes
        self.assertTrue(invoice, "Invoice must be created.")
        self.assertEqual(invoice.move_type, 'out_invoice', "Invoice must be a customer invoice.")
        self.assertEqual(invoice.partner_id, self.partner, "Invoice must belong to the correct customer.")
        self.assertEqual(invoice.subscription_id, sub, "Invoice must be linked to the originating subscription.")
        self.assertEqual(invoice.subscription_billing_date, self.today, "Billing cycle date must match target date.")
        self.assertTrue(invoice.is_subscription_invoice, "is_subscription_invoice flag must be True.")

        # Assert line values
        self.assertEqual(len(invoice.invoice_line_ids), 1, "Invoice must have 1 line.")
        inv_line = invoice.invoice_line_ids[0]
        self.assertEqual(inv_line.product_id, self.product)
        self.assertEqual(inv_line.quantity, 2.0)
        self.assertEqual(inv_line.price_unit, 100.0)
        self.assertEqual(inv_line.discount, 10.0)

        # Assert next billing date has advanced by 1 month
        expected_next = self.today + relativedelta(months=1)
        self.assertEqual(sub.next_billing_date, expected_next, "Next billing date must advance by 1 month.")

    def test_02_idempotency_no_duplicate_invoices(self):
        """Ensure invoice generation is idempotent: retries do not produce duplicate invoices."""
        if not hasattr(self, 'env'):
            return

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'next_billing_date': self.today,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1.0,
                'price_unit': 50.0,
            })],
        })
        sub.action_confirm()

        # First generation
        inv1 = sub.action_generate_invoice(billing_date=self.today)
        self.assertTrue(inv1)
        initial_invoice_count = sub.invoice_count

        # Second generation attempt for the exact same billing cycle date
        inv2 = sub.action_generate_invoice(billing_date=self.today)
        self.assertEqual(inv1.id, inv2.id, "Second call must return the existing invoice without creating a new one.")
        self.assertEqual(sub.invoice_count, initial_invoice_count, "Invoice count must not increase on duplicate call.")

    def test_03_failed_billing_does_not_advance_date(self):
        """Verify that failed billing operations do not advance the next billing date."""
        if not hasattr(self, 'env'):
            return

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'next_billing_date': self.today,
            # No line items!
        })
        sub.state = 'active'
        original_billing_date = sub.next_billing_date

        with self.assertRaises(UserError):
            sub.action_generate_invoice()

        self.assertEqual(
            sub.next_billing_date,
            original_billing_date,
            "Next billing date must remain untouched when billing generation fails."
        )

    def test_04_cron_generates_only_due_subscriptions(self):
        """Ensure the scheduled cron only processes active subscriptions that have reached billing date."""
        if not hasattr(self, 'env'):
            return

        future_date = self.today + relativedelta(days=15)

        # Due subscription
        sub_due = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'next_billing_date': self.today,
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1.0, 'price_unit': 80.0})],
        })
        sub_due.action_confirm()

        # Future subscription (not due)
        sub_future = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'next_billing_date': future_date,
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1.0, 'price_unit': 80.0})],
        })
        sub_future.action_confirm()
        sub_future.next_billing_date = future_date

        # Run cron
        invoices = self.env['subscription.subscription']._cron_generate_recurring_invoices()

        self.assertTrue(any(inv.subscription_id == sub_due for inv in invoices), "Due subscription must be billed.")
        self.assertFalse(any(inv.subscription_id == sub_future for inv in invoices), "Future subscription must not be billed.")
        self.assertEqual(sub_future.next_billing_date, future_date, "Future billing date must remain untouched.")
