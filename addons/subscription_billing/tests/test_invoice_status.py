# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

"""
Unit tests for invoice status lifecycle, transitions, authorization checks,
finalized invoice protection, action restrictions, and audit history tracking.

Runs cleanly both standalone under pytest and within the Odoo test framework.
"""

import unittest
from datetime import datetime, date
from types import SimpleNamespace


class MockUser:
    def __init__(self, name="Test User", groups=None):
        self.id = 10
        self.name = name
        self.login = name.lower().replace(" ", "_")
        self.groups = set(groups or [])

    def has_group(self, group_ext_id):
        return group_ext_id in self.groups


class MockPartner:
    def __init__(self, name="Acme Corp", email="billing@acme.com"):
        self.id = 1
        self.name = name
        self.email = email


class MockHistoryRecord:
    def __init__(self, vals):
        self.id = vals.get('id', 1)
        self.move_id = vals.get('move_id')
        self.timestamp = vals.get('timestamp') or datetime.now()
        self.user_id = vals.get('user_id')
        self.user_name = vals.get('user_name')
        self.action = vals.get('action')
        self.previous_status = vals.get('previous_status')
        self.current_status = vals.get('current_status')
        self.details = vals.get('details', '')


class MockHistoryModel:
    def __init__(self):
        self.records = []
        self._next_id = 1

    def create(self, vals):
        vals['id'] = self._next_id
        self._next_id += 1
        rec = MockHistoryRecord(vals)
        self.records.append(rec)
        return rec


