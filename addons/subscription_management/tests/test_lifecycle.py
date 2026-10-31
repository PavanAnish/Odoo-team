# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
"""
Comprehensive Automated Test Suite for Subscription Lifecycle Management.

Covers:
- Status Transition Tests (Draft -> Quotation -> Confirmed -> Active -> Closed & invalid rejection)
- Security Tests (Admin, Staff, Customer restrictions, Direct write guards)
- History Tests (Audit logging, previous/new states, timestamps, immutability)
- Billing Protection Tests (Active billable, Closed rejected, cron exclusion, invoice preservation)
- Integration Tests (Quotation conversion, initial state handling)
"""

from datetime import date, timedelta

try:
    from odoo import fields
    from odoo.tests.common import TransactionCase, tagged
    from odoo.exceptions import ValidationError, UserError, AccessError
except ImportError:
    import unittest
    TransactionCase = unittest.TestCase
    def tagged(*args):
        return lambda cls: cls
    class ValidationError(Exception): pass
    class UserError(Exception): pass
    class AccessError(Exception): pass
    fields = None


@tagged('post_install', '-at_install')
class TestSubscriptionLifecycle(TransactionCase):
    """Test suite verifying strict lifecycle management and audit history."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not hasattr(cls, 'env'):
            return

        cls.company = cls.env.company
        today = fields.Date.context_today(cls.env.user)

        # 1. Staff and Admin Users
        cls.staff_user = cls.env['res.users'].create({
            'name': 'Lifecycle Staff User',
            'login': 'lifecycle_staff@example.com',
            'email': 'lifecycle_staff@example.com',
            'groups_id': [(6, 0, [cls.env.ref('subscription_base.group_subscription_user').id])],
        })

        cls.admin_user = cls.env['res.users'].create({
            'name': 'Lifecycle Admin User',
            'login': 'lifecycle_admin@example.com',
            'email': 'lifecycle_admin@example.com',
            'groups_id': [(6, 0, [cls.env.ref('subscription_base.group_subscription_manager').id])],
        })

        # 2. Customers (Partners)
        cls.customer_1 = cls.env['res.partner'].create({
            'name': 'Alpha Enterprise Client',
            'email': 'alpha_client@example.com',
            'is_subscription_customer': True,
        })
        cls.customer_2 = cls.env['res.partner'].create({
            'name': 'Beta Logistics Client',
            'email': 'beta_client@example.com',
            'is_subscription_customer': True,
        })

        # 3. Portal User for Customer 1
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal Customer Alpha',
            'login': 'portal_alpha@example.com',
            'email': 'portal_alpha@example.com',
            'partner_id': cls.customer_1.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

        # 4. Subscription Plan
        cls.plan = cls.env['subscription.plan'].create({
            'name': 'Lifecycle Standard Plan',
            'code': 'PLAN-LIFECYCLE-01',
            'billing_interval': 1,
            'billing_period': 'monthly',
            'active': True,
            'min_quantity': 1.0,
        })

        # 5. Product
        cls.product_tmpl = cls.env['product.template'].create({
            'name': 'Managed Cloud Node',
            'type': 'service',
            'list_price': 1500.0,
            'is_subscription_product': True,
            'subscription_plan_id': cls.plan.id,
        })
        cls.product = cls.product_tmpl.product_variant_ids[0]

    def _make_subscription(self, customer=None, state='draft'):
        """Helper to create a fresh test subscription."""
        today = fields.Date.context_today(self.env.user)
        target_customer = customer or self.customer_1
        sub = self.env['subscription.subscription'].create({
            'partner_id': target_customer.id,
            'plan_id': self.plan.id,
            'date_quotation': today,
            'date_expiration': today + timedelta(days=30),
            'date_start': today,
            'state': state,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1.0,
                'price_unit': 1500.0,
            })],
        })
        return sub

    # =========================================================================
    # 1. STATUS TRANSITION TESTS
    # =========================================================================

    def test_01_draft_to_quotation_succeeds(self):
        """Valid transition: Draft -> Quotation."""
        sub = self._make_subscription()
        self.assertEqual(sub.state, 'draft')
        sub.action_set_quotation()
        self.assertEqual(sub.state, 'quotation')

    def test_02_quotation_to_confirmed_succeeds(self):
        """Valid transition: Quotation -> Confirmed."""
        sub = self._make_subscription()
        sub.action_set_quotation()
        self.assertEqual(sub.state, 'quotation')
        sub.action_confirm()
        self.assertEqual(sub.state, 'confirmed')

    def test_03_confirmed_to_active_succeeds(self):
        """Valid transition: Confirmed -> Active."""
        sub = self._make_subscription()
        sub.action_set_quotation()
        sub.action_confirm()
        self.assertEqual(sub.state, 'confirmed')
        sub.action_activate()
        self.assertEqual(sub.state, 'active')

    def test_04_active_to_closed_succeeds(self):
        """Valid transition: Active -> Closed."""
        sub = self._make_subscription()
        sub.action_set_quotation()
        sub.action_confirm()
        sub.action_activate()
        self.assertEqual(sub.state, 'active')
        sub.action_close(reason="Client requested contract termination")
        self.assertEqual(sub.state, 'closed')
        self.assertFalse(sub.next_billing_date, "Closing a subscription must clear next_billing_date.")

    def test_05_invalid_transitions_rejected(self):
        """Verify that every invalid lifecycle transition is strictly rejected."""
        # 1. Draft -> Active
        sub_draft = self._make_subscription()
        with self.assertRaises(ValidationError):
            sub_draft.action_activate()
        with self.assertRaises(ValidationError):
            sub_draft.write({'state': 'active'})

        # 2. Draft -> Closed
        with self.assertRaises(ValidationError):
            sub_draft.action_close()
        with self.assertRaises(ValidationError):
            sub_draft.write({'state': 'closed'})

        # 3. Quotation -> Active
        sub_quotation = self._make_subscription()
        sub_quotation.action_set_quotation()
        with self.assertRaises(ValidationError):
            sub_quotation.action_activate()
        with self.assertRaises(ValidationError):
            sub_quotation.write({'state': 'active'})

        # 4. Confirmed -> Closed
        sub_confirmed = self._make_subscription()
        sub_confirmed.action_set_quotation()
        sub_confirmed.action_confirm()
        with self.assertRaises(ValidationError):
            sub_confirmed.action_close()
        with self.assertRaises(ValidationError):
            sub_confirmed.write({'state': 'closed'})

        # 5. Closed -> Active
        sub_active = self._make_subscription()
        sub_active.action_set_quotation()
        sub_active.action_confirm()
        sub_active.action_activate()
        sub_active.action_close()
        self.assertEqual(sub_active.state, 'closed')

        with self.assertRaises(ValidationError):
            sub_active.action_activate()
        with self.assertRaises(ValidationError):
            sub_active.write({'state': 'active'})

        # 6. Closed -> Confirmed
        with self.assertRaises(ValidationError):
            sub_active.action_confirm()
        with self.assertRaises(ValidationError):
            sub_active.write({'state': 'confirmed'})

        # 7. Closed -> Draft
        with self.assertRaises(ValidationError):
            sub_active.write({'state': 'draft'})

        # 8. Quotation -> Draft
        sub_q2 = self._make_subscription()
        sub_q2.action_set_quotation()
        with self.assertRaises(ValidationError):
            sub_q2.write({'state': 'draft'})

    # =========================================================================
    # 2. SECURITY TESTS
    # =========================================================================

    def test_06_admin_can_perform_authorized_transitions(self):
        """Admin can execute all valid lifecycle transitions."""
        sub = self._make_subscription().with_user(self.admin_user)
        sub.action_set_quotation()
        self.assertEqual(sub.state, 'quotation')
        sub.action_confirm()
        self.assertEqual(sub.state, 'confirmed')
        sub.action_activate()
        self.assertEqual(sub.state, 'active')
        sub.action_close()
        self.assertEqual(sub.state, 'closed')

    def test_07_internal_staff_can_perform_permitted_transitions(self):
        """Internal staff can execute permitted transitions."""
        sub = self._make_subscription().with_user(self.staff_user)
        sub.action_set_quotation()
        self.assertEqual(sub.state, 'quotation')
        sub.action_confirm()
        self.assertEqual(sub.state, 'confirmed')
        sub.action_activate()
        self.assertEqual(sub.state, 'active')

    def test_08_customer_cannot_change_subscription_status(self):
        """Customer portal users are strictly blocked from triggering lifecycle transitions."""
        sub = self._make_subscription(customer=self.customer_1)
        sub.action_set_quotation()

        # Customer attempts to confirm via action
        with self.assertRaises(AccessError):
            sub.with_user(self.portal_user).action_confirm()

        # Customer attempts direct write
        with self.assertRaises(AccessError):
            sub.with_user(self.portal_user).write({'state': 'confirmed'})

    def test_09_customer_cannot_view_other_customers_history(self):
        """Record rules restrict portal customers to their own status history entries."""
        sub1 = self._make_subscription(customer=self.customer_1)
        sub1.action_set_quotation()

        sub2 = self._make_subscription(customer=self.customer_2)
        sub2.action_set_quotation()

        # Query history as portal user (customer 1)
        portal_history = self.env['subscription.status.history'].with_user(self.portal_user).search([])
        sub1_history = portal_history.filtered(lambda h: h.subscription_id == sub1)
        sub2_history = portal_history.filtered(lambda h: h.subscription_id == sub2)

        self.assertTrue(sub1_history, "Customer should be able to view history of their own subscription.")
        self.assertFalse(sub2_history, "Customer must NOT be able to view history of other customers' subscriptions.")

    def test_10_direct_status_modification_cannot_bypass_validation(self):
        """Direct ORM write of state field is validated identically to action methods."""
        sub = self._make_subscription()
        self.assertEqual(sub.state, 'draft')

        # Direct write of invalid state must raise ValidationError
        with self.assertRaises(ValidationError):
            sub.write({'state': 'active'})
        with self.assertRaises(ValidationError):
            sub.write({'state': 'closed'})

        # Direct write of valid next state is allowed for authorized staff
        sub.write({'state': 'quotation'})
        self.assertEqual(sub.state, 'quotation')

    # =========================================================================
    # 3. HISTORY TESTS
    # =========================================================================

    def test_11_every_successful_transition_creates_history_entry(self):
        """Every valid transition appends a history record in the same transaction."""
        sub = self._make_subscription()
        # 1 entry on create (draft)
        self.assertEqual(len(sub.history_ids), 1)

        sub.action_set_quotation()
        self.assertEqual(len(sub.history_ids), 2)

        sub.action_confirm()
        self.assertEqual(len(sub.history_ids), 3)

        sub.action_activate()
        self.assertEqual(len(sub.history_ids), 4)

        sub.action_close()
        self.assertEqual(len(sub.history_ids), 5)

    def test_12_previous_and_new_statuses_are_correct(self):
        """History entries accurately reflect previous and target statuses."""
        sub = self._make_subscription()
        sub.action_set_quotation()
        sub.action_confirm()

        # Most recent history entry (Confirmed)
        latest = sub.history_ids[0]
        self.assertEqual(latest.previous_state, 'quotation')
        self.assertEqual(latest.new_state, 'confirmed')

        # Previous entry (Quotation)
        prev = sub.history_ids[1]
        self.assertEqual(prev.previous_state, 'draft')
        self.assertEqual(prev.new_state, 'quotation')

    def test_13_user_and_timestamp_are_recorded(self):
        """History entries record the initiating user and valid timestamps."""
        sub = self._make_subscription().with_user(self.staff_user)
        sub.action_set_quotation()

        latest_entry = sub.history_ids[0]
        self.assertEqual(latest_entry.user_id, self.staff_user)
        self.assertTrue(latest_entry.change_date)

    def test_14_rejected_transitions_do_not_create_history(self):
        """When a transition is rejected, no history entry is created."""
        sub = self._make_subscription()
        initial_history_count = len(sub.history_ids)

        # Attempt invalid transition
        try:
            sub.action_activate()
        except ValidationError:
            pass

        self.assertEqual(len(sub.history_ids), initial_history_count,
                         "History records must not be created for rejected transitions.")

    def test_15_historical_records_cannot_be_modified_or_deleted(self):
        """History records are permanent audit logs that cannot be modified or deleted."""
        sub = self._make_subscription()
        sub.action_set_quotation()
        history_entry = sub.history_ids[0]

        # Modification must be blocked
        with self.assertRaises(UserError):
            history_entry.write({'reason': 'Tampered Reason'})

        # Deletion by staff must be blocked
        with self.assertRaises(UserError):
            history_entry.with_user(self.staff_user).unlink()

    # =========================================================================
    # 4. BILLING PROTECTION TESTS
    # =========================================================================

    def test_16_active_subscription_can_be_billed(self):
        """Active subscriptions can generate recurring invoices."""
        sub = self._make_subscription()
        sub.action_set_quotation()
        sub.action_confirm()
        sub.action_activate()
        self.assertEqual(sub.state, 'active')

        invoice = sub.action_generate_invoice()
        self.assertTrue(invoice)
        self.assertEqual(invoice.subscription_id, sub)

    def test_17_closed_subscription_cannot_be_billed(self):
        """Closed subscriptions must raise UserError when billed."""
        sub = self._make_subscription()
        sub.action_set_quotation()
        sub.action_confirm()
        sub.action_activate()
        sub.action_close()
        self.assertEqual(sub.state, 'closed')

        with self.assertRaises(UserError) as ctx:
            sub.action_generate_invoice()

        self.assertIn("closed", str(ctx.exception).lower())

    def test_18_scheduled_billing_skips_closed_subscriptions(self):
        """Cron recurring billing ignores closed subscriptions."""
        sub = self._make_subscription()
        sub.action_set_quotation()
        sub.action_confirm()
        sub.action_activate()
        sub.action_close()

        # Run recurring billing cron
        invoices = self.env['subscription.subscription']._cron_generate_recurring_invoices()
        sub_invoices = invoices.filtered(lambda inv: inv.subscription_id == sub)
        self.assertFalse(sub_invoices, "Cron must never generate invoices for closed subscriptions.")

    def test_19_manually_triggered_billing_rejects_closed(self):
        """Manual billing actions on closed subscriptions are rejected."""
        sub = self._make_subscription()
        sub.action_set_quotation()
        sub.action_confirm()
        sub.action_activate()
        sub.action_close()

        with self.assertRaises(UserError):
            sub.action_generate_invoice(billing_date=fields.Date.today())

    def test_20_previously_generated_invoices_remain_unchanged_after_closure(self):
        """Closing a subscription does not alter or delete previous invoices."""
        sub = self._make_subscription()
        sub.action_set_quotation()
        sub.action_confirm()
        sub.action_activate()

        # Generate invoice while active
        inv = sub.action_generate_invoice()
        inv_id = inv.id
        inv_amount = inv.amount_total

        # Close subscription
        sub.action_close()
        self.assertEqual(sub.state, 'closed')

        # Check existing invoice
        existing_inv = self.env['account.move'].browse(inv_id)
        self.assertTrue(existing_inv.exists())
        self.assertEqual(existing_inv.amount_total, inv_amount)
        self.assertEqual(existing_inv.subscription_id, sub)

    # =========================================================================
    # 5. INTEGRATION TESTS
    # =========================================================================

    def test_21_subscription_creation_uses_correct_initial_status(self):
        """Newly created subscriptions initialize in Draft with an initial audit entry."""
        sub = self._make_subscription()
        self.assertEqual(sub.state, 'draft')
        self.assertEqual(len(sub.history_ids), 1)
        self.assertFalse(sub.history_ids[0].previous_state)
        self.assertEqual(sub.history_ids[0].new_state, 'draft')

    def test_22_quotation_conversion_produces_correct_subscription_status(self):
        """Converting a confirmed quotation yields an Active subscription."""
        quotation = self._make_subscription()
        quotation.action_set_quotation()
        quotation.action_confirm()
        self.assertEqual(quotation.state, 'confirmed')

        sub = quotation.action_create_subscription()
        self.assertEqual(sub.state, 'active')
        self.assertTrue(sub.history_ids)
        self.assertEqual(sub.history_ids[0].new_state, 'active')
