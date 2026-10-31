# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

"""
Unit tests for Outstanding Balances, Payment Identification, Overdue Detection,
Cancelled Invoice Exclusion, and Financial Summaries.

Validates all 8 requirements:
1. Calculate total valid payments against each invoice (excluding cancelled payments).
2. Calculate remaining outstanding balance.
3. Identify fully paid invoices.
4. Identify partially paid invoices.
5. Identify unpaid invoices.
6. Detect overdue invoices using due dates (days overdue, status).
7. Update financial summaries accordingly (totals, collected, outstanding, overdue, counts).
8. Ensure cancelled invoices are excluded from outstanding calculations.
"""

import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from addons.subscription_billing.models.account_move import AccountMove


class MockPayment:
    def __init__(self, amount=100.0, state='posted', payment_date=None):
        self.amount = float(amount)
        self.state = state
        self.payment_date = payment_date or date.today()


class MockInvoiceRecord:
    """Mock record modeling AccountMove state and behavior."""

    def __init__(self, id=1, name="INV/2026/001", amount_total=200.0, invoice_status='confirmed',
                 invoice_date=None, invoice_date_due=None, payments=None):
        self.id = id
        self.name = name
        self.amount_total = float(amount_total)
        self.subscription_amount_total = float(amount_total)
        self.invoice_status = invoice_status
        self.state = 'posted' if invoice_status in ('confirmed', 'paid') else invoice_status
        self.invoice_date = invoice_date or date.today()
        self.invoice_date_due = invoice_date_due or date.today()
        self.payment_ids = payments or []
        self.amount_paid = 0.0
        self.amount_residual = float(amount_total)
        self.payment_state = 'not_paid'
        self.is_overdue = False
        self.days_overdue = 0
        self.overdue_status = 'not_due'
        self.is_fully_paid = False
        self.is_partially_paid = False
        self.is_unpaid = True
        self.history_ids = []

        self.env = SimpleNamespace(
            user=SimpleNamespace(id=1, name="Admin User"),
            context_today=lambda *args: date.today(),
            su=False
        )

        self._recompute()

    def filtered(self, fn):
        return [p for p in self.payment_ids if fn(p)]

    def ensure_one(self):
        return self

    def _recompute(self):
        AccountMove._compute_payments_and_residual([self])
        AccountMove._compute_overdue_status([self])

    def action_cancel(self):
        AccountMove.action_cancel([self])
        self._recompute()

    def write(self, vals):
        for k, v in vals.items():
            setattr(self, k, v)
        return True

    def _log_history(self, action, previous_status=None, current_status=None, details='', **kwargs):
        self.history_ids.append({
            'action': action,
            'previous_status': previous_status,
            'current_status': current_status,
            'details': details
        })


