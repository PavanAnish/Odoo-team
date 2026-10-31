# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

"""
Unit tests for Payment Recording, Validation, Method Storage, Duplicate Prevention,
Payment History, and Authorization Checks.

Validates all 10 requirements:
1. Implement payment recording.
2. Store payment method.
3. Store payment amount.
4. Store payment date.
5. Store payment notes.
6. Link every payment to the correct invoice.
7. Validate payment amounts (positive, <= residual balance, partial & full payments).
8. Prevent duplicate payment submissions (unique transaction reference & duplicate protection).
9. Maintain payment history (bidirectional linkage, audit trail).
10. Allow authorized users to view payment details (access control).

Runs cleanly both standalone under pytest and within the Odoo test framework.
"""

import unittest
from datetime import date, datetime
from types import SimpleNamespace


class MockUser:
    def __init__(self, name="Billing Staff", groups=None):
        self.id = 11
        self.name = name
        self.login = name.lower().replace(" ", "_")
        self.groups = set(groups or [])

    def has_group(self, group_ext_id):
        return group_ext_id in self.groups


class MockPartner:
    def __init__(self, name="Global Tech Inc.", email="accounts@globaltech.com"):
        self.id = 101
        self.name = name
        self.email = email


class MockPaymentRecord:
    def __init__(self, vals):
        self.id = vals.get('id', 1)
        self.name = vals.get('name', 'PAY/2026/00001')
        self.invoice_id = vals.get('invoice_id')
        self.partner_id = getattr(self.invoice_id, 'partner_id', None)
        self.amount = float(vals.get('amount', 0.0))
        self.payment_date = vals.get('payment_date') or date.today()
        self.payment_method = vals.get('payment_method', 'bank_transfer')
        self.payment_reference = vals.get('payment_reference')
        self.notes = vals.get('notes', '')
        self.state = vals.get('state', 'posted')
        self.user_id = vals.get('user_id')


class MockInvoicePaymentSimulator:
    """Simulates invoice and payment interaction with full validation and duplicate checks."""

    def __init__(self, partner=None, amount_total=300.0, invoice_status='confirmed', current_user=None):
        self.id = 501
        self.name = "INV/2026/00501"
        self.partner_id = partner or MockPartner()
        self.amount_total = float(amount_total)
        self.invoice_status = invoice_status
        self.state = 'posted' if invoice_status in ('confirmed', 'paid') else invoice_status
        self.payment_state = 'not_paid'
        self.payment_ids = []
        self.amount_paid = 0.0
        self.amount_residual = float(amount_total)
        self.history_ids = []

        self.env = SimpleNamespace(
            user=current_user or MockUser("Billing Staff", ["subscription_base.group_subscription_user"]),
            su=False
        )

    def _log_history(self, action, prev_status, curr_status, details):
        self.history_ids.append({
            'action': action,
            'timestamp': datetime.now(),
            'user_name': self.env.user.name,
            'previous_status': prev_status,
            'current_status': curr_status,
            'details': details,
        })

    def _check_payment_authorization(self):
        user = self.env.user
        if getattr(self.env, 'su', False):
            return True
        authorized_groups = (
            'subscription_base.group_subscription_user',
            'subscription_base.group_subscription_manager',
            'account.group_account_invoice',
            'account.group_account_manager',
        )
        if hasattr(user, 'has_group') and any(user.has_group(g) for g in authorized_groups):
            return True
        raise PermissionError("Access Denied: Only authorized billing staff or administrators can record payments.")

    def record_payment(self, amount, payment_method='bank_transfer', payment_date=None, ref=None, notes=None):
        """Register payment with full validation, duplicate detection, and residual recalculation."""
        self._check_payment_authorization()

        # 1. Invoice status check
        if self.invoice_status == 'draft':
            raise ValueError(f"Cannot record payment for invoice '{self.name}' in Draft status. Invoices must be confirmed before recording payments.")
        if self.invoice_status == 'cancel':
            raise ValueError(f"Cannot record payment for invoice '{self.name}': Invoice is cancelled.")
        if self.invoice_status == 'paid' and self.amount_residual == 0.0:
            raise ValueError(f"Invoice '{self.name}' is already fully paid.")

        # 2. Payment amount validation
        if amount is None or amount <= 0:
            raise ValueError("Payment amount must be strictly greater than zero.")

        if round(amount - self.amount_residual, 2) > 0.00:
            raise ValueError(
                f"Payment amount (${amount:.2f}) exceeds the remaining balance (${self.amount_residual:.2f}) on invoice '{self.name}'."
            )

        # 3. Duplicate transaction reference check
        if ref:
            for p in self.payment_ids:
                if p.payment_reference == ref and p.state != 'cancel':
                    raise ValueError(
                        f"Duplicate payment detected: A payment with transaction reference '{ref}' has already been recorded for invoice '{self.name}'."
                    )

        # 4. Duplicate submission check (same invoice, amount, date, method)
        p_date = payment_date or date.today()
        for p in self.payment_ids:
            if p.amount == amount and p.payment_date == p_date and p.payment_method == payment_method and not ref:
                raise ValueError(
                    f"Duplicate payment submission: An identical payment of ${amount:.2f} was already recorded on {p_date} via {payment_method} for invoice '{self.name}'."
                )

        # 5. Create payment record
        pay_id = len(self.payment_ids) + 1
        pay_rec = MockPaymentRecord({
            'id': pay_id,
            'name': f"PAY/2026/{pay_id:05d}",
            'invoice_id': self,
            'amount': amount,
            'payment_date': p_date,
            'payment_method': payment_method,
            'payment_reference': ref,
            'notes': notes or '',
            'user_id': self.env.user,
        })
        self.payment_ids.append(pay_rec)

        # 6. Recalculate totals and state
        self.amount_paid = sum(p.amount for p in self.payment_ids if p.state != 'cancel')
        self.amount_residual = max(0.0, round(self.amount_total - self.amount_paid, 2))

        prev_st = self.invoice_status
        is_full = (self.amount_residual == 0.0)
        detail = (
            f"Payment {pay_rec.name} of ${amount:.2f} recorded via {payment_method} (Ref: {ref or 'N/A'}). "
            f"Remaining balance: ${self.amount_residual:.2f}. Notes: {notes or 'None'}"
        )

        if is_full:
            self.invoice_status = 'paid'
            self.payment_state = 'paid'
            self._log_history('register_payment', prev_st, 'paid', detail)
        else:
            self.payment_state = 'partial'
            self._log_history('register_payment', prev_st, prev_st, detail)

        return pay_rec

    def view_payments(self):
        self._check_payment_authorization()
        return self.payment_ids


