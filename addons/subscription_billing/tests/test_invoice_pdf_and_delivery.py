# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

import json
import unittest
from datetime import date, datetime
from addons.subscription_billing.models.invoice_pdf_generator import (
    InvoicePDFGenerator,
    REPORTLAB_AVAILABLE,
)
from addons.subscription_billing.models.invoice_calculator import InvoiceCalculator


class MockPartner:
    def __init__(self, name="Northwind Co.", email="billing@northwind.io", phone="+1 555-0101",
                 street="1200 Pine St, Suite 400", city="Seattle", zip_code="98101", vat="US-98129034"):
        self.id = 1
        self.name = name
        self.display_name = name
        self.email = email
        self.phone = phone
        self.mobile = phone
        self.street = street
        self.city = city
        self.zip = zip_code
        self.vat = vat
        self.country_id = type('Country', (), {'name': 'United States'})()


class MockCompany:
    def __init__(self):
        self.id = 1
        self.name = "Odoo Subscription Management"
        self.email = "billing@odoo-subscription.com"
        self.phone = "+1 (555) 019-2834"
        self.vat = "US-94819284"


class MockInvoiceLine:
    def __init__(self, name="Pro SaaS Seat", quantity=2.0, price_unit=50.0, discount=10.0, price_subtotal=90.0):
        self.id = 1
        self.name = name
        self.quantity = quantity
        self.price_unit = price_unit
        self.discount = discount
        self.price_subtotal = price_subtotal
        self.product_id = type('Product', (), {'name': name})()


class MockPayment:
    def __init__(self, name="PAY-1001", payment_date="2026-10-15", amount=50.0, method="Credit Card", ref="CC-9012"):
        self.id = 1
        self.name = name
        self.payment_date = payment_date
        self.date = payment_date
        self.amount = amount
        self.payment_reference = ref
        self.ref = ref
        self.journal_id = type('Journal', (), {'name': method})()
        self.notes = "Partial payment received"


class MockHistoryRecord:
    def __init__(self, vals):
        self.id = vals.get('id', 1)
        self.move_id = vals.get('move_id')
        self.timestamp = vals.get('timestamp') or datetime.now()
        self.user_id = vals.get('user_id')
        self.user_name = vals.get('user_name', 'Admin')
        self.action = vals.get('action')
        self.previous_status = vals.get('previous_status')
        self.current_status = vals.get('current_status')
        self.details = vals.get('details', '')