class TestBalanceAndOverdue(unittest.TestCase):
    """Test suite covering outstanding balance calculation, overdue detection,
    payment identification, cancelled invoice exclusion, and financial summaries."""

    def setUp(self):
        self.today = date.today()
        self.past_due_5_days = self.today - timedelta(days=5)
        self.past_due_15_days = self.today - timedelta(days=15)
        self.future_due_10_days = self.today + timedelta(days=10)

    # -------------------------------------------------------------------------
    # 1. Total Valid Payments & Outstanding Balance
    # -------------------------------------------------------------------------
    def test_01_total_valid_payments_excludes_cancelled_payments(self):
        """Valid payments must be summed while cancelled payments are strictly excluded."""
        payments = [
            MockPayment(amount=50.0, state='posted'),
            MockPayment(amount=30.0, state='posted'),
            MockPayment(amount=40.0, state='cancel'),  # Should be excluded
        ]
        inv = MockInvoiceRecord(amount_total=200.0, payments=payments)
        self.assertEqual(inv.amount_paid, 80.0)
        self.assertEqual(inv.amount_residual, 120.0)

    def test_02_remaining_outstanding_balance_calculation(self):
        """Remaining balance must equal total invoiced minus valid payments."""
        inv = MockInvoiceRecord(amount_total=500.0)
        self.assertEqual(inv.amount_residual, 500.0)

        inv.payment_ids.append(MockPayment(amount=175.50, state='posted'))
        inv._recompute()
        self.assertEqual(inv.amount_paid, 175.50)
        self.assertEqual(inv.amount_residual, 324.50)

    # -------------------------------------------------------------------------
    # 2. Payment Identification: Unpaid, Partially Paid, Fully Paid
    # -------------------------------------------------------------------------
    def test_03_identify_unpaid_invoices(self):
        """Invoices with 0 payments must be identified as unpaid."""
        inv = MockInvoiceRecord(amount_total=300.0)
        self.assertEqual(inv.payment_state, 'not_paid')
        self.assertTrue(inv.is_unpaid)
        self.assertFalse(inv.is_partially_paid)
        self.assertFalse(inv.is_fully_paid)
        self.assertTrue(AccountMove.is_invoice_unpaid(inv))
        self.assertFalse(AccountMove.is_invoice_partially_paid(inv))
        self.assertFalse(AccountMove.is_invoice_fully_paid(inv))

    def test_04_identify_partially_paid_invoices(self):
        """Invoices with payments > 0 but residual > 0 must be identified as partially paid."""
        payments = [MockPayment(amount=100.0, state='posted')]
        inv = MockInvoiceRecord(amount_total=300.0, payments=payments)
        self.assertEqual(inv.payment_state, 'partial')
        self.assertFalse(inv.is_unpaid)
        self.assertTrue(inv.is_partially_paid)
        self.assertFalse(inv.is_fully_paid)
        self.assertTrue(AccountMove.is_invoice_partially_paid(inv))
        self.assertFalse(AccountMove.is_invoice_unpaid(inv))
        self.assertFalse(AccountMove.is_invoice_fully_paid(inv))

    def test_05_identify_fully_paid_invoices(self):
        """Invoices with residual 0 and payments >= total must be identified as fully paid."""
        payments = [MockPayment(amount=300.0, state='posted')]
        inv = MockInvoiceRecord(amount_total=300.0, payments=payments)
        self.assertEqual(inv.payment_state, 'paid')
        self.assertEqual(inv.amount_residual, 0.0)
        self.assertFalse(inv.is_unpaid)
        self.assertFalse(inv.is_partially_paid)
        self.assertTrue(inv.is_fully_paid)
        self.assertTrue(AccountMove.is_invoice_fully_paid(inv))
        self.assertFalse(AccountMove.is_invoice_unpaid(inv))
        self.assertFalse(AccountMove.is_invoice_partially_paid(inv))

    # -------------------------------------------------------------------------
    # 3. Overdue Detection Using Due Dates
    # -------------------------------------------------------------------------
    def test_06_detect_overdue_invoices_past_due_date(self):
        """Confirmed invoices with residual > 0 and due date < today must be flagged as overdue."""
        inv = MockInvoiceRecord(
            amount_total=250.0,
            invoice_status='confirmed',
            invoice_date_due=self.past_due_5_days
        )
        self.assertTrue(inv.is_overdue)
        self.assertEqual(inv.days_overdue, 5)
        self.assertEqual(inv.overdue_status, 'overdue')

    def test_07_days_overdue_calculation_accuracy(self):
        """Days overdue must be calculated exactly as (today - due_date)."""
        inv = MockInvoiceRecord(
            amount_total=100.0,
            invoice_status='confirmed',
            invoice_date_due=self.past_due_15_days
        )
        self.assertTrue(inv.is_overdue)
        self.assertEqual(inv.days_overdue, 15)

    def test_08_not_overdue_when_due_date_in_future_or_today(self):
        """Invoices due today or in the future must not be marked as overdue."""
        # Due today
        inv_today = MockInvoiceRecord(
            amount_total=100.0,
            invoice_status='confirmed',
            invoice_date_due=self.today
        )
        self.assertFalse(inv_today.is_overdue)
        self.assertEqual(inv_today.days_overdue, 0)
        self.assertEqual(inv_today.overdue_status, 'not_due')

        # Due in future
        inv_future = MockInvoiceRecord(
            amount_total=100.0,
            invoice_status='confirmed',
            invoice_date_due=self.future_due_10_days
        )
        self.assertFalse(inv_future.is_overdue)
        self.assertEqual(inv_future.days_overdue, 0)
        self.assertEqual(inv_future.overdue_status, 'not_due')

    def test_09_settled_invoices_not_marked_as_overdue(self):
        """Even if the due date is in the past, a fully paid invoice must not be overdue."""
        payments = [MockPayment(amount=200.0, state='posted')]
        inv = MockInvoiceRecord(
            amount_total=200.0,
            invoice_status='paid',
            invoice_date_due=self.past_due_15_days,
            payments=payments
        )
        self.assertFalse(inv.is_overdue)
        self.assertEqual(inv.days_overdue, 0)
        self.assertEqual(inv.overdue_status, 'settled')

    # -------------------------------------------------------------------------
    # 4. Cancelled Invoices Exclusion
    # -------------------------------------------------------------------------
    def test_10_cancelled_invoices_excluded_from_outstanding_residual(self):
        """Cancelled invoices must have 0 residual balance and cannot be considered unpaid/outstanding."""
        inv = MockInvoiceRecord(
            amount_total=400.0,
            invoice_status='cancel',
            invoice_date_due=self.past_due_5_days
        )
        self.assertEqual(inv.amount_residual, 0.0)
        self.assertFalse(inv.is_unpaid)
        self.assertFalse(inv.is_partially_paid)
        self.assertFalse(inv.is_fully_paid)
        self.assertFalse(AccountMove.is_invoice_unpaid(inv))

    def test_11_cancelled_invoices_excluded_from_overdue_detection(self):
        """Cancelled invoices must never be marked as overdue regardless of due date."""
        inv = MockInvoiceRecord(
            amount_total=400.0,
            invoice_status='cancel',
            invoice_date_due=self.past_due_15_days
        )
        self.assertFalse(inv.is_overdue)
        self.assertEqual(inv.days_overdue, 0)
        self.assertEqual(inv.overdue_status, 'cancelled')

    def test_12_cancellation_action_clears_residual_and_overdue(self):
        """Executing action_cancel must immediately reset residual to 0 and clear overdue flags."""
        inv = MockInvoiceRecord(
            amount_total=300.0,
            invoice_status='confirmed',
            invoice_date_due=self.past_due_5_days
        )
        self.assertTrue(inv.is_overdue)
        self.assertEqual(inv.amount_residual, 300.0)

        # Cancel the invoice
        inv.action_cancel()
        self.assertEqual(inv.invoice_status, 'cancel')
        self.assertEqual(inv.amount_residual, 0.0)
        self.assertFalse(inv.is_overdue)
        self.assertEqual(inv.days_overdue, 0)
        self.assertEqual(inv.overdue_status, 'cancelled')

    # -------------------------------------------------------------------------
    # 5. Financial Summaries
    # -------------------------------------------------------------------------
    def test_13_financial_summary_basic_aggregation(self):
        """Financial summary must aggregate invoiced, paid, outstanding, and overdue amounts accurately."""
        inv1 = MockInvoiceRecord(id=1, amount_total=100.0, invoice_status='confirmed',
                                 invoice_date_due=self.future_due_10_days)
        inv2 = MockInvoiceRecord(id=2, amount_total=200.0, invoice_status='confirmed',
                                 invoice_date_due=self.past_due_5_days,
                                 payments=[MockPayment(amount=50.0)])
        inv3 = MockInvoiceRecord(id=3, amount_total=150.0, invoice_status='paid',
                                 payments=[MockPayment(amount=150.0)])

        invoices = [inv1, inv2, inv3]
        summary = AccountMove.get_financial_summary(invoices)

        # Total invoiced: 100 + 200 + 150 = 450
        self.assertEqual(summary['total_invoiced'], 450.0)
        # Total paid: 0 + 50 + 150 = 200
        self.assertEqual(summary['total_paid'], 200.0)
        # Total outstanding: 100 + 150 (inv2 residual) = 250
        self.assertEqual(summary['total_outstanding'], 250.0)
        # Total overdue: inv2 is overdue with remaining residual of 150 (NOT 200)
        self.assertEqual(summary['total_overdue'], 150.0)

    def test_14_financial_summary_strictly_excludes_cancelled_invoices(self):
        """Cancelled invoices must be excluded from total invoiced, outstanding, and overdue."""
        inv_active = MockInvoiceRecord(id=1, amount_total=100.0, invoice_status='confirmed',
                                       invoice_date_due=self.past_due_5_days)
        inv_cancelled = MockInvoiceRecord(id=2, amount_total=999.0, invoice_status='cancel',
                                          invoice_date_due=self.past_due_15_days)

        summary = AccountMove.get_financial_summary([inv_active, inv_cancelled])

        # Active is 100, cancelled 999 must NOT be added
        self.assertEqual(summary['total_invoiced'], 100.0)
        self.assertEqual(summary['total_outstanding'], 100.0)
        self.assertEqual(summary['total_overdue'], 100.0)
        self.assertEqual(summary['count_total'], 1)
        self.assertEqual(summary['count_cancelled'], 1)
        self.assertEqual(summary['count_overdue'], 1)

    def test_15_financial_summary_tracks_counts_accurately(self):
        """Summary metrics must count unpaid, partially paid, paid, overdue, and cancelled invoices."""
        invoices = [
            MockInvoiceRecord(id=1, amount_total=100.0, invoice_status='draft'),
            MockInvoiceRecord(id=2, amount_total=200.0, invoice_status='confirmed', payments=[]),
            MockInvoiceRecord(id=3, amount_total=300.0, invoice_status='confirmed', payments=[MockPayment(50.0)]),
            MockInvoiceRecord(id=4, amount_total=400.0, invoice_status='paid', payments=[MockPayment(400.0)]),
            MockInvoiceRecord(id=5, amount_total=500.0, invoice_status='cancel'),
        ]

        summary = AccountMove.get_financial_summary(invoices)
        self.assertEqual(summary['count_total'], 4)
        self.assertEqual(summary['count_draft'], 1)
        self.assertEqual(summary['count_confirmed'], 2)
        self.assertEqual(summary['count_paid'], 1)
        self.assertEqual(summary['count_partial'], 1)
        self.assertEqual(summary['count_unpaid'], 2)  # inv1 (draft) + inv2 (confirmed unpaid)
        self.assertEqual(summary['count_cancelled'], 1)

    def test_16_overdue_amount_is_residual_not_total_for_partially_paid(self):
        """When an overdue invoice has received partial payment, only the residual is overdue."""
        payments = [MockPayment(amount=120.0, state='posted')]
        inv = MockInvoiceRecord(
            amount_total=200.0,
            invoice_status='confirmed',
            invoice_date_due=self.past_due_5_days,
            payments=payments
        )
        self.assertTrue(inv.is_overdue)
        self.assertEqual(inv.amount_paid, 120.0)
        self.assertEqual(inv.amount_residual, 80.0)

        summary = AccountMove.get_financial_summary([inv])
        self.assertEqual(summary['total_overdue'], 80.0)
        self.assertEqual(summary['total_outstanding'], 80.0)

    def test_17_protected_finalized_fields_include_invoice_date_due(self):
        """Due date must be protected from unauthorized changes on finalized invoices."""
        self.assertIn('invoice_date_due', AccountMove.PROTECTED_FINALIZED_FIELDS)


if __name__ == '__main__':
    unittest.main()