class InvoiceStatusSimulator:
    """Simulates AccountMove logic for invoice lifecycle, validation, authorization, and history."""

    PROTECTED_FINALIZED_FIELDS = {
        'invoice_line_ids',
        'line_ids',
        'partner_id',
        'currency_id',
        'invoice_date',
        'subscription_id',
        'subscription_billing_date',
        'amount_untaxed',
        'amount_total',
        'amount_tax',
    }

    def __init__(self, partner=None, lines=None, current_user=None, env_su=False):
        self.id = 101
        self.name = "INV/2026/00101"
        self.partner_id = partner or MockPartner()
        self.invoice_line_ids = lines if lines is not None else [{'product': 'SaaS Seat', 'amount': 100.0}]
        self.line_ids = self.invoice_line_ids
        self.invoice_status = 'draft'
        self.state = 'draft'
        self.payment_state = 'not_paid'
        self.invoice_sent = False
        self.invoice_sent_date = None
        self.amount_total = 118.0
        self.amount_untaxed = 100.0
        self.amount_tax = 18.0

        # Simulation environment
        self.env = SimpleNamespace(
            user=current_user or MockUser("Billing Staff", ["subscription_base.group_subscription_user"]),
            su=env_su,
            history_model=MockHistoryModel(),
            context={}
        )
        self.history_ids = []

        # Log creation history
        self._log_history('create', None, 'draft', "Invoice created in Draft status.")

    def _log_history(self, action, previous_status, current_status, details=None):
        user = self.env.user
        rec = self.env.history_model.create({
            'move_id': self.id,
            'timestamp': datetime.now(),
            'user_id': user.id if hasattr(user, 'id') else False,
            'user_name': getattr(user, 'name', 'System'),
            'action': action,
            'previous_status': previous_status,
            'current_status': current_status,
            'details': details or '',
        })
        self.history_ids.append(rec)
        return rec

    def _check_confirm_authorization(self):
        if getattr(self.env, 'su', False):
            return True
        user = self.env.user
        authorized_groups = (
            'subscription_base.group_subscription_user',
            'subscription_base.group_subscription_manager',
            'account.group_account_invoice',
            'account.group_account_manager',
        )
        if hasattr(user, 'has_group'):
            if any(user.has_group(g) for g in authorized_groups):
                return True
            raise PermissionError("Access Denied: Only authorized billing staff or administrators can confirm invoices.")
        return True

    def _validate_status_transition(self, from_status, to_status):
        if from_status == 'draft':
            if to_status not in ('confirmed', 'cancel'):
                raise ValueError(
                    f"Invalid status transition for invoice '{self.name}': Cannot transition from 'Draft' directly to '{to_status.capitalize()}'. "
                    f"Draft invoices must first be confirmed before recording payment."
                )
        elif from_status == 'confirmed':
            if to_status not in ('paid', 'cancel'):
                raise ValueError(
                    f"Invalid status transition for invoice '{self.name}': Cannot transition from 'Confirmed' to '{to_status.capitalize()}'. "
                    f"Confirmed invoices can only be paid or cancelled."
                )
        elif from_status == 'paid':
            raise ValueError(
                f"Invalid status transition for invoice '{self.name}': Invoice is fully paid and finalized. "
                f"No status transitions or modifications are permitted on paid invoices."
            )
        elif from_status == 'cancel':
            raise ValueError(
                f"Invalid status transition for invoice '{self.name}': Invoice is cancelled. "
                f"Cancelled invoices cannot be transitioned to '{to_status.capitalize()}'."
            )

    def write(self, vals):
        # Check protection on finalized invoices
        if not self.env.context.get('ignore_protection', False):
            if self.invoice_status in ('confirmed', 'paid', 'cancel'):
                attempted = set(vals.keys()).intersection(self.PROTECTED_FINALIZED_FIELDS)
                if attempted:
                    fields_str = ', '.join(sorted(attempted))
                    raise ValueError(
                        f"Cannot modify protected field(s) [{fields_str}] on finalized invoice '{self.name}' in '{self.invoice_status}' status. "
                        f"Finalized invoices are protected against unauthorized or invalid modifications."
                    )

        # Transition validation
        new_status = vals.get('invoice_status')
        if new_status and new_status != self.invoice_status:
            self._validate_status_transition(self.invoice_status, new_status)

        # Automatic payment flow
        if vals.get('payment_state') == 'paid' and 'invoice_status' not in vals:
            if self.invoice_status == 'confirmed':
                vals['invoice_status'] = 'paid'
                self._log_history('register_payment', 'confirmed', 'paid', "Invoice automatically marked as Paid via payment matching.")

        # Apply updates
        for k, v in vals.items():
            if not k.startswith('_'):
                setattr(self, k, v)

        if new_status:
            if new_status == 'draft':
                self.state = 'draft'
            elif new_status == 'confirmed':
                self.state = 'posted'
            elif new_status == 'paid':
                self.state = 'posted'
                self.payment_state = 'paid'
            elif new_status == 'cancel':
                self.state = 'cancel'
        return True

    def unlink(self):
        if self.invoice_status in ('confirmed', 'paid'):
            raise ValueError(
                f"Cannot delete invoice '{self.name}' in '{self.invoice_status}' status. "
                f"Finalized and confirmed invoices are protected from deletion."
            )
        return True

    def action_confirm(self):
        self._check_confirm_authorization()
        if self.invoice_status != 'draft':
            raise ValueError(
                f"Only draft invoices can be confirmed. Invoice '{self.name}' is currently in '{self.invoice_status.capitalize()}' status."
            )
        lines = self.invoice_line_ids or self.line_ids
        if not lines:
            raise ValueError(f"Cannot confirm invoice '{self.name}': Invoice must contain at least one line item.")

        prev = self.invoice_status
        self.write({
            'invoice_status': 'confirmed',
            'state': 'posted',
            '_skip_history_log': True,
        })
        self._log_history('confirm', prev, 'confirmed', "Invoice confirmed and finalized awaiting payment.")
        return True

    def action_mark_paid(self, payment_ref=None, payment_date=None, amount=None):
        if self.invoice_status == 'draft':
            raise ValueError(
                f"Cannot mark draft invoice '{self.name}' as paid. Invoice must be confirmed before recording payment."
            )
        if self.invoice_status == 'cancel':
            raise ValueError(f"Cannot record payment on cancelled invoice '{self.name}'.")
        if self.invoice_status == 'paid':
            raise ValueError(f"Invoice '{self.name}' is already fully paid.")
        if self.invoice_status != 'confirmed':
            raise ValueError(
                f"Invalid status for payment: Invoice '{self.name}' must be in Confirmed status (current: '{self.invoice_status.capitalize()}')."
            )

        prev = self.invoice_status
        self.write({
            'invoice_status': 'paid',
            'payment_state': 'paid',
            'state': 'posted',
            '_skip_history_log': True,
        })
        detail = "Invoice marked as fully paid."
        if payment_ref:
            detail += f" Payment Ref: {payment_ref}"
        if amount is not None:
            detail += f" Amount: {amount}"
        self._log_history('register_payment', prev, 'paid', detail)
        return True

    def action_cancel(self):
        if self.invoice_status == 'paid':
            raise ValueError(
                f"Cannot cancel invoice '{self.name}': Invoice is fully paid. Payments must be reversed or refunded before cancellation."
            )
        if self.invoice_status == 'cancel':
            raise ValueError(f"Invoice '{self.name}' is already cancelled.")
        if self.invoice_status not in ('draft', 'confirmed'):
            raise ValueError(
                f"Cannot cancel invoice '{self.name}': Cancellation is only permitted for Draft or Confirmed invoices."
            )

        prev = self.invoice_status
        self.write({
            'invoice_status': 'cancel',
            'state': 'cancel',
            '_skip_history_log': True,
        })
        self._log_history('cancel', prev, 'cancel', "Invoice cancelled.")
        return True

    def action_send_invoice(self):
        if self.invoice_status == 'draft':
            raise ValueError(
                f"Draft invoice '{self.name}' cannot be sent to the customer. Please confirm the invoice before sending."
            )
        if self.invoice_status == 'cancel':
            raise ValueError(f"Cannot send cancelled invoice '{self.name}'.")
        if not self.partner_id or not self.partner_id.email:
            name = self.partner_id.name if self.partner_id else "Unassigned"
            raise ValueError(f"Cannot send invoice '{self.name}': Customer '{name}' does not have a valid email address.")

        self.write({
            'invoice_sent': True,
            'invoice_sent_date': datetime.now(),
            '_skip_history_log': True,
        })
        self._log_history('send', self.invoice_status, self.invoice_status, f"Invoice sent to customer {self.partner_id.name} ({self.partner_id.email}).")
        return True

    def action_print_invoice(self):
        if self.invoice_status == 'cancel':
            raise ValueError(f"Cannot print cancelled invoice '{self.name}'.")
        self._log_history('print', self.invoice_status, self.invoice_status, "Invoice document printed.")
        return True

    def action_download_invoice(self):
        if self.invoice_status == 'cancel':
            raise ValueError(f"Cannot download cancelled invoice '{self.name}'.")
        self._log_history('download', self.invoice_status, self.invoice_status, "Invoice PDF downloaded.")
        return {'url': f'/web/content/account.move/{self.id}/pdf'}