class MockInvoiceRecord:
    """Mock simulating an account.move record with full PDF and delivery capabilities."""

    def __init__(self, name="INV-2026-0042", partner=..., status='confirmed', amt=118.0, lines=None):
        self.id = 42
        self.name = name
        self.partner_id = MockPartner() if partner is ... else partner
        self.company_id = MockCompany()
        self.currency_id = type('Currency', (), {'name': 'USD', 'symbol': '$'})()
        self.invoice_date = date(2026, 10, 31)
        self.invoice_date_due = date(2026, 11, 15)
        self.invoice_origin = "Subscription SUB-1001"
        self.invoice_status = status
        self.state = status
        self.payment_state = 'not_paid' if status != 'paid' else 'paid'
        self.amount_untaxed = 100.0
        self.amount_tax = 18.0
        self.amount_total = amt
        self.amount_paid = 0.0 if status != 'paid' else amt
        self.amount_residual = amt if status != 'paid' else 0.0
        self.invoice_line_ids = lines if lines is not None else [MockInvoiceLine()]
        self.line_ids = self.invoice_line_ids
        self.payment_ids = []
        self.history_ids = []
        self.invoice_sent = False
        self.invoice_sent_date = None
        self.invoice_recipient_email = None
        self.invoice_delivery_status = 'not_sent'
        self.invoice_delivery_error = False
        self.subscription_calculation_details = None

    def ensure_one(self):
        return True

    def write(self, vals):
        for k, v in vals.items():
            setattr(self, k, v)
        return True

    def _log_history(self, action, previous_status, current_status, details, **kwargs):
        vals = {
            'action': action,
            'previous_status': previous_status,
            'current_status': current_status,
            'details': details,
            'timestamp': datetime.now(),
            'user_name': 'Admin User',
        }
        self.history_ids.append(MockHistoryRecord(vals))

    def generate_invoice_pdf(self):
        self.ensure_one()
        return InvoicePDFGenerator.generate_pdf(self)

    def get_invoice_pdf_data(self):
        self.ensure_one()
        return InvoicePDFGenerator.extract_invoice_data(self)

    def validate_invoice_completeness(self):
        errors = []
        if not self.partner_id:
            errors.append("Missing customer information: No partner assigned.")
        elif not (getattr(self.partner_id, 'name', '') or getattr(self.partner_id, 'display_name', '')):
            errors.append("Missing customer information: Customer has no name.")

        lines = self.invoice_line_ids or self.line_ids
        if not lines:
            errors.append("Missing product information: Invoice contains no line items.")
        else:
            for idx, line in enumerate(lines, 1):
                qty = getattr(line, 'quantity', 0.0)
                if qty <= 0:
                    errors.append(f"Line #{idx} has invalid quantity ({qty}). Quantity must be greater than zero.")
                desc = getattr(line, 'name', '') or getattr(getattr(line, 'product_id', None), 'name', '')
                if not desc:
                    errors.append(f"Line #{idx} has missing product description.")

        if self.amount_total < 0:
            errors.append(f"Invoice total amount cannot be negative ({self.amount_total}).")

        if not self.invoice_date_due:
            errors.append("Missing payment due date.")

        return errors

    def action_send_invoice(self, recipient_email=None, subject=None, body=None):
        if self.invoice_status == 'draft':
            raise ValueError(f"Draft invoice '{self.name}' cannot be sent to the customer. Please confirm the invoice before sending.")

        if self.invoice_status == 'cancel':
            raise ValueError(f"Cannot send cancelled invoice '{self.name}'.")

        email_to = (recipient_email or (self.partner_id.email if self.partner_id else '') or '').strip()
        if not email_to or '@' not in email_to:
            customer_name = self.partner_id.name if self.partner_id else 'Unassigned'
            self.write({
                'invoice_delivery_status': 'failed',
                'invoice_delivery_error': f"Customer '{customer_name}' does not have a valid email address.",
            })
            raise ValueError(f"Cannot send invoice '{self.name}': Customer '{customer_name}' does not have a valid email address.")

        pdf_content = self.generate_invoice_pdf()
        assert pdf_content.startswith(b'%PDF'), "PDF content must be valid"

        self.write({
            'invoice_sent': True,
            'invoice_sent_date': datetime.now(),
            'invoice_recipient_email': email_to,
            'invoice_delivery_status': 'sent',
            'invoice_delivery_error': False,
        })
        log_detail = f"Invoice sent to customer {self.partner_id.name} ({email_to}). PDF attached."
        if subject:
            log_detail += f" Subject: {subject}"
        self._log_history('send', self.invoice_status, self.invoice_status, log_detail)
        return True

    def action_download_invoice(self):
        if self.invoice_status == 'cancel':
            raise ValueError(f"Cannot download cancelled invoice '{self.name}'.")
        self._log_history('download', self.invoice_status, self.invoice_status, "Invoice PDF downloaded.")
        return {
            'type': 'ir.actions.act_url',
            'url': f'/admin/api/invoice/{self.id}/pdf',
            'target': 'self',
        }

    def action_print_invoice(self):
        if self.invoice_status == 'cancel':
            raise ValueError(f"Cannot print cancelled invoice '{self.name}'.")
        self._log_history('print', self.invoice_status, self.invoice_status, "Invoice document printed.")
        return True


