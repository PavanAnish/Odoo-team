# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    """Payment record linked to customer invoices with strict amount validation,
    idempotency duplicate prevention, method tracking, and authorization guards."""
    _name = 'account.payment'
    _description = 'Payment Recording & Invoice Settlement'
    _order = 'payment_date desc, id desc'

    name = fields.Char(
        string='Payment Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
        help='Unique payment sequence or reference.'
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        required=True,
        ondelete='cascade',
        index=True,
        domain="[('move_type', '=', 'out_invoice')]",
        help='Invoice to which this payment is credited.'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='invoice_id.partner_id',
        store=True,
        readonly=True,
        index=True,
        help='Customer linked to this payment.'
    )
    amount = fields.Monetary(
        string='Payment Amount',
        required=True,
        currency_field='currency_id',
        help='Monetary amount received.'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='invoice_id.currency_id',
        store=True,
        readonly=True
    )
    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.context_today,
        help='Date when payment was made or settled.'
    )
    payment_method = fields.Selection(
        selection=[
            ('credit_card', 'Credit / Debit Card'),
            ('bank_transfer', 'Bank Transfer'),
            ('cash', 'Cash'),
            ('direct_debit', 'Direct Debit'),
            ('check', 'Check / Cheque'),
            ('other', 'Other'),
        ],
        string='Payment Method',
        required=True,
        default='bank_transfer',
        help='Channel through which payment was received.'
    )
    payment_reference = fields.Char(
        string='Transaction Reference',
        copy=False,
        index=True,
        help='External bank or gateway transaction identifier (e.g. TXN-1234).'
    )
    notes = fields.Text(
        string='Payment Notes / Memo',
        help='Internal operational notes or receipt memo for this payment.'
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('posted', 'Recorded'),
            ('cancel', 'Cancelled'),
        ],
        string='Status',
        default='posted',
        required=True,
        copy=False,
        readonly=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Recorded By',
        default=lambda self: self.env.user,
        readonly=True,
        help='Internal user who recorded this payment.'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='invoice_id.company_id',
        store=True,
        readonly=True
    )

    # --- Authorization Helper ---
    def _check_payment_authorization(self):
        """Ensure only authorized internal staff or administrators can record payments."""
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
            raise AccessError(_("Access Denied: Only authorized billing staff or administrators can record payments."))
        return True

    # --- Constraints & Validations ---
    @api.constrains('amount', 'invoice_id')
    def _check_payment_amount(self):
        """Validate payment amount is strictly positive and does not exceed residual balance."""
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_("Payment amount must be strictly greater than zero."))

            invoice = payment.invoice_id
            if not invoice:
                continue

            # Ensure invoice is in a valid state to accept payments
            if invoice.invoice_status == 'draft':
                raise ValidationError(_(
                    "Cannot record payment for invoice '%s' in Draft status. "
                    "Invoices must be confirmed before recording payments."
                ) % (invoice.name or invoice.id))

            if invoice.invoice_status == 'cancel':
                raise ValidationError(_(
                    "Cannot record payment for invoice '%s': Invoice is cancelled."
                ) % (invoice.name or invoice.id))

            # Compute remaining balance on invoice excluding this record
            other_payments = self.search([
                ('invoice_id', '=', invoice.id),
                ('id', '!=', payment.id),
                ('state', '!=', 'cancel')
            ])
            total_other = sum(p.amount for p in other_payments)
            total_invoice = invoice.amount_total or invoice.subscription_amount_total or 0.0
            remaining_before = total_invoice - total_other

            if round(payment.amount - remaining_before, 2) > 0.00:
                raise ValidationError(_(
                    "Payment amount (%(amt)s) exceeds the remaining balance (%(bal)s) on invoice '%(inv)s'."
                ) % {
                    'amt': payment.amount,
                    'bal': remaining_before,
                    'inv': invoice.name or invoice.id,
                })

    @api.constrains('payment_reference', 'invoice_id')
    def _check_duplicate_payment(self):
        """Prevent duplicate payment submissions with identical transaction reference or submission details."""
        for payment in self:
            if not payment.invoice_id:
                continue

            # 1. Unique transaction reference per invoice
            if payment.payment_reference:
                duplicate_ref = self.search([
                    ('id', '!=', payment.id),
                    ('invoice_id', '=', payment.invoice_id.id),
                    ('payment_reference', '=', payment.payment_reference),
                    ('state', '!=', 'cancel'),
                ], limit=1)
                if duplicate_ref:
                    raise ValidationError(_(
                        "Duplicate payment detected: A payment with transaction reference '%(ref)s' "
                        "has already been recorded for invoice '%(inv)s' (Payment %(pay)s)."
                    ) % {
                        'ref': payment.payment_reference,
                        'inv': payment.invoice_id.name or payment.invoice_id.id,
                        'pay': duplicate_ref.name or duplicate_ref.id,
                    })

            # 2. Duplicate submission prevention without reference (identical amount, date, method)
            duplicate_identical = self.search([
                ('id', '!=', payment.id),
                ('invoice_id', '=', payment.invoice_id.id),
                ('amount', '=', payment.amount),
                ('payment_date', '=', payment.payment_date),
                ('payment_method', '=', payment.payment_method),
                ('state', '!=', 'cancel'),
            ], limit=1)
            if duplicate_identical and not payment.payment_reference:
                raise ValidationError(_(
                    "Duplicate payment submission: An identical payment of %(amt)s was already recorded "
                    "on %(date)s via %(method)s for invoice '%(inv)s'."
                ) % {
                    'amt': payment.amount,
                    'date': payment.payment_date,
                    'method': dict(payment._fields['payment_method'].selection).get(payment.payment_method, payment.payment_method),
                    'inv': payment.invoice_id.name or payment.invoice_id.id,
                })

    # --- CRUD Lifecycle Overrides ---
    @api.model_create_multi
    def create(self, vals_list):
        self._check_payment_authorization()
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('New'):
                seq = (
                    self.env['ir.sequence'].next_by_code('account.payment')
                    or self.env['ir.sequence'].next_by_code('subscription.payment')
                )
                vals['name'] = seq or f"PAY/{fields.Date.today().year}/{self.env['account.payment'].search_count([]) + 1:05d}"

        payments = super().create(vals_list)

        for payment in payments:
            invoice = payment.invoice_id
            if invoice:
                # Trigger residual recomputation
                if hasattr(invoice, '_compute_payments_and_residual'):
                    invoice._compute_payments_and_residual()

                other_payments = self.search([
                    ('invoice_id', '=', invoice.id),
                    ('state', '!=', 'cancel')
                ])
                total_paid = sum(p.amount for p in other_payments)
                total_inv = invoice.amount_total or invoice.subscription_amount_total or 0.0
                residual = max(0.0, round(total_inv - total_paid, 2))

                is_full = (residual == 0.0)
                method_label = dict(payment._fields['payment_method'].selection).get(payment.payment_method, payment.payment_method)
                detail_msg = _(
                    "Payment %(ref)s of %(amt)s recorded via %(method)s (Ref: %(tx)s). "
                    "Remaining balance: %(bal)s. Notes: %(notes)s"
                ) % {
                    'ref': payment.name,
                    'amt': payment.amount,
                    'method': method_label,
                    'tx': payment.payment_reference or _('N/A'),
                    'bal': residual,
                    'notes': payment.notes or _('None'),
                }

                if is_full:
                    invoice.write({
                        'invoice_status': 'paid',
                        'payment_state': 'paid',
                        '_skip_history_log': True,
                    })
                    invoice._log_history('register_payment', 'confirmed', 'paid', detail_msg)
                else:
                    invoice.write({
                        'payment_state': 'partial',
                        '_skip_history_log': True,
                    })
                    invoice._log_history('register_payment', invoice.invoice_status, invoice.invoice_status, detail_msg)

        return payments