class TestInvoiceStatusLifecycle(unittest.TestCase):
    """Test suite covering all acceptance criteria for invoice statuses and lifecycle workflows."""

    def setUp(self):
        self.partner = MockPartner(name="Acme Global", email="billing@acme.com")
        self.staff_user = MockUser("Billing Staff", ["subscription_base.group_subscription_user"])
        self.manager_user = MockUser("Billing Manager", ["subscription_base.group_subscription_manager"])
        self.portal_user = MockUser("Portal Customer", ["subscription_auth.group_subscription_customer"])
        self.invoice = InvoiceStatusSimulator(partner=self.partner, current_user=self.staff_user)

    # -------------------------------------------------------------
    # 1. Invoice Creation Sets Status to Draft by Default
    # -------------------------------------------------------------
    def test_01_creation_defaults_to_draft(self):
        inv = InvoiceStatusSimulator(partner=self.partner)
        self.assertEqual(inv.invoice_status, 'draft', "New invoice must default to 'draft' status.")
        self.assertEqual(inv.state, 'draft', "Underlying Odoo state must also be 'draft'.")
        # History check
        self.assertEqual(len(inv.history_ids), 1, "Creation event must be recorded in history.")
        self.assertEqual(inv.history_ids[0].action, 'create')
        self.assertIsNone(inv.history_ids[0].previous_status)
        self.assertEqual(inv.history_ids[0].current_status, 'draft')

    # -------------------------------------------------------------
    # 2. Draft -> Confirmed Flow
    # -------------------------------------------------------------
    def test_02_draft_to_confirmed_success(self):
        self.assertEqual(self.invoice.invoice_status, 'draft')
        self.invoice.action_confirm()
        self.assertEqual(self.invoice.invoice_status, 'confirmed', "Invoice must transition to 'confirmed'.")
        self.assertEqual(self.invoice.state, 'posted', "Odoo state must transition to 'posted'.")

        # History verification
        confirm_events = [h for h in self.invoice.history_ids if h.action == 'confirm']
        self.assertEqual(len(confirm_events), 1)
        self.assertEqual(confirm_events[0].previous_status, 'draft')
        self.assertEqual(confirm_events[0].current_status, 'confirmed')
        self.assertEqual(confirm_events[0].user_name, 'Billing Staff')

    def test_03_cannot_confirm_without_lines(self):
        empty_inv = InvoiceStatusSimulator(lines=[])
        with self.assertRaises(ValueError) as cm:
            empty_inv.action_confirm()
        self.assertIn("must contain at least one line item", str(cm.exception))
        self.assertEqual(empty_inv.invoice_status, 'draft')

    # -------------------------------------------------------------
    # 3. Confirmed -> Paid Flow
    # -------------------------------------------------------------
    def test_04_confirmed_to_paid_success(self):
        self.invoice.action_confirm()
        self.assertEqual(self.invoice.invoice_status, 'confirmed')

        self.invoice.action_mark_paid(payment_ref="TXN-9090", amount=118.0)
        self.assertEqual(self.invoice.invoice_status, 'paid', "Invoice must move to 'paid'.")
        self.assertEqual(self.invoice.payment_state, 'paid')

        # History verification
        pay_events = [h for h in self.invoice.history_ids if h.action == 'register_payment']
        self.assertEqual(len(pay_events), 1)
        self.assertEqual(pay_events[0].previous_status, 'confirmed')
        self.assertEqual(pay_events[0].current_status, 'paid')
        self.assertIn("TXN-9090", pay_events[0].details)

    def test_05_draft_cannot_move_directly_to_paid(self):
        self.assertEqual(self.invoice.invoice_status, 'draft')
        with self.assertRaises(ValueError) as cm:
            self.invoice.action_mark_paid(payment_ref="TXN-1111")
        self.assertIn("must be confirmed before recording payment", str(cm.exception))
        self.assertEqual(self.invoice.invoice_status, 'draft')

    def test_06_automatic_paid_transition_on_payment_state(self):
        self.invoice.action_confirm()
        self.assertEqual(self.invoice.invoice_status, 'confirmed')

        # Simulate Odoo reconciling payment and writing payment_state='paid'
        self.invoice.write({'payment_state': 'paid'})
        self.assertEqual(self.invoice.invoice_status, 'paid')
        pay_events = [h for h in self.invoice.history_ids if h.action == 'register_payment']
        self.assertTrue(len(pay_events) >= 1)

    # -------------------------------------------------------------
    # 4. Cancellation Flow
    # -------------------------------------------------------------
    def test_07_cancel_from_draft(self):
        self.assertEqual(self.invoice.invoice_status, 'draft')
        self.invoice.action_cancel()
        self.assertEqual(self.invoice.invoice_status, 'cancel')
        self.assertEqual(self.invoice.state, 'cancel')

        cancel_events = [h for h in self.invoice.history_ids if h.action == 'cancel']
        self.assertEqual(len(cancel_events), 1)
        self.assertEqual(cancel_events[0].previous_status, 'draft')
        self.assertEqual(cancel_events[0].current_status, 'cancel')

    def test_08_cancel_from_confirmed(self):
        self.invoice.action_confirm()
        self.assertEqual(self.invoice.invoice_status, 'confirmed')

        self.invoice.action_cancel()
        self.assertEqual(self.invoice.invoice_status, 'cancel')
        self.assertEqual(self.invoice.state, 'cancel')

        cancel_events = [h for h in self.invoice.history_ids if h.action == 'cancel']
        self.assertEqual(len(cancel_events), 1)
        self.assertEqual(cancel_events[0].previous_status, 'confirmed')
        self.assertEqual(cancel_events[0].current_status, 'cancel')

    def test_09_cannot_cancel_fully_paid_invoice(self):
        self.invoice.action_confirm()
        self.invoice.action_mark_paid()
        self.assertEqual(self.invoice.invoice_status, 'paid')

        with self.assertRaises(ValueError) as cm:
            self.invoice.action_cancel()
        self.assertIn("Invoice is fully paid", str(cm.exception))
        self.assertEqual(self.invoice.invoice_status, 'paid')

    def test_10_cannot_cancel_already_cancelled_invoice(self):
        self.invoice.action_cancel()
        self.assertEqual(self.invoice.invoice_status, 'cancel')

        with self.assertRaises(ValueError) as cm:
            self.invoice.action_cancel()
        self.assertIn("already cancelled", str(cm.exception))

    # -------------------------------------------------------------
    # 5. Invalid Transition Attempts Rejected with Clear Errors
    # -------------------------------------------------------------
    def test_11_invalid_transitions_rejected(self):
        # 1. Draft -> Paid directly via write
        with self.assertRaises(ValueError) as cm:
            self.invoice.write({'invoice_status': 'paid'})
        self.assertIn("Cannot transition from 'Draft' directly to 'Paid'", str(cm.exception))

        # 2. Confirmed -> Draft via write
        self.invoice.action_confirm()
        with self.assertRaises(ValueError) as cm:
            self.invoice.write({'invoice_status': 'draft'})
        self.assertIn("Cannot transition from 'Confirmed' to 'Draft'", str(cm.exception))

        # 3. Paid -> any other status
        self.invoice.action_mark_paid()
        for target in ('draft', 'confirmed', 'cancel'):
            with self.assertRaises(ValueError) as cm:
                self.invoice.write({'invoice_status': target})
            self.assertIn("Invoice is fully paid and finalized", str(cm.exception))

        # 4. Cancel -> Confirmed or Paid
        inv_cancel = InvoiceStatusSimulator(partner=self.partner)
        inv_cancel.action_cancel()
        for target in ('confirmed', 'paid'):
            with self.assertRaises(ValueError) as cm:
                inv_cancel.write({'invoice_status': target})
            self.assertIn("Cancelled invoices cannot be transitioned", str(cm.exception))

    # -------------------------------------------------------------
    # 6. Authorization Checks
    # -------------------------------------------------------------
    def test_12_authorized_staff_and_manager_can_confirm(self):
        # Internal Staff
        inv_staff = InvoiceStatusSimulator(partner=self.partner, current_user=self.staff_user)
        self.assertTrue(inv_staff.action_confirm())
        self.assertEqual(inv_staff.invoice_status, 'confirmed')

        # Administrator
        inv_mgr = InvoiceStatusSimulator(partner=self.partner, current_user=self.manager_user)
        self.assertTrue(inv_mgr.action_confirm())
        self.assertEqual(inv_mgr.invoice_status, 'confirmed')

    def test_13_unauthorized_user_cannot_confirm(self):
        # Portal Customer has no billing staff privileges
        inv_portal = InvoiceStatusSimulator(partner=self.partner, current_user=self.portal_user)
        with self.assertRaises(PermissionError) as cm:
            inv_portal.action_confirm()
        self.assertIn("Access Denied", str(cm.exception))
        self.assertEqual(inv_portal.invoice_status, 'draft')

    # -------------------------------------------------------------
    # 7. Invoice History Tracking
    # -------------------------------------------------------------
    def test_14_full_lifecycle_history_audit(self):
        inv = InvoiceStatusSimulator(partner=self.partner, current_user=self.staff_user)
        # 1. Created
        self.assertEqual(len(inv.history_ids), 1)
        self.assertEqual(inv.history_ids[0].action, 'create')
        self.assertEqual(inv.history_ids[0].current_status, 'draft')

        # 2. Confirmed
        inv.action_confirm()
        self.assertEqual(len(inv.history_ids), 2)
        self.assertEqual(inv.history_ids[1].action, 'confirm')
        self.assertEqual(inv.history_ids[1].previous_status, 'draft')
        self.assertEqual(inv.history_ids[1].current_status, 'confirmed')

        # 3. Sent
        inv.action_send_invoice()
        self.assertEqual(len(inv.history_ids), 3)
        self.assertEqual(inv.history_ids[2].action, 'send')
        self.assertEqual(inv.history_ids[2].previous_status, 'confirmed')
        self.assertEqual(inv.history_ids[2].current_status, 'confirmed')

        # 4. Downloaded & Printed
        inv.action_download_invoice()
        inv.action_print_invoice()
        self.assertEqual(len(inv.history_ids), 5)
        self.assertEqual(inv.history_ids[3].action, 'download')
        self.assertEqual(inv.history_ids[4].action, 'print')

        # 5. Paid
        inv.action_mark_paid(payment_ref="REC-2026-X")
        self.assertEqual(len(inv.history_ids), 6)
        self.assertEqual(inv.history_ids[5].action, 'register_payment')
        self.assertEqual(inv.history_ids[5].previous_status, 'confirmed')
        self.assertEqual(inv.history_ids[5].current_status, 'paid')

        # Check timestamp and actor on all records
        for h in inv.history_ids:
            self.assertIsNotNone(h.timestamp)
            self.assertTrue(h.user_name)
            self.assertTrue(h.action)

    # -------------------------------------------------------------
    # 8. Protection of Finalized Invoices (Edits & Deletion)
    # -------------------------------------------------------------
    def test_15_finalized_invoices_protected_from_modification(self):
        self.invoice.action_confirm()

        # Cannot modify financial fields on confirmed invoice
        with self.assertRaises(ValueError) as cm:
            self.invoice.write({'amount_total': 500.0})
        self.assertIn("Cannot modify protected field(s)", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            self.invoice.write({'invoice_line_ids': []})
        self.assertIn("Cannot modify protected field(s)", str(cm.exception))

        # Paid invoice also protected
        self.invoice.action_mark_paid()
        with self.assertRaises(ValueError) as cm:
            self.invoice.write({'partner_id': 999})
        self.assertIn("Cannot modify protected field(s)", str(cm.exception))

    def test_16_finalized_invoices_protected_from_deletion(self):
        # Draft can be deleted
        draft_inv = InvoiceStatusSimulator(partner=self.partner)
        self.assertTrue(draft_inv.unlink())

        # Confirmed cannot be deleted
        self.invoice.action_confirm()
        with self.assertRaises(ValueError) as cm:
            self.invoice.unlink()
        self.assertIn("Cannot delete invoice", str(cm.exception))

        # Paid cannot be deleted
        self.invoice.action_mark_paid()
        with self.assertRaises(ValueError) as cm:
            self.invoice.unlink()
        self.assertIn("Cannot delete invoice", str(cm.exception))

    # -------------------------------------------------------------
    # 9. Invoice Sending, Printing, and Downloading State Restrictions
    # -------------------------------------------------------------
    def test_17_invoice_sending_state_restrictions(self):
        # Draft invoice cannot be sent
        with self.assertRaises(ValueError) as cm:
            self.invoice.action_send_invoice()
        self.assertIn("Draft invoice", str(cm.exception))
        self.assertIn("cannot be sent", str(cm.exception))

        # Confirmed invoice sends successfully
        self.invoice.action_confirm()
        self.assertTrue(self.invoice.action_send_invoice())
        self.assertTrue(self.invoice.invoice_sent)
        self.assertIsNotNone(self.invoice.invoice_sent_date)

        # Cancelled invoice cannot be sent
        inv_cancel = InvoiceStatusSimulator(partner=self.partner)
        inv_cancel.action_cancel()
        with self.assertRaises(ValueError) as cm:
            inv_cancel.action_send_invoice()
        self.assertIn("Cannot send cancelled invoice", str(cm.exception))

    def test_18_customer_missing_email_prevents_sending(self):
        no_email_partner = MockPartner(name="Offline Co", email=None)
        inv = InvoiceStatusSimulator(partner=no_email_partner)
        inv.action_confirm()
        with self.assertRaises(ValueError) as cm:
            inv.action_send_invoice()
        self.assertIn("does not have a valid email address", str(cm.exception))

    def test_19_printing_and_downloading_restrictions(self):
        # Draft, Confirmed, and Paid can be printed and downloaded
        draft_inv = InvoiceStatusSimulator(partner=self.partner)
        self.assertTrue(draft_inv.action_print_invoice())
        self.assertTrue(draft_inv.action_download_invoice())

        self.invoice.action_confirm()
        self.assertTrue(self.invoice.action_print_invoice())
        self.assertTrue(self.invoice.action_download_invoice())

        self.invoice.action_mark_paid()
        self.assertTrue(self.invoice.action_print_invoice())
        self.assertTrue(self.invoice.action_download_invoice())

        # Cancelled invoices cannot be printed or downloaded
        inv_cancel = InvoiceStatusSimulator(partner=self.partner)
        inv_cancel.action_cancel()
        with self.assertRaises(ValueError) as cm:
            inv_cancel.action_print_invoice()
        self.assertIn("Cannot print cancelled invoice", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            inv_cancel.action_download_invoice()
        self.assertIn("Cannot download cancelled invoice", str(cm.exception))


if __name__ == '__main__':
    unittest.main()

