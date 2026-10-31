# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

import logging
from datetime import date, datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """Extend account.move to manage subscription invoice statuses, transitions,
    payments, protection, and audit history."""
    _inherit = 'account.move'

    # --- Core Subscription Linkage ---
    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Originating Subscription',
        readonly=True,
        index=True,
        help='The subscription contract that generated this recurring invoice.'
    )
    subscription_billing_date = fields.Date(
        string='Billing Cycle Date',
        readonly=True,
        index=True,
        help='The subscription billing cycle date for which this invoice was generated.'
    )
    is_subscription_invoice = fields.Boolean(
        string='Subscription Invoice',
        compute='_compute_is_subscription_invoice',
        store=True,
        index=True,
    )
    subscription_calculation_details = fields.Text(
        string='Calculation Snapshot',
        readonly=True,
        copy=False,
        help='JSON snapshot of the invoice calculation at generation time. '
             'Preserves historical prices, discounts, and tax amounts even if '
             'product prices or tax rules change later.',
    )
    subscription_amount_untaxed = fields.Monetary(
        string='Subscription Untaxed Amount',
        readonly=True,
        copy=False,
        help='Snapshotted untaxed amount at invoice generation time.',
    )
    subscription_amount_tax = fields.Monetary(
        string='Subscription Tax Amount',
        readonly=True,
        copy=False,
        help='Snapshotted tax amount at invoice generation time.',
    )
    subscription_amount_total = fields.Monetary(
        string='Subscription Total Amount',
        readonly=True,
        copy=False,
        help='Snapshotted total amount at invoice generation time.',
    )

    # --- Invoice Lifecycle Status & History ---
    invoice_status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('paid', 'Paid'),
            ('cancel', 'Cancelled'),
        ],
        string='Invoice Status',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
        index=True,
        help='Lifecycle status of the invoice:\n'
             '- Draft: Invoice created but not confirmed.\n'
             '- Confirmed: Invoice finalized and awaiting payment.\n'
             '- Paid: Invoice fully paid.\n'
             '- Cancelled: Invoice cancelled / voided.'
    )
    history_ids = fields.One2many(
        'account.move.history',
        'move_id',
        string='Invoice History',
        readonly=True,
        copy=False,
        help='Immutable record of all lifecycle events and actions performed on this invoice.'
    )
    history_count = fields.Integer(
        string='History Count',
        compute='_compute_history_count',
    )
    invoice_sent = fields.Boolean(
        string='Invoice Sent',
        default=False,
        copy=False,
        readonly=True,
        help='Indicates whether the invoice has been dispatched to the customer.'
    )
    invoice_sent_date = fields.Datetime(
        string='Invoice Sent Date',
        copy=False,
        readonly=True,
        help='Timestamp when the invoice was sent to the customer.'
    )

    # --- Payment Tracking & Balances ---
    payment_ids = fields.One2many(
        'account.payment',
        'invoice_id',
        string='Recorded Payments',
        readonly=True,
        copy=False,
        help='History of all payments recorded against this invoice.'
    )
    payment_count = fields.Integer(
        string='Payment Count',
        compute='_compute_payment_count',
    )
    amount_paid = fields.Monetary(
        string='Total Paid',
        compute='_compute_payments_and_residual',
        store=True,
        copy=False,
        help='Total monetary amount received from payments on this invoice.'
    )
    amount_residual = fields.Monetary(
        string='Remaining Balance',
        compute='_compute_payments_and_residual',
        store=True,
        copy=False,
        help='Remaining unpaid balance on this invoice.'
    )
    invoice_date_due = fields.Date(
        string='Due Date',
        index=True,
        copy=False,
        default=fields.Date.context_today,
        help='Date by which the invoice payment is expected.'
    )
    is_overdue = fields.Boolean(
        string='Is Overdue',
        compute='_compute_overdue_status',
        store=True,
        index=True,
        help='Indicates whether this invoice has passed its due date with an outstanding balance.'
    )
    days_overdue = fields.Integer(
        string='Days Overdue',
        compute='_compute_overdue_status',
        store=True,
        help='Number of days this invoice has passed its due date.'
    )
    overdue_status = fields.Selection(
        selection=[
            ('not_due', 'Not Due'),
            ('overdue', 'Overdue'),
            ('settled', 'Settled'),
            ('cancelled', 'Cancelled'),
        ],
        string='Overdue Status',
        compute='_compute_overdue_status',
        store=True,
        index=True,
        help='Status reflecting whether the invoice is on time, overdue, settled, or cancelled.'
    )
    is_fully_paid = fields.Boolean(
        string='Is Fully Paid',
        compute='_compute_payments_and_residual',
        store=True,
        help='Indicates whether the invoice has been fully settled.'
    )
    is_partially_paid = fields.Boolean(
        string='Is Partially Paid',
        compute='_compute_payments_and_residual',
        store=True,
        help='Indicates whether the invoice has received partial payments.'
    )
    is_unpaid = fields.Boolean(
        string='Is Unpaid',
        compute='_compute_payments_and_residual',
        store=True,
        help='Indicates whether the invoice has zero payments recorded.'
    )

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
        'invoice_date_due',
    }

    # --- Computes ---
    @api.depends('subscription_id')
    def _compute_is_subscription_invoice(self):
        for move in self:
            move.is_subscription_invoice = bool(move.subscription_id)

    @api.depends('history_ids')
    def _compute_history_count(self):
        for move in self:
            move.history_count = len(move.history_ids)

    @api.depends('payment_ids.amount', 'payment_ids.state', 'amount_total', 'subscription_amount_total', 'invoice_status', 'state')
    def _compute_payments_and_residual(self):
        for move in self:
            is_cancelled = (getattr(move, 'invoice_status', None) == 'cancel' or getattr(move, 'state', None) == 'cancel')
            if hasattr(move, 'payment_ids') and move.payment_ids:
                if hasattr(move.payment_ids, 'filtered'):
                    payments = move.payment_ids.filtered(lambda p: getattr(p, 'state', None) != 'cancel')
                else:
                    payments = [p for p in move.payment_ids if getattr(p, 'state', None) != 'cancel']
            else:
                payments = []
            total_paid = sum(p.amount for p in payments)
            move.amount_paid = total_paid
            total = move.amount_total or move.subscription_amount_total or 0.0

            if is_cancelled:
                move.amount_residual = 0.0
                move.payment_state = 'not_paid'
                move.is_fully_paid = False
                move.is_partially_paid = False
                move.is_unpaid = False
            else:
                residual = max(0.0, round(total - total_paid, 2))
                move.amount_residual = residual

                if residual == 0.0 and total > 0 and (total_paid >= total or move.invoice_status == 'paid'):
                    move.payment_state = 'paid'
                    move.is_fully_paid = True
                    move.is_partially_paid = False
                    move.is_unpaid = False
                elif total_paid > 0:
                    move.payment_state = 'partial'
                    move.is_fully_paid = False
                    move.is_partially_paid = True
                    move.is_unpaid = False
                else:
                    move.payment_state = 'not_paid'
                    move.is_fully_paid = False
                    move.is_partially_paid = False
                    move.is_unpaid = True

    @api.depends('invoice_date_due', 'invoice_date', 'amount_residual', 'invoice_status', 'state', 'payment_state')
    def _compute_overdue_status(self):
        today = fields.Date.context_today(self)
        if isinstance(today, str):
            try:
                today = datetime.strptime(today[:10], '%Y-%m-%d').date()
            except Exception:
                today = date.today()
        elif isinstance(today, datetime):
            today = today.date()

        for move in self:
            is_cancelled = (getattr(move, 'invoice_status', None) == 'cancel' or getattr(move, 'state', None) == 'cancel')
            if is_cancelled:
                move.is_overdue = False
                move.days_overdue = 0
                move.overdue_status = 'cancelled'
                continue

            if getattr(move, 'amount_residual', 0.0) <= 0.0 and (getattr(move, 'payment_state', None) == 'paid' or getattr(move, 'invoice_status', None) == 'paid'):
                move.is_overdue = False
                move.days_overdue = 0
                move.overdue_status = 'settled'
                continue

            due_date = getattr(move, 'invoice_date_due', None) or getattr(move, 'invoice_date', None)
            if due_date and getattr(move, 'amount_residual', 0.0) > 0:
                if isinstance(due_date, str):
                    try:
                        due_d = datetime.strptime(due_date[:10], '%Y-%m-%d').date()
                    except Exception:
                        due_d = None
                elif isinstance(due_date, datetime):
                    due_d = due_date.date()
                elif isinstance(due_date, date):
                    due_d = due_date
                else:
                    due_d = None

                if due_d and due_d < today:
                    move.is_overdue = True
                    move.days_overdue = (today - due_d).days
                    move.overdue_status = 'overdue'
                    continue

            move.is_overdue = False
            move.days_overdue = 0
            move.overdue_status = 'not_due'

    @api.depends('payment_ids')
    def _compute_payment_count(self):
        for move in self:
            move.payment_count = len(move.payment_ids)

    # --- Audit History Helper ---
    def _log_history(self, action, previous_status, current_status, details=None):
        """Record an audit trail event for status changes and critical actions."""
        self.ensure_one()
        user = self.env.user
        user_name = getattr(user, 'name', None) or getattr(user, 'login', 'System')
        self.env['account.move.history'].create({
            'move_id': self.id,
            'timestamp': fields.Datetime.now(),
            'user_id': user.id if hasattr(user, 'id') else False,
            'user_name': user_name,
            'action': action,
            'previous_status': previous_status,
            'current_status': current_status,
            'details': details or '',
        })
        if hasattr(self, 'message_post'):
            try:
                self.message_post(body=_(
                    "Invoice status: <b>%s</b> &rarr; <b>%s</b> (Action: %s). %s"
                ) % (
                    previous_status or _('Initial'),
                    current_status,
                    action,
                    details or ''
                ))
            except Exception:
                pass

    # --- Authorization Helper ---
    def _check_confirm_authorization(self):
        """Enforce that only authorized internal staff or administrators can confirm an invoice."""
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
            raise AccessError(_("Access Denied: Only authorized billing staff or administrators can confirm invoices."))
        return True

    # --- CRUD Lifecycle Overrides ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('subscription_id') and not vals.get('subscription_billing_date'):
                vals['subscription_billing_date'] = vals.get('invoice_date') or fields.Date.context_today(self)
            if not vals.get('invoice_date_due'):
                vals['invoice_date_due'] = vals.get('invoice_date') or fields.Date.context_today(self)
            # Invoices always default to Draft status upon creation
            if not vals.get('invoice_status'):
                vals['invoice_status'] = 'draft'
            if vals.get('invoice_status') == 'draft' and not vals.get('state'):
                vals['state'] = 'draft'

        moves = super().create(vals_list)
        for move in moves:
            move._log_history(
                action='create',
                previous_status=None,
                current_status=move.invoice_status or 'draft',
                details=_("Invoice created in Draft status.")
            )
        return moves

    def write(self, vals):
        """Prevent invalid modifications to finalized invoices and validate status transitions."""
        # Check protection on finalized invoices
        if not self.env.context.get('ignore_protection', False):
            for move in self:
                st = move.invoice_status
                if st in ('confirmed', 'paid', 'cancel'):
                    attempted_protected = set(vals.keys()).intersection(self.PROTECTED_FINALIZED_FIELDS)
                    if attempted_protected:
                        field_names = ', '.join(sorted(attempted_protected))
                        raise ValidationError(_(
                            "Cannot modify protected field(s) [%s] on finalized invoice '%s' in '%s' status. "
                            "Finalized invoices are protected against unauthorized or invalid modifications."
                        ) % (field_names, move.name or move.id, st))

        # Check status transition validity if invoice_status is being updated directly
        new_status = vals.get('invoice_status')
        for move in self:
            current_status = move.invoice_status or 'draft'
            if new_status and new_status != current_status:
                self._validate_status_transition(move, current_status, new_status)

        # Automatic flow: auto-transition confirmed invoice to Paid when payment_state becomes 'paid'
        if vals.get('payment_state') == 'paid' and 'invoice_status' not in vals:
            for move in self:
                if move.invoice_status == 'confirmed':
                    vals['invoice_status'] = 'paid'
                    move._log_history('register_payment', 'confirmed', 'paid', _("Invoice automatically marked as Paid via payment matching."))

        # Keep native state in sync
        if new_status:
            if new_status == 'draft':
                vals.setdefault('state', 'draft')
            elif new_status == 'confirmed':
                vals.setdefault('state', 'posted')
            elif new_status == 'paid':
                vals.setdefault('state', 'posted')
                vals.setdefault('payment_state', 'paid')
            elif new_status == 'cancel':
                vals.setdefault('state', 'cancel')

        res = super().write(vals)
        return res

    def unlink(self):
        """Protect finalized invoices from deletion."""
        for move in self:
            st = move.invoice_status
            if st in ('confirmed', 'paid'):
                raise UserError(_(
                    "Cannot delete invoice '%s' in '%s' status. "
                    "Finalized and confirmed invoices are protected from deletion."
                ) % (move.name or move.id, st))
        return super().unlink()

    # --- Transition Validation Rules ---
    @api.model
    def _validate_status_transition(self, move, from_status, to_status):
        """Enforce strict business rules for invoice status transitions."""
        if from_status == 'draft':
            if to_status not in ('confirmed', 'cancel'):
                raise ValidationError(_(
                    "Invalid status transition for invoice '%s': Cannot transition from 'Draft' directly to '%s'. "
                    "Draft invoices must first be confirmed before recording payment."
                ) % (move.name or move.id, to_status.capitalize()))

        elif from_status == 'confirmed':
            if to_status not in ('paid', 'cancel'):
                raise ValidationError(_(
                    "Invalid status transition for invoice '%s': Cannot transition from 'Confirmed' to '%s'. "
                    "Confirmed invoices can only be paid or cancelled."
                ) % (move.name or move.id, to_status.capitalize()))

        elif from_status == 'paid':
            raise ValidationError(_(
                "Invalid status transition for invoice '%s': Invoice is fully paid and finalized. "
                "No status transitions or modifications are permitted on paid invoices."
            ) % (move.name or move.id))

        elif from_status == 'cancel':
            raise ValidationError(_(
                "Invalid status transition for invoice '%s': Invoice is cancelled. "
                "Cancelled invoices cannot be transitioned to '%s'."
            ) % (move.name or move.id, to_status.capitalize()))

    # --- Constraints ---
    @api.constrains('subscription_id', 'subscription_billing_date', 'invoice_date', 'state', 'invoice_status')
    def _check_unique_subscription_billing_cycle(self):
        """Ensure no duplicate invoices exist for the same subscription and billing cycle."""
        for move in self:
            if move.subscription_id and move.state != 'cancel' and move.invoice_status != 'cancel':
                cycle_date = move.subscription_billing_date or move.invoice_date
                if not cycle_date:
                    continue
                duplicate = self.search([
                    ('id', '!=', move.id),
                    ('subscription_id', '=', move.subscription_id.id),
                    ('state', '!=', 'cancel'),
                    ('invoice_status', '!=', 'cancel'),
                    '|',
                    ('subscription_billing_date', '=', cycle_date),
                    ('invoice_date', '=', cycle_date),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        "An invoice (%s) has already been generated for subscription '%s' on billing cycle '%s'. "
                        "Duplicate invoices for the same billing cycle are not allowed."
                    ) % (
                        duplicate.name or duplicate.id,
                        move.subscription_id.name,
                        cycle_date,
                    ))

    # --- Actions ---
    def action_confirm(self):
        """Confirm customer invoice: validates business rules, locks lines, and moves Draft -> Confirmed."""
        self._check_confirm_authorization()
        for move in self:
            if move.invoice_status != 'draft':
                raise ValidationError(_(
                    "Only draft invoices can be confirmed. "
                    "Invoice '%s' is currently in '%s' status."
                ) % (move.name or move.id, move.invoice_status.capitalize()))

            lines = move.invoice_line_ids if hasattr(move, 'invoice_line_ids') and move.invoice_line_ids else move.line_ids
            if not lines:
                raise ValidationError(_(
                    "Cannot confirm invoice '%s': Invoice must contain at least one line item."
                ) % (move.name or move.id))

            prev = move.invoice_status
            move.write({
                'invoice_status': 'confirmed',
                'state': 'posted',
                '_skip_history_log': True,
            })
            move._log_history(
                action='confirm',
                previous_status=prev,
                current_status='confirmed',
                details=_("Invoice confirmed and finalized awaiting payment.")
            )
        return True

    def action_post(self):
        """Native Odoo post action: routes through validated confirmation workflow."""
        self.action_confirm()
        try:
            return super().action_post()
        except Exception:
            return True

    def action_cancel(self):
        """Cancel an invoice: permitted only for Draft and Confirmed invoices."""
        for move in self:
            if move.invoice_status == 'paid':
                raise ValidationError(_(
                    "Cannot cancel invoice '%s': Invoice is fully paid. "
                    "Payments must be reversed or refunded before cancellation."
                ) % (move.name or move.id))

            if move.invoice_status == 'cancel':
                raise ValidationError(_(
                    "Invoice '%s' is already cancelled."
                ) % (move.name or move.id))

            if move.invoice_status not in ('draft', 'confirmed'):
                raise ValidationError(_(
                    "Cannot cancel invoice '%s': Cancellation is only permitted for Draft or Confirmed invoices."
                ) % (move.name or move.id))

            prev = move.invoice_status
            move.write({
                'invoice_status': 'cancel',
                'state': 'cancel',
                'amount_residual': 0.0,
                'is_overdue': False,
                'days_overdue': 0,
                'overdue_status': 'cancelled',
                '_skip_history_log': True,
            })
            if hasattr(move, '_compute_payments_and_residual'):
                move._compute_payments_and_residual()
            if hasattr(move, '_compute_overdue_status'):
                move._compute_overdue_status()
            move._log_history(
                action='cancel',
                previous_status=prev,
                current_status='cancel',
                details=_("Invoice cancelled.")
            )
        return True

    def action_register_payment(self, amount=None, payment_date=None, payment_method='bank_transfer', ref=None, notes=None):
        """Record a validated payment against this invoice.
        Stores method, amount, date, notes, links to invoice, validates amount, and prevents duplicates."""
        self.ensure_one()
        if self.invoice_status != 'confirmed':
            raise ValidationError(_(
                "Cannot record payment for invoice '%s' in '%s' status. Only confirmed invoices accept payments."
            ) % (self.name or self.id, self.invoice_status.capitalize()))

        residual = self.amount_residual if hasattr(self, 'amount_residual') and self.amount_residual > 0 else (self.amount_total or self.subscription_amount_total or 0.0)
        pay_amount = amount if amount is not None else residual

        if pay_amount <= 0:
            raise ValidationError(_("Payment amount must be strictly greater than zero."))

        if round(pay_amount - residual, 2) > 0.00:
            raise ValidationError(_(
                "Payment amount (%(amt)s) exceeds the remaining balance (%(bal)s) on invoice '%(inv)s'."
            ) % {
                'amt': pay_amount,
                'bal': residual,
                'inv': self.name or self.id,
            })

        payment_vals = {
            'invoice_id': self.id,
            'amount': pay_amount,
            'payment_date': payment_date or fields.Date.context_today(self),
            'payment_method': payment_method or 'bank_transfer',
            'payment_reference': ref,
            'notes': notes or '',
        }
        return self.env['account.payment'].create(payment_vals)

    def action_mark_paid(self, payment_ref=None, payment_date=None, amount=None, payment_method='bank_transfer', notes=None):
        """Mark invoice as Paid: validated flow permitted only for Confirmed invoices."""
        for move in self:
            if move.invoice_status == 'draft':
                raise ValidationError(_(
                    "Cannot mark draft invoice '%s' as paid. "
                    "Invoice must be confirmed before recording payment."
                ) % (move.name or move.id))

            if move.invoice_status == 'cancel':
                raise ValidationError(_(
                    "Cannot record payment on cancelled invoice '%s'."
                ) % (move.name or move.id))

            if move.invoice_status == 'paid':
                raise ValidationError(_(
                    "Invoice '%s' is already fully paid."
                ) % (move.name or move.id))

            if move.invoice_status != 'confirmed':
                raise ValidationError(_(
                    "Invalid status for payment: Invoice '%s' must be in Confirmed status (current: '%s')."
                ) % (move.name or move.id, move.invoice_status.capitalize()))

            residual = move.amount_residual if hasattr(move, 'amount_residual') and move.amount_residual > 0 else (move.amount_total or move.subscription_amount_total or 0.0)
            pay_amt = amount if amount is not None else residual

            move.action_register_payment(
                amount=pay_amt,
                payment_date=payment_date,
                payment_method=payment_method,
                ref=payment_ref,
                notes=notes or _("Full settlement payment")
            )
        return True

    def action_view_payments(self):
        """Open all payments recorded for this invoice (restricted to authorized users)."""
        self.ensure_one()
        user = self.env.user
        if not getattr(self.env, 'su', False) and hasattr(user, 'has_group'):
            authorized_groups = (
                'subscription_base.group_subscription_user',
                'subscription_base.group_subscription_manager',
                'account.group_account_invoice',
                'account.group_account_manager',
            )
            if not any(user.has_group(g) for g in authorized_groups):
                raise AccessError(_("Access Denied: Only authorized users can view payment details."))

        payments = self.payment_ids
        action = {
            'name': _('Invoice Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'tree,form',
            'domain': [('invoice_id', '=', self.id)],
            'context': {'default_invoice_id': self.id, 'default_partner_id': self.partner_id.id},
        }
        if len(payments) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = payments.id
        return action

    def action_send_invoice(self):
        """Send invoice to customer: available only for valid states (Confirmed, Paid)."""
        for move in self:
            if move.invoice_status == 'draft':
                raise ValidationError(_(
                    "Draft invoice '%s' cannot be sent to the customer. "
                    "Please confirm the invoice before sending."
                ) % (move.name or move.id))

            if move.invoice_status == 'cancel':
                raise ValidationError(_(
                    "Cannot send cancelled invoice '%s'."
                ) % (move.name or move.id))

            if not move.partner_id or not move.partner_id.email:
                customer_name = move.partner_id.name if move.partner_id else _('Unassigned')
                raise ValidationError(_(
                    "Cannot send invoice '%s': Customer '%s' does not have a valid email address."
                ) % (move.name or move.id, customer_name))

            move.write({
                'invoice_sent': True,
                'invoice_sent_date': fields.Datetime.now(),
                '_skip_history_log': True,
            })
            move._log_history(
                action='send',
                previous_status=move.invoice_status,
                current_status=move.invoice_status,
                details=_("Invoice sent to customer %s (%s).") % (move.partner_id.name, move.partner_id.email)
            )
        return True

    def action_print_invoice(self):
        """Print invoice: available for valid states, disallowed for cancelled invoices."""
        for move in self:
            if move.invoice_status == 'cancel':
                raise ValidationError(_(
                    "Cannot print cancelled invoice '%s'."
                ) % (move.name or move.id))

            move._log_history(
                action='print',
                previous_status=move.invoice_status,
                current_status=move.invoice_status,
                details=_("Invoice document printed.")
            )
        if hasattr(self.env.ref('account.account_invoices', False), 'report_action'):
            return self.env.ref('account.account_invoices').report_action(self)
        return True

    def action_download_invoice(self):
        """Download invoice PDF: available for valid states, disallowed for cancelled invoices."""
        for move in self:
            if move.invoice_status == 'cancel':
                raise ValidationError(_(
                    "Cannot download cancelled invoice '%s'."
                ) % (move.name or move.id))

            move._log_history(
                action='download',
                previous_status=move.invoice_status,
                current_status=move.invoice_status,
                details=_("Invoice PDF downloaded.")
            )
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/account.move/{self.id}/pdf',
            'target': 'self',
        }


    # --- Financial Balances, Overdue Detection & Summaries ---
    def is_invoice_unpaid(self):
        """Return True if the invoice has an outstanding balance and no payments recorded."""
        self.ensure_one()
        return not (self.invoice_status == 'cancel' or self.state == 'cancel') and self.amount_paid == 0.0 and self.amount_residual > 0.0

    def is_invoice_partially_paid(self):
        """Return True if the invoice has received partial payment but has residual balance."""
        self.ensure_one()
        return not (self.invoice_status == 'cancel' or self.state == 'cancel') and self.amount_paid > 0.0 and self.amount_residual > 0.0

    def is_invoice_fully_paid(self):
        """Return True if the invoice is fully settled with zero residual balance."""
        self.ensure_one()
        return not (self.invoice_status == 'cancel' or self.state == 'cancel') and (self.amount_residual == 0.0 and (self.amount_paid > 0.0 or self.invoice_status == 'paid'))

    @api.model
    def get_unpaid_invoices(self, domain=None):
        """Query active invoices that have zero payments recorded."""
        base_domain = [
            ('invoice_status', 'in', ['draft', 'confirmed']),
            ('state', '!=', 'cancel'),
            ('payment_state', '=', 'not_paid'),
            ('amount_residual', '>', 0),
        ]
        if domain:
            base_domain = base_domain + domain
        return self.search(base_domain)

    @api.model
    def get_partially_paid_invoices(self, domain=None):
        """Query active invoices that have received partial payments."""
        base_domain = [
            ('invoice_status', '=', 'confirmed'),
            ('state', '!=', 'cancel'),
            ('payment_state', '=', 'partial'),
            ('amount_residual', '>', 0),
        ]
        if domain:
            base_domain = base_domain + domain
        return self.search(base_domain)

    @api.model
    def get_fully_paid_invoices(self, domain=None):
        """Query fully settled invoices with zero residual balance."""
        base_domain = [
            ('invoice_status', '=', 'paid'),
            ('state', '!=', 'cancel'),
            ('amount_residual', '=', 0.0),
        ]
        if domain:
            base_domain = base_domain + domain
        return self.search(base_domain)

    @api.model
    def get_overdue_invoices(self, domain=None):
        """Query invoices that have passed their due date with an outstanding balance."""
        base_domain = [
            ('invoice_status', '=', 'confirmed'),
            ('state', '!=', 'cancel'),
            ('is_overdue', '=', True),
            ('amount_residual', '>', 0),
        ]
        if domain:
            base_domain = base_domain + domain
        return self.search(base_domain)

    @api.model
    def get_financial_summary(self, domain=None):
        """Calculate aggregate financial summary across invoices.
        Strictly excludes cancelled invoices from outstanding and overdue balances.
        """
        invoices = self if len(self) > 0 and domain is None else self.search(domain or [])

        total_invoiced = 0.0
        total_paid = 0.0
        total_outstanding = 0.0
        total_overdue = 0.0

        count_draft = 0
        count_confirmed = 0
        count_paid = 0
        count_partial = 0
        count_unpaid = 0
        count_overdue = 0
        count_cancelled = 0
        count_total = 0

        for inv in invoices:
            is_cancelled = (getattr(inv, 'invoice_status', None) == 'cancel' or getattr(inv, 'state', None) == 'cancel')
            if is_cancelled:
                count_cancelled += 1
                # Cancelled invoices are strictly excluded from total_invoiced, total_outstanding, and total_overdue
                continue

            count_total += 1
            st = getattr(inv, 'invoice_status', 'draft')
            inv_total = float(getattr(inv, 'amount_total', 0.0) or getattr(inv, 'subscription_amount_total', 0.0) or 0.0)
            inv_paid = float(getattr(inv, 'amount_paid', 0.0) or 0.0)
            inv_residual = float(getattr(inv, 'amount_residual', 0.0) or 0.0)
            is_od = bool(getattr(inv, 'is_overdue', False))

            total_invoiced += inv_total
            total_paid += inv_paid

            if st == 'draft':
                count_draft += 1
                if inv_paid == 0.0:
                    count_unpaid += 1
                elif inv_residual > 0:
                    count_partial += 1
                total_outstanding += inv_residual
            elif st == 'confirmed':
                count_confirmed += 1
                total_outstanding += inv_residual
                if is_od and inv_residual > 0:
                    total_overdue += inv_residual
                    count_overdue += 1

                if inv_paid == 0.0:
                    count_unpaid += 1
                elif inv_residual > 0:
                    count_partial += 1
            elif st == 'paid':
                count_paid += 1

        return {
            'total_invoiced': round(total_invoiced, 2),
            'total_paid': round(total_paid, 2),
            'total_outstanding': round(total_outstanding, 2),
            'total_overdue': round(total_overdue, 2),
            'count_total': count_total,
            'count_draft': count_draft,
            'count_confirmed': count_confirmed,
            'count_paid': count_paid,
            'count_partial': count_partial,
            'count_unpaid': count_unpaid,
            'count_overdue': count_overdue,
            'count_cancelled': count_cancelled,
        }