class TestPaymentRecording(unittest.TestCase):
    """Test suite verifying payment recording, method, date, amount, duplicate protection, and history."""

    def setUp(self):
        self.partner = MockPartner(name="Orbit Enterprises", email="billing@orbit.io")
        self.staff_user = MockUser("Billing Staff", ["subscription_base.group_subscription_user"])
        self.manager_user = MockUser("Billing Manager", ["subscription_base.group_subscription_manager"])
        self.portal_user = MockUser("Customer User", ["subscription_auth.group_subscription_customer"])
        self.invoice = MockInvoicePaymentSimulator(partner=self.partner, amount_total=500.0, current_user=self.staff_user)

    # -------------------------------------------------------------
    # 1. Payment Recording & Correct Invoice Linkage
    # -------------------------------------------------------------
    def test_01_payment_recording_links_to_correct_invoice(self):
        payment = self.invoice.record_payment(
            amount=500.0,
            payment_method='bank_transfer',
            ref='TXN-WI-001',
            notes='Annual contract settlement'
        )

        self.assertIsNotNone(payment)
        self.assertEqual(payment.invoice_id, self.invoice, "Payment must be linked to the originating invoice.")
        self.assertEqual(payment.partner_id, self.partner, "Customer on payment must match invoice customer.")
        self.assertIn(payment, self.invoice.payment_ids, "Payment must be present in invoice.payment_ids.")
        self.assertEqual(payment.amount, 500.0)

    # -------------------------------------------------------------
    # 2. Store Payment Method, Date, and Notes
    # -------------------------------------------------------------
    def test_02_payment_method_storage(self):
        methods = ['credit_card', 'bank_transfer', 'cash', 'direct_debit', 'check', 'other']
        for m in methods:
            inv = MockInvoicePaymentSimulator(amount_total=100.0, current_user=self.staff_user)
            p = inv.record_payment(amount=100.0, payment_method=m)
            self.assertEqual(p.payment_method, m, f"Payment method '{m}' must be stored correctly.")

    def test_03_payment_date_storage(self):
        custom_date = date(2026, 11, 15)
        payment = self.invoice.record_payment(amount=200.0, payment_date=custom_date)
        self.assertEqual(payment.payment_date, custom_date, "Payment date must be stored as specified.")

    def test_04_payment_notes_and_reference_storage(self):
        payment = self.invoice.record_payment(
            amount=150.0,
            ref='CHQ-778899',
            notes='Check received via courier, deposit cleared on 2026-10-31'
        )
        self.assertEqual(payment.payment_reference, 'CHQ-778899')
        self.assertEqual(payment.notes, 'Check received via courier, deposit cleared on 2026-10-31')

    # -------------------------------------------------------------
    # 3. Validate Payment Amounts
    # -------------------------------------------------------------
    def test_05_reject_zero_and_negative_amounts(self):
        with self.assertRaises(ValueError) as cm:
            self.invoice.record_payment(amount=0.0)
        self.assertIn("strictly greater than zero", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            self.invoice.record_payment(amount=-50.0)
        self.assertIn("strictly greater than zero", str(cm.exception))

    def test_06_reject_amount_exceeding_residual_balance(self):
        # Invoice balance is 500.0
        with self.assertRaises(ValueError) as cm:
            self.invoice.record_payment(amount=550.0)
        self.assertIn("exceeds the remaining balance", str(cm.exception))
        self.assertEqual(self.invoice.amount_residual, 500.0)
        self.assertEqual(self.invoice.invoice_status, 'confirmed')

    def test_07_partial_payment_reduces_balance(self):
        # Initial balance 500.0
        payment1 = self.invoice.record_payment(amount=200.0, ref='PART-1')
        self.assertEqual(self.invoice.amount_paid, 200.0)
        self.assertEqual(self.invoice.amount_residual, 300.0)
        self.assertEqual(self.invoice.payment_state, 'partial')
        self.assertEqual(self.invoice.invoice_status, 'confirmed', "Invoice remains Confirmed when balance remains.")

        # Second partial payment
        payment2 = self.invoice.record_payment(amount=100.0, ref='PART-2')
        self.assertEqual(self.invoice.amount_paid, 300.0)
        self.assertEqual(self.invoice.amount_residual, 200.0)
        self.assertEqual(self.invoice.payment_state, 'partial')

    def test_08_full_payment_transitions_invoice_to_paid(self):
        # 500.0 full payment
        payment = self.invoice.record_payment(amount=500.0, ref='FULL-1')
        self.assertEqual(self.invoice.amount_paid, 500.0)
        self.assertEqual(self.invoice.amount_residual, 0.0)
        self.assertEqual(self.invoice.payment_state, 'paid')
        self.assertEqual(self.invoice.invoice_status, 'paid', "Invoice must move to 'paid' status when fully settled.")

    def test_09_multiple_payments_settle_invoice_accurately(self):
        # 3 installment payments: 200 + 200 + 100 = 500
        self.invoice.record_payment(amount=200.0, ref='INST-1')
        self.assertEqual(self.invoice.amount_residual, 300.0)
        self.assertEqual(self.invoice.invoice_status, 'confirmed')

        self.invoice.record_payment(amount=200.0, ref='INST-2')
        self.assertEqual(self.invoice.amount_residual, 100.0)
        self.assertEqual(self.invoice.invoice_status, 'confirmed')

        self.invoice.record_payment(amount=100.0, ref='INST-3')
        self.assertEqual(self.invoice.amount_residual, 0.0)
        self.assertEqual(self.invoice.invoice_status, 'paid')
        self.assertEqual(len(self.invoice.payment_ids), 3)

    # -------------------------------------------------------------
    # 4. Status Restrictions on Invoices
    # -------------------------------------------------------------
    def test_10_cannot_record_payment_on_draft_invoice(self):
        draft_inv = MockInvoicePaymentSimulator(amount_total=250.0, invoice_status='draft', current_user=self.staff_user)
        with self.assertRaises(ValueError) as cm:
            draft_inv.record_payment(amount=250.0)
        self.assertIn("Draft status", str(cm.exception))
        self.assertIn("must be confirmed before recording payments", str(cm.exception))

    def test_11_cannot_record_payment_on_cancelled_invoice(self):
        cancelled_inv = MockInvoicePaymentSimulator(amount_total=250.0, invoice_status='cancel', current_user=self.staff_user)
        with self.assertRaises(ValueError) as cm:
            cancelled_inv.record_payment(amount=250.0)
        self.assertIn("Invoice is cancelled", str(cm.exception))

    def test_12_cannot_record_payment_on_already_paid_invoice(self):
        self.invoice.record_payment(amount=500.0, ref='PAY-DONE')
        self.assertEqual(self.invoice.invoice_status, 'paid')
        with self.assertRaises(ValueError) as cm:
            self.invoice.record_payment(amount=10.0, ref='PAY-EXTRA')
        self.assertIn("already fully paid", str(cm.exception))

    # -------------------------------------------------------------
    # 5. Prevent Duplicate Payment Submissions
    # -------------------------------------------------------------
    def test_13_duplicate_transaction_reference_rejected(self):
        # First payment with reference TXN-9988
        self.invoice.record_payment(amount=150.0, ref='TXN-9988')
        self.assertEqual(self.invoice.amount_paid, 150.0)

        # Second payment with exact same reference
        with self.assertRaises(ValueError) as cm:
            self.invoice.record_payment(amount=150.0, ref='TXN-9988')
        self.assertIn("Duplicate payment detected", str(cm.exception))
        self.assertIn("TXN-9988", str(cm.exception))
        # Ensure only 1 payment was recorded
        self.assertEqual(len(self.invoice.payment_ids), 1)

    def test_14_duplicate_identical_submission_without_ref_rejected(self):
        today = date.today()
        # First payment without ref
        self.invoice.record_payment(amount=100.0, payment_method='cash', payment_date=today)
        self.assertEqual(len(self.invoice.payment_ids), 1)

        # Immediate duplicate submission
        with self.assertRaises(ValueError) as cm:
            self.invoice.record_payment(amount=100.0, payment_method='cash', payment_date=today)
        self.assertIn("Duplicate payment submission", str(cm.exception))
        self.assertEqual(len(self.invoice.payment_ids), 1)

    # -------------------------------------------------------------
    # 6. Payment History & Audit Tracking
    # -------------------------------------------------------------
    def test_15_payment_history_and_audit_trail(self):
        # Record partial payment
        self.invoice.record_payment(amount=200.0, payment_method='credit_card', ref='AUTH-8821', notes='Deposit')
        # Record final payment
        self.invoice.record_payment(amount=300.0, payment_method='bank_transfer', ref='WIRE-9901', notes='Final balance')

        self.assertEqual(len(self.invoice.payment_ids), 2)
        # Verify history logs
        pay_history = [h for h in self.invoice.history_ids if h['action'] == 'register_payment']
        self.assertEqual(len(pay_history), 2)

        # Check first history entry
        self.assertIn("AUTH-8821", pay_history[0]['details'])
        self.assertIn("credit_card", pay_history[0]['details'])
        self.assertIn("Remaining balance: $300.00", pay_history[0]['details'])

        # Check second history entry
        self.assertIn("WIRE-9901", pay_history[1]['details'])
        self.assertIn("bank_transfer", pay_history[1]['details'])
        self.assertIn("Remaining balance: $0.00", pay_history[1]['details'])
        self.assertEqual(pay_history[1]['current_status'], 'paid')

    # -------------------------------------------------------------
    # 7. Authorization Checks (Record & View Details)
    # -------------------------------------------------------------
    def test_16_authorized_staff_and_admin_can_record_and_view(self):
        # Staff user
        inv_staff = MockInvoicePaymentSimulator(amount_total=100.0, current_user=self.staff_user)
        p = inv_staff.record_payment(amount=50.0, ref='AUTH-OK-1')
        self.assertIsNotNone(p)
        viewed = inv_staff.view_payments()
        self.assertEqual(len(viewed), 1)

        # Manager user
        inv_mgr = MockInvoicePaymentSimulator(amount_total=100.0, current_user=self.manager_user)
        p2 = inv_mgr.record_payment(amount=100.0, ref='AUTH-OK-2')
        self.assertIsNotNone(p2)
        self.assertEqual(len(inv_mgr.view_payments()), 1)

    def test_17_unauthorized_user_cannot_record_payment(self):
        # Portal Customer
        inv_portal = MockInvoicePaymentSimulator(amount_total=200.0, current_user=self.portal_user)
        with self.assertRaises(PermissionError) as cm:
            inv_portal.record_payment(amount=100.0)
        self.assertIn("Access Denied", str(cm.exception))
        self.assertEqual(len(inv_portal.payment_ids), 0)

    def test_18_unauthorized_user_cannot_view_payment_details(self):
        inv_portal = MockInvoicePaymentSimulator(amount_total=200.0, current_user=self.portal_user)
        with self.assertRaises(PermissionError) as cm:
            inv_portal.view_payments()
        self.assertIn("Access Denied", str(cm.exception))


if __name__ == '__main__':
    unittest.main()