class TestInvoicePDFAndDelivery(unittest.TestCase):
    """Test suite covering PDF generation, formatting, customer data, and email delivery."""

    def setUp(self):
        self.partner = MockPartner(
            name="Acme Global Inc.",
            email="accounting@acmeglobal.com",
            phone="+1 (555) 012-3456",
            street="742 Evergreen Terrace",
            city="Springfield",
            zip_code="97477",
            vat="US-99887766"
        )
        self.line1 = MockInvoiceLine(name="SaaS Enterprise Subscription", quantity=1.0, price_unit=1000.0, discount=10.0, price_subtotal=900.0)
        self.line2 = MockInvoiceLine(name="24/7 Dedicated Support", quantity=2.0, price_unit=100.0, discount=0.0, price_subtotal=200.0)
        self.invoice = MockInvoiceRecord(
            name="INV-2026-9001",
            partner=self.partner,
            status='confirmed',
            amt=1298.0,
            lines=[self.line1, self.line2]
        )
        self.invoice.amount_untaxed = 1100.0
        self.invoice.amount_tax = 198.0
        self.invoice.amount_residual = 1298.0

    # -------------------------------------------------------------------------
    # 1. PDF Generation & Format Integrity
    # -------------------------------------------------------------------------
    def test_01_generate_invoice_pdf_success(self):
        """Verify PDF generator produces a valid %PDF binary stream with non-trivial size."""
        pdf_bytes = self.invoice.generate_invoice_pdf()
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'), "Generated file must start with %PDF header")
        self.assertGreater(len(pdf_bytes), 1000, "PDF must contain content and structure (> 1KB)")

    def test_02_pdf_contains_invoice_number_and_date(self):
        """Verify extracted data and PDF generation include the invoice number, date, and due date."""
        data = self.invoice.get_invoice_pdf_data()
        self.assertEqual(data['number'], "INV-2026-9001")
        self.assertEqual(data['date'], "2026-10-31")
        self.assertEqual(data['due_date'], "2026-11-15")
        self.assertEqual(data['status_label'], "CONFIRMED")

    # -------------------------------------------------------------------------
    # 2. Customer Details Completeness
    # -------------------------------------------------------------------------
    def test_03_pdf_contains_full_customer_details(self):
        """Verify customer details (name, email, phone, street, city, VAT) are extracted."""
        data = self.invoice.get_invoice_pdf_data()
        cust = data['customer']
        self.assertEqual(cust['name'], "Acme Global Inc.")
        self.assertEqual(cust['email'], "accounting@acmeglobal.com")
        self.assertEqual(cust['phone'], "+1 (555) 012-3456")
        self.assertEqual(cust['street'], "742 Evergreen Terrace")
        self.assertEqual(cust['city'], "Springfield")
        self.assertEqual(cust['zip'], "97477")
        self.assertEqual(cust['vat'], "US-99887766")

    def test_04_fallback_for_missing_customer_fields(self):
        """Verify missing customer info gracefully falls back to sensible defaults without crashing."""
        minimal_partner = MockPartner(name="Solo Trader", email=None, phone=None, street=None, city=None, vat=None)
        inv = MockInvoiceRecord(name="INV-2026-9002", partner=minimal_partner)
        data = inv.get_invoice_pdf_data()
        self.assertEqual(data['customer']['name'], "Solo Trader")
        self.assertEqual(data['customer']['email'], "")
        # PDF generation should succeed without error
        pdf = inv.generate_invoice_pdf()
        self.assertTrue(pdf.startswith(b'%PDF'))

    # -------------------------------------------------------------------------
    # 3. Product Descriptions and Quantities
    # -------------------------------------------------------------------------
    def test_05_pdf_contains_product_descriptions_and_quantities(self):
        """Verify line items include product names, quantities, unit prices, discounts, and subtotals."""
        data = self.invoice.get_invoice_pdf_data()
        self.assertEqual(len(data['lines']), 2)
        l1 = data['lines'][0]
        self.assertEqual(l1['name'], "SaaS Enterprise Subscription")
        self.assertEqual(l1['quantity'], 1.0)
        self.assertEqual(l1['price_unit'], 1000.0)
        self.assertEqual(l1['discount_str'], "10%")
        self.assertEqual(l1['subtotal'], 900.0)

        l2 = data['lines'][1]
        self.assertEqual(l2['name'], "24/7 Dedicated Support")
        self.assertEqual(l2['quantity'], 2.0)
        self.assertEqual(l2['price_unit'], 100.0)
        self.assertEqual(l2['subtotal'], 200.0)

    def test_06_snapshot_preservation_in_pdf_extraction(self):
        """Verify that when a historical calculation snapshot exists, PDF generator uses it faithfully."""
        snapshot = {
            'currency': 'USD',
            'amount_untaxed': 450.0,
            'amount_tax': 81.0,
            'amount_total': 531.0,
            'lines': [
                {
                    'product_name': 'Historical Plan A',
                    'quantity': 3.0,
                    'price_unit': 150.0,
                    'discount_percent': 0.0,
                    'discount_fixed': 0.0,
                    'subtotal': 450.0,
                    'tax_details': [{'name': 'VAT 18%', 'amount': 81.0}],
                    'line_total': 531.0,
                }
            ]
        }
        self.invoice.subscription_calculation_details = json.dumps(snapshot)
        data = self.invoice.get_invoice_pdf_data()
        self.assertEqual(len(data['lines']), 1)
        self.assertEqual(data['lines'][0]['name'], 'Historical Plan A')
        self.assertEqual(data['lines'][0]['quantity'], 3.0)
        self.assertEqual(data['totals']['untaxed'], 450.0)
        self.assertEqual(data['totals']['tax'], 81.0)
        self.assertEqual(data['totals']['total'], 531.0)

    # -------------------------------------------------------------------------
    # 4. Subtotal, Discounts, Taxes, and Final Invoice Amount
    # -------------------------------------------------------------------------
    def test_07_display_subtotal_discounts_taxes_and_total(self):
        """Verify subtotal (untaxed), tax amount, and total are accurately exposed."""
        data = self.invoice.get_invoice_pdf_data()
        totals = data['totals']
        self.assertEqual(totals['untaxed'], 1100.0)
        self.assertEqual(totals['tax'], 198.0)
        self.assertEqual(totals['total'], 1298.0)
        self.assertEqual(totals['residual'], 1298.0)
        self.assertEqual(totals['paid'], 0.0)

    # -------------------------------------------------------------------------
    # 5. Payment Details, Due Date, and Recorded Payment History
    # -------------------------------------------------------------------------
    def test_08_include_payment_details_and_due_date(self):
        """Verify payment instructions and due date are included."""
        data = self.invoice.get_invoice_pdf_data()
        self.assertEqual(data['due_date'], "2026-11-15")
        # Check company details for wire remit
        self.assertTrue(data['company']['name'])
        self.assertTrue(data['company']['email'])

    def test_09_include_recorded_payment_receipts(self):
        """Verify that when payments are recorded, they appear in the PDF payments table."""
        pay1 = MockPayment(name="PAY-8801", payment_date="2026-11-01", amount=500.0, method="Bank Transfer", ref="TXN-9912")
        self.invoice.payment_ids = [pay1]
        self.invoice.amount_paid = 500.0
        self.invoice.amount_residual = 798.0

        data = self.invoice.get_invoice_pdf_data()
        self.assertEqual(len(data['payments']), 1)
        p = data['payments'][0]
        self.assertEqual(p['number'], "PAY-8801")
        self.assertEqual(p['date'], "2026-11-01")
        self.assertEqual(p['amount'], 500.0)
        self.assertEqual(p['ref'], "TXN-9912")
        self.assertEqual(data['totals']['paid'], 500.0)
        self.assertEqual(data['totals']['residual'], 798.0)

        pdf = self.invoice.generate_invoice_pdf()
        self.assertTrue(pdf.startswith(b'%PDF'))

    # -------------------------------------------------------------------------
    # 6. Download and Print Functionality
    # -------------------------------------------------------------------------
    def test_10_download_functionality_and_url(self):
        """Verify action_download_invoice generates URL and records download event in history."""
        action = self.invoice.action_download_invoice()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertIn('/admin/api/invoice/42/pdf', action['url'])
        self.assertEqual(len(self.invoice.history_ids), 1)
        self.assertEqual(self.invoice.history_ids[0].action, 'download')

    def test_11_print_functionality_and_history(self):
        """Verify action_print_invoice logs print event in history."""
        res = self.invoice.action_print_invoice()
        self.assertTrue(res)
        self.assertEqual(len(self.invoice.history_ids), 1)
        self.assertEqual(self.invoice.history_ids[0].action, 'print')

    def test_12_download_and_print_disallowed_on_cancelled_invoice(self):
        """Verify cancelled invoices cannot be downloaded or printed."""
        self.invoice.invoice_status = 'cancel'
        with self.assertRaises(ValueError) as cm:
            self.invoice.action_download_invoice()
        self.assertIn("Cannot download cancelled invoice", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            self.invoice.action_print_invoice()
        self.assertIn("Cannot print cancelled invoice", str(cm.exception))

    # -------------------------------------------------------------------------
    # 7. Invoice Email Sending & Delivery Verification
    # -------------------------------------------------------------------------
    def test_13_send_invoice_email_success(self):
        """Verify invoice sending dispatches PDF, updates sent flags, and creates audit log."""
        self.assertTrue(self.invoice.action_send_invoice())
        self.assertTrue(self.invoice.invoice_sent)
        self.assertIsNotNone(self.invoice.invoice_sent_date)
        self.assertEqual(self.invoice.invoice_recipient_email, "accounting@acmeglobal.com")
        self.assertEqual(self.invoice.invoice_delivery_status, "sent")
        self.assertFalse(self.invoice.invoice_delivery_error)

        self.assertEqual(len(self.invoice.history_ids), 1)
        h = self.invoice.history_ids[0]
        self.assertEqual(h.action, 'send')
        self.assertIn("accounting@acmeglobal.com", h.details)
        self.assertIn("PDF attached", h.details)

    def test_14_send_invoice_custom_recipient_and_subject(self):
        """Verify sending to explicit recipient email and subject line."""
        custom_email = "direct_cfo@acmeglobal.com"
        subject = "Official Invoice INV-2026-9001 Settlement Request"
        self.assertTrue(self.invoice.action_send_invoice(recipient_email=custom_email, subject=subject))
        self.assertEqual(self.invoice.invoice_recipient_email, custom_email)
        self.assertIn(custom_email, self.invoice.history_ids[0].details)
        self.assertIn(subject, self.invoice.history_ids[0].details)

    def test_15_send_invoice_fails_on_draft(self):
        """Verify draft invoices cannot be dispatched via email."""
        self.invoice.invoice_status = 'draft'
        with self.assertRaises(ValueError) as cm:
            self.invoice.action_send_invoice()
        self.assertIn("Draft invoice", str(cm.exception))
        self.assertIn("cannot be sent", str(cm.exception))

    def test_16_send_invoice_fails_on_cancelled(self):
        """Verify cancelled invoices cannot be sent."""
        self.invoice.invoice_status = 'cancel'
        with self.assertRaises(ValueError) as cm:
            self.invoice.action_send_invoice()
        self.assertIn("Cannot send cancelled invoice", str(cm.exception))

    def test_17_send_invoice_missing_email_records_delivery_failure(self):
        """Verify missing/invalid customer email prevents sending and updates delivery error status."""
        no_email_partner = MockPartner(name="Offline Store Ltd", email="")
        inv = MockInvoiceRecord(name="INV-2026-9999", partner=no_email_partner, status='confirmed')
        with self.assertRaises(ValueError) as cm:
            inv.action_send_invoice()
        self.assertIn("does not have a valid email address", str(cm.exception))
        self.assertEqual(inv.invoice_delivery_status, "failed")
        self.assertTrue(inv.invoice_delivery_error)
        self.assertFalse(inv.invoice_sent)

    # -------------------------------------------------------------------------
    # 8. Invoice Completeness Validation
    # -------------------------------------------------------------------------
    def test_18_validate_invoice_completeness_valid(self):
        """Verify complete invoice passes validation with zero errors."""
        errors = self.invoice.validate_invoice_completeness()
        self.assertEqual(len(errors), 0, f"Expected 0 errors, got: {errors}")

    def test_19_validate_invoice_completeness_detects_missing_lines_and_customer(self):
        """Verify validation catches missing customer and empty lines."""
        broken_inv = MockInvoiceRecord(name="INV-ERR-1", partner=None, lines=[])
        errors = broken_inv.validate_invoice_completeness()
        self.assertTrue(any("Missing customer information" in e for e in errors))
        self.assertTrue(any("Missing product information" in e for e in errors))

    # -------------------------------------------------------------------------
    # 9. Standalone Dict Input to PDF Generator
    # -------------------------------------------------------------------------
    def test_20_pdf_generator_raw_dict_support(self):
        """Verify generator supports raw dictionary input for API endpoints / frontend serialization."""
        dict_inv = {
            'id': 100,
            'name': 'INV-JSON-001',
            'invoice_date': '2026-10-31',
            'invoice_date_due': '2026-11-20',
            'invoice_status': 'confirmed',
            'partner_id': {
                'name': 'Web Client Ltd',
                'email': 'client@web.com',
                'phone': '+1 555-9988',
                'street': '500 Tech Blvd',
                'city': 'San Jose',
                'vat': 'US-11223344',
            },
            'lines': [
                {'desc': 'Cloud Compute Instance', 'qty': 2.0, 'unitPrice': 150.0, 'disc': 0, 'tax': 18, 'subtotal': 300.0}
            ],
            'amount_untaxed': 300.0,
            'amount_tax': 54.0,
            'amount_total': 354.0,
            'amount_paid': 0.0,
            'amount_residual': 354.0,
        }
        pdf = InvoicePDFGenerator.generate_pdf(dict_inv)
        self.assertTrue(pdf.startswith(b'%PDF'))
