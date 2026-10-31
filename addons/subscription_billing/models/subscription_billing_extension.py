# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

import logging
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SubscriptionSubscriptionLine(models.Model):
    """Extend subscription lines with taxes and discounts for accurate billing."""
    _inherit = 'subscription.subscription.line'

    discount = fields.Float(
        string='Discount (%)',
        digits='Discount',
        default=0.0,
        help='Discount percentage applied to this line item.'
    )
    tax_ids = fields.Many2many(
        'account.tax',
        'subscription_billing_line_tax_rel',
        'line_id',
        'tax_id',
        string='Taxes',
        domain="[('type_tax_use', '=', 'sale')]",
        help='Taxes applicable to this recurring line.'
    )

    @api.depends('quantity', 'price_unit', 'discount')
    def _compute_price_subtotal(self):
        """Compute subtotal taking discount into account."""
        for line in self:
            discount_factor = 1.0 - (line.discount or 0.0) / 100.0
            line.price_subtotal = line.quantity * line.price_unit * discount_factor


class SubscriptionSubscription(models.Model):
    """Extend subscription.subscription with automated invoice generation and billing history."""
    _inherit = 'subscription.subscription'

    invoice_ids = fields.One2many(
        'account.move',
        'subscription_id',
        string='Invoices',
        readonly=True,
    )
    invoice_count = fields.Integer(
        string='Invoice Count',
        compute='_compute_invoice_count',
    )

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for sub in self:
            sub.invoice_count = len(sub.invoice_ids)

    def action_view_invoices(self):
        """Open invoices linked to this subscription."""
        self.ensure_one()
        invoices = self.invoice_ids
        action = {
            'name': _('Subscription Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,kanban,form',
            'domain': [('id', 'in', invoices.ids)],
            'context': {'default_move_type': 'out_invoice', 'default_subscription_id': self.id},
        }
        if len(invoices) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = invoices.id
        return action

    def _get_next_billing_date(self, current_date=None):
        """Calculate the next recurring billing date based on plan interval and period."""
        self.ensure_one()
        current = current_date or self.next_billing_date or fields.Date.context_today(self)
        if not self.plan_id:
            return current + relativedelta(months=1)

        interval = self.plan_id.billing_interval or 1
        period = self.plan_id.billing_period or 'monthly'
        delta = relativedelta(
            days=interval if period == 'daily' else 0,
            weeks=interval if period == 'weekly' else 0,
            months=interval if period == 'monthly' else 0,
            years=interval if period == 'yearly' else 0,
        )
        return current + delta

    def _prepare_invoice_line_vals(self, line, fiscal_position=None):
        """Prepare values dictionary for creating an invoice line from a subscription line."""
        self.ensure_one()
        # Determine applicable taxes
        taxes = line.tax_ids
        if not taxes and line.product_id:
            taxes = line.product_id.taxes_id.filtered(lambda t: t.company_id == self.company_id)
        if fiscal_position and taxes:
            taxes = fiscal_position.map_tax(taxes)

        # Line description / name
        product = line.product_id
        name = product.display_name or product.name or _('Subscription Item')
        if hasattr(product, 'get_product_multiline_description_sale'):
            description = product.get_product_multiline_description_sale()
            if description:
                name = description

        return {
            'product_id': product.id,
            'name': name,
            'quantity': line.quantity,
            'price_unit': line.price_unit,
            'discount': line.discount or 0.0,
            'tax_ids': [(6, 0, taxes.ids)] if taxes else [(5, 0, 0)],
        }

    def _prepare_invoice_vals(self, billing_date):
        """Prepare values dictionary for creating a customer invoice from a subscription."""
        self.ensure_one()
        partner = self.partner_id
        fiscal_position = partner.property_account_position_id if hasattr(partner, 'property_account_position_id') else False
        if not fiscal_position and hasattr(self.env['account.fiscal.position'], '_get_fiscal_position'):
            fiscal_position = self.env['account.fiscal.position']._get_fiscal_position(partner)

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

        lines_vals = [
            (0, 0, self._prepare_invoice_line_vals(line, fiscal_position=fiscal_position))
            for line in self.line_ids
        ]

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'partner_shipping_id': partner.address_get(['delivery'])['delivery'] if hasattr(partner, 'address_get') else partner.id,
            'subscription_id': self.id,
            'subscription_billing_date': billing_date,
            'invoice_date': billing_date,
            'currency_id': self.currency_id.id if self.currency_id else self.env.company.currency_id.id,
            'company_id': self.company_id.id,
            'invoice_origin': self.name,
            'ref': _("Subscription %s - Billing Cycle %s") % (self.name, billing_date),
            'invoice_line_ids': lines_vals,
        }

        if journal:
            invoice_vals['journal_id'] = journal.id

        if partner.property_payment_term_id:
            invoice_vals['invoice_payment_term_id'] = partner.property_payment_term_id.id

        if fiscal_position:
            invoice_vals['fiscal_position_id'] = fiscal_position.id

        return invoice_vals

    def action_generate_invoice(self, billing_date=None, auto_post=False):
        """
        Generate a customer invoice for this subscription for the designated billing date.

        Ensures:
        - Subscriptions must be active to be billed.
        - Idempotency: no duplicate invoice is created for the same subscription and billing cycle.
        - Next billing date is updated ONLY upon successful invoice creation.
        """
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_("Invoices can only be generated for active subscriptions (Contract '%s' is in state '%s').") % (self.name, self.state))

        if not self.partner_id:
            raise UserError(_("Cannot generate invoice for subscription '%s': no customer is assigned.") % self.name)

        if not self.line_ids:
            raise UserError(_("Cannot generate invoice for subscription '%s': no recurring product lines exist.") % self.name)

        target_billing_date = billing_date or self.next_billing_date or fields.Date.context_today(self)

        # 1. Idempotency Check: prevent duplicate invoices for the same subscription and cycle
        existing_invoice = self.env['account.move'].search([
            ('subscription_id', '=', self.id),
            ('state', '!=', 'cancel'),
            '|',
            ('subscription_billing_date', '=', target_billing_date),
            ('invoice_date', '=', target_billing_date),
        ], limit=1)

        if existing_invoice:
            _logger.warning(
                "Subscription '%s' already has an invoice (%s) for billing cycle %s. Skipping duplicate generation.",
                self.name, existing_invoice.name or existing_invoice.id, target_billing_date
            )
            return existing_invoice

        # 2. Build values and create invoice
        invoice_vals = self._prepare_invoice_vals(target_billing_date)
        invoice = self.env['account.move'].create(invoice_vals)

        # 3. Unique invoice number: trigger Odoo accounting sequence or sequence fallback
        if auto_post and hasattr(invoice, 'action_post'):
            try:
                invoice.action_post()
            except Exception as e:
                _logger.info("Could not auto-post invoice %s for subscription %s: %s", invoice.id, self.name, str(e))

        if not invoice.name or invoice.name == '/':
            seq_num = (
                self.env['ir.sequence'].next_by_code('subscription.invoice')
                or self.env['ir.sequence'].next_by_code('account.move')
            )
            if seq_num:
                invoice.name = seq_num

        # 4. Advance next billing date ONLY after successful creation of invoice
        next_date = self._get_next_billing_date(target_billing_date)
        if self.date_end and next_date > self.date_end:
            self.next_billing_date = False
            _logger.info("Subscription '%s' reached contract end date %s. Next billing date cleared.", self.name, self.date_end)
        else:
            self.next_billing_date = next_date

        # Log chatter notification if mail module is active
        if hasattr(self, 'message_post'):
            self.message_post(body=_(
                "Recurring invoice <a href='#' data-oe-model='account.move' data-oe-id='%d'>%s</a> "
                "generated for billing cycle <b>%s</b>. Next billing date set to <b>%s</b>."
            ) % (
                invoice.id,
                invoice.name or _('Draft Invoice'),
                target_billing_date,
                self.next_billing_date or _('Contract Ended'),
            ))

        return invoice

    @api.model
    def _cron_generate_recurring_invoices(self):
        """
        Scheduled Action (cron): automatically generate invoices for all active subscriptions
        whose next billing date has arrived.

        Failed operations on individual subscriptions are isolated with savepoints and logged
        so that failed operations do not crash the batch or incorrectly advance billing dates.
        """
        today = fields.Date.context_today(self)
        due_subscriptions = self.search([
            ('state', '=', 'active'),
            ('next_billing_date', '<=', today),
        ])
        _logger.info("Cron recurring billing: Found %d active subscriptions due on or before %s", len(due_subscriptions), today)

        generated_invoices = self.env['account.move']
        for subscription in due_subscriptions:
            try:
                with self.env.cr.savepoint():
                    invoice = subscription.action_generate_invoice()
                    if invoice:
                        generated_invoices |= invoice
            except Exception as e:
                _logger.exception(
                    "Cron recurring billing failed for subscription '%s' (ID: %d): %s. "
                    "Next billing date was NOT advanced.",
                    subscription.name, subscription.id, str(e)
                )

        _logger.info("Cron recurring billing finished: %d invoice(s) generated.", len(generated_invoices))
        return generated_invoices
