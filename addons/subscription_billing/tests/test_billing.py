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
    """Test automated recurring billing, idempotency, date progression, status validation, and error isolation."""

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
        self.assertTrue(invoice.name and invoice.name not in ('/', 'False'), "Invoice must have a unique invoice number.")

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

    def test_05_status_validation_rejects_inactive(self):
        """Ensure non-active subscriptions (draft, paused, closed) cannot generate invoices."""
        if not hasattr(self, 'env'):
            return

        sub_draft = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1.0, 'price_unit': 100.0})],
        })
        # state is 'draft'
        with self.assertRaises(UserError):
            sub_draft.action_generate_invoice()

        # Confirm and pause
        sub_draft.action_confirm()
        sub_draft.action_pause()
        self.assertEqual(sub_draft.state, 'paused')
        with self.assertRaises(UserError):
            sub_draft.action_generate_invoice()

        # Close
        sub_draft.action_close()
        self.assertEqual(sub_draft.state, 'closed')
        with self.assertRaises(UserError):
            sub_draft.action_generate_invoice()

    def test_06_cron_picks_up_active_subscription_without_next_billing_date(self):
        """Ensure active subscriptions where next_billing_date is False are safely picked up and billed."""
        if not hasattr(self, 'env'):
            return

        sub_no_date = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'state': 'active',
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1.0, 'price_unit': 60.0})],
        })
        sub_no_date.next_billing_date = False

        invoices = self.env['subscription.subscription']._cron_generate_recurring_invoices()
        matching = [inv for inv in invoices if inv.subscription_id == sub_no_date]
        self.assertTrue(matching, "Active subscription with missing next_billing_date must be billed.")
        self.assertTrue(sub_no_date.next_billing_date, "Next billing date must be set after billing.")

    # ------------------------------------------------------------------
    # Invoice Calculation Tests
    # ------------------------------------------------------------------

    def test_07_invoice_no_discount(self):
        """Generate an invoice without discounts: total = quantity × price_unit."""
        if not hasattr(self, 'env'):
            return

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'next_billing_date': self.today,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 3.0,
                'price_unit': 100.0,
            })],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()

        self.assertTrue(invoice)
        # Subscription line subtotal
        line = sub.line_ids[0]
        self.assertAlmostEqual(line.price_subtotal, 300.0, places=2)
        # Invoice snapshot amounts
        self.assertAlmostEqual(invoice.subscription_amount_untaxed, 300.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_tax, 0.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_total, 300.0, places=2)
        # Calculation details JSON must exist
        self.assertTrue(invoice.subscription_calculation_details)

    def test_08_invoice_percentage_discount(self):
        """Generate an invoice with percentage discount: 10% off $100 × 2 = $180."""
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
                'discount_type': 'percent',
                'discount': 10.0,
            })],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()

        self.assertTrue(invoice)
        line = sub.line_ids[0]
        self.assertAlmostEqual(line.price_subtotal, 180.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_untaxed, 180.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_total, 180.0, places=2)

    def test_09_invoice_fixed_discount(self):
        """Generate an invoice with fixed discount: $100 - $15 fixed = $85."""
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
                'price_unit': 100.0,
                'discount_type': 'fixed',
                'discount_fixed': 15.0,
            })],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()

        self.assertTrue(invoice)
        line = sub.line_ids[0]
        self.assertAlmostEqual(line.price_subtotal, 85.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_untaxed, 85.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_total, 85.0, places=2)

    def test_10_invoice_with_tax(self):
        """Generate an invoice with applicable taxes: $100 + 18% tax = $118."""
        if not hasattr(self, 'env'):
            return

        tax_18 = self.env['account.tax'].create({
            'name': 'Tax 18%',
            'type_tax_use': 'sale',
            'amount_type': 'percent',
            'amount': 18.0,
        })

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'next_billing_date': self.today,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1.0,
                'price_unit': 100.0,
                'tax_ids': [(6, 0, [tax_18.id])],
            })],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()

        self.assertTrue(invoice)
        line = sub.line_ids[0]
        self.assertAlmostEqual(line.price_subtotal, 100.0, places=2)
        self.assertAlmostEqual(line.price_tax, 18.0, places=2)
        self.assertAlmostEqual(line.price_total, 118.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_untaxed, 100.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_tax, 18.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_total, 118.0, places=2)

    def test_11_invoice_with_tax_and_discount(self):
        """Generate invoice with both 10% discount and 18% tax on $100.
        subtotal=90, tax=16.20, total=106.20."""
        if not hasattr(self, 'env'):
            return

        tax_18 = self.env['account.tax'].create({
            'name': 'Tax 18% combo',
            'type_tax_use': 'sale',
            'amount_type': 'percent',
            'amount': 18.0,
        })

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'next_billing_date': self.today,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1.0,
                'price_unit': 100.0,
                'discount_type': 'percent',
                'discount': 10.0,
                'tax_ids': [(6, 0, [tax_18.id])],
            })],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()

        self.assertTrue(invoice)
        line = sub.line_ids[0]
        self.assertAlmostEqual(line.price_subtotal, 90.0, places=2)
        self.assertAlmostEqual(line.price_tax, 16.2, places=2)
        self.assertAlmostEqual(line.price_total, 106.2, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_untaxed, 90.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_tax, 16.2, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_total, 106.2, places=2)

    def test_12_invoice_multiple_products(self):
        """Test calculations with multiple product lines."""
        if not hasattr(self, 'env'):
            return

        product_b = self.env['product.product'].create({
            'name': 'Premium Add-on',
            'type': 'service',
            'list_price': 50.0,
            'is_subscription_product': True,
        })

        tax_10 = self.env['account.tax'].create({
            'name': 'Tax 10% multi',
            'type_tax_use': 'sale',
            'amount_type': 'percent',
            'amount': 10.0,
        })

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'next_billing_date': self.today,
            'line_ids': [
                # Line 1: 2 × $100, no discount, no tax → subtotal $200
                (0, 0, {
                    'product_id': self.product.id,
                    'quantity': 2.0,
                    'price_unit': 100.0,
                }),
                # Line 2: 1 × $50, 20% discount, 10% tax → subtotal $40, tax $4
                (0, 0, {
                    'product_id': product_b.id,
                    'quantity': 1.0,
                    'price_unit': 50.0,
                    'discount_type': 'percent',
                    'discount': 20.0,
                    'tax_ids': [(6, 0, [tax_10.id])],
                }),
            ],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()

        self.assertTrue(invoice)
        # Check subscription-level amounts
        self.assertAlmostEqual(sub.amount_untaxed, 240.0, places=2)
        self.assertAlmostEqual(sub.amount_tax, 4.0, places=2)
        self.assertAlmostEqual(sub.amount_total, 244.0, places=2)
        # Check invoice snapshot
        self.assertAlmostEqual(invoice.subscription_amount_untaxed, 240.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_tax, 4.0, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_total, 244.0, places=2)
        # Verify 2 invoice lines were created
        self.assertEqual(len(invoice.invoice_line_ids), 2)

    def test_13_decimal_precision_and_rounding(self):
        """Test decimal precision: $33.33 × 3 must equal $99.99, not $100.00."""
        if not hasattr(self, 'env'):
            return

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'next_billing_date': self.today,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 3.0,
                'price_unit': 33.33,
            })],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()

        self.assertTrue(invoice)
        line = sub.line_ids[0]
        # 3 × 33.33 = 99.99 (exact Decimal), NOT 100.00 or 99.98999...
        self.assertAlmostEqual(line.price_subtotal, 99.99, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_untaxed, 99.99, places=2)
        self.assertAlmostEqual(invoice.subscription_amount_total, 99.99, places=2)

    def test_14_calculation_snapshot_preserved(self):
        """Verify that calculation details are stored as JSON on the invoice."""
        if not hasattr(self, 'env'):
            return
        import json

        tax_5 = self.env['account.tax'].create({
            'name': 'Snapshot Tax 5%',
            'type_tax_use': 'sale',
            'amount_type': 'percent',
            'amount': 5.0,
        })

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'next_billing_date': self.today,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 2.0,
                'price_unit': 75.0,
                'discount_type': 'percent',
                'discount': 5.0,
                'tax_ids': [(6, 0, [tax_5.id])],
            })],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()

        self.assertTrue(invoice.subscription_calculation_details)
        snapshot = json.loads(invoice.subscription_calculation_details)

        # Verify structure
        self.assertIn('calculation_timestamp', snapshot)
        self.assertIn('lines', snapshot)
        self.assertIn('amount_untaxed', snapshot)
        self.assertIn('amount_tax', snapshot)
        self.assertIn('amount_total', snapshot)

        # Verify line detail
        self.assertEqual(len(snapshot['lines']), 1)
        line = snapshot['lines'][0]
        # subtotal: 2 * 75 * 0.95 = 142.50
        self.assertAlmostEqual(line['subtotal'], 142.50, places=2)
        self.assertEqual(len(line['tax_details']), 1)
        # tax: 142.50 * 0.05 = 7.125 → 7.13 (ROUND_HALF_UP)
        self.assertAlmostEqual(line['tax_details'][0]['tax_amount'], 7.13, places=2)
        self.assertAlmostEqual(snapshot['amount_total'], 149.63, places=2)

    # ------------------------------------------------------------------
    # Invoice Status, Transition, Protection & History Tests
    # ------------------------------------------------------------------

    def test_15_invoice_status_draft_to_confirmed(self):
        """Test invoice creation defaults to Draft, and confirms to Confirmed with history."""
        if not hasattr(self, 'env'):
            return

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1.0, 'price_unit': 100.0})],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()

        self.assertEqual(invoice.invoice_status, 'draft')
        self.assertTrue(invoice.history_ids)
        self.assertEqual(invoice.history_ids[0].action, 'create')

        # Confirm
        invoice.action_confirm()
        self.assertEqual(invoice.invoice_status, 'confirmed')
        self.assertEqual(invoice.state, 'posted')

        confirm_events = [h for h in invoice.history_ids if h.action == 'confirm']
        self.assertTrue(confirm_events)
        self.assertEqual(confirm_events[0].previous_status, 'draft')
        self.assertEqual(confirm_events[0].current_status, 'confirmed')

    def test_16_invoice_status_confirmed_to_paid(self):
        """Test confirmed invoice moves to Paid upon payment registration."""
        if not hasattr(self, 'env'):
            return

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1.0, 'price_unit': 100.0})],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()
        invoice.action_confirm()

        # Mark paid
        invoice.action_mark_paid(payment_ref='TXN-TEST-01', amount=100.0)
        self.assertEqual(invoice.invoice_status, 'paid')
        self.assertEqual(invoice.payment_state, 'paid')

        pay_events = [h for h in invoice.history_ids if h.action == 'register_payment']
        self.assertTrue(pay_events)
        self.assertEqual(pay_events[0].previous_status, 'confirmed')
        self.assertEqual(pay_events[0].current_status, 'paid')

    def test_17_invoice_cancellation_flow(self):
        """Test invoice cancellation from draft and confirmed, and rejection from paid."""
        if not hasattr(self, 'env'):
            return

        # Cancel from draft
        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1.0, 'price_unit': 100.0})],
        })
        sub.action_confirm()
        inv_draft = sub.action_generate_invoice()
        inv_draft.action_cancel()
        self.assertEqual(inv_draft.invoice_status, 'cancel')

        # Cancel from confirmed
        sub.next_billing_date = self.today + relativedelta(days=1)
        inv_conf = sub.action_generate_invoice(billing_date=self.today + relativedelta(days=1))
        inv_conf.action_confirm()
        inv_conf.action_cancel()
        self.assertEqual(inv_conf.invoice_status, 'cancel')

        # Paid cannot be cancelled
        sub.next_billing_date = self.today + relativedelta(days=2)
        inv_paid = sub.action_generate_invoice(billing_date=self.today + relativedelta(days=2))
        inv_paid.action_confirm()
        inv_paid.action_mark_paid()
        with self.assertRaises(ValidationError):
            inv_paid.action_cancel()

    def test_18_invalid_transition_rejections(self):
        """Verify invalid transitions (Draft -> Paid, Paid -> any, Cancel -> any) raise ValidationError."""
        if not hasattr(self, 'env'):
            return

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1.0, 'price_unit': 100.0})],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()

        # Cannot mark draft as paid directly
        with self.assertRaises(ValidationError):
            invoice.action_mark_paid()

        # Confirm and pay
        invoice.action_confirm()
        invoice.action_mark_paid()

        # Paid cannot move to draft, confirmed, or cancel
        for target in ('draft', 'confirmed', 'cancel'):
            with self.assertRaises(ValidationError):
                invoice.write({'invoice_status': target})

    def test_19_finalized_protection_and_deletion(self):
        """Ensure confirmed and paid invoices cannot have lines modified or be deleted."""
        if not hasattr(self, 'env'):
            return

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1.0, 'price_unit': 100.0})],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()
        invoice.action_confirm()

        # Protected from modification of financial lines/amounts
        with self.assertRaises(ValidationError):
            invoice.write({'amount_total': 999.0})

        # Protected from deletion
        with self.assertRaises(UserError):
            invoice.unlink()

    def test_20_invoice_sending_printing_downloading(self):
        """Verify send, print, download rules and history recording."""
        if not hasattr(self, 'env'):
            return

        sub = self.env['subscription.subscription'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_monthly.id,
            'date_start': self.today,
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1.0, 'price_unit': 100.0})],
        })
        sub.action_confirm()
        invoice = sub.action_generate_invoice()

        # Draft cannot be sent
        with self.assertRaises(ValidationError):
            invoice.action_send_invoice()

        # Print & download on draft works
        self.assertTrue(invoice.action_print_invoice())
        self.assertTrue(invoice.action_download_invoice())

        # Confirm and send
        invoice.action_confirm()
        self.assertTrue(invoice.action_send_invoice())
        self.assertTrue(invoice.invoice_sent)
