# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

import logging
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .invoice_calculator import InvoiceCalculator

_logger = logging.getLogger(__name__)


class SubscriptionSubscriptionLine(models.Model):
    """Extend subscription lines with taxes and discounts for accurate billing."""
    _inherit = 'subscription.subscription.line'

    discount_type = fields.Selection(
        selection=[
            ('percent', 'Percentage'),
            ('fixed', 'Fixed Amount'),
        ],
        string='Discount Type',
        default='percent',
        help='Type of discount: percentage of line total, or a fixed monetary deduction.',
    )
    discount = fields.Float(
        string='Discount (%)',
        digits='Discount',
        default=0.0,
        help='Discount percentage applied to this line item.',
    )
    discount_fixed = fields.Monetary(
        string='Discount (Fixed)',
        currency_field='currency_id',
        default=0.0,
        help='Fixed monetary amount to deduct from this line item.',
    )
    tax_ids = fields.Many2many(
        'account.tax',
        'subscription_billing_line_tax_rel',
        'line_id',
        'tax_id',
        string='Taxes',
        domain="[('type_tax_use', '=', 'sale')]",
        help='Taxes applicable to this recurring line.',
    )
    price_tax = fields.Monetary(
        string='Tax Amount',
        compute='_compute_price_subtotal',
        store=True,
        currency_field='currency_id',
        help='Computed tax amount for this line.',
    )
    price_total = fields.Monetary(
        string='Total',
        compute='_compute_price_subtotal',
        store=True,
        currency_field='currency_id',
        help='Line total including taxes.',
    )

    @api.depends('quantity', 'price_unit', 'discount_type', 'discount', 'discount_fixed', 'tax_ids')
    def _compute_price_subtotal(self):
        """Compute subtotal, tax, and total using Decimal arithmetic."""
        calc = InvoiceCalculator
        for line in self:
            subtotal = calc.calculate_line_subtotal(
                quantity=line.quantity,
                price_unit=line.price_unit,
                discount_type=line.discount_type or 'percent',
                discount_percent=line.discount or 0.0,
                discount_fixed=line.discount_fixed or 0.0,
            )
            line.price_subtotal = subtotal

            # Calculate taxes
            taxes = line.tax_ids or []
            tax_total, _details = calc.calculate_line_taxes(subtotal, taxes)
            line.price_tax = tax_total
            line.price_total = calc._round(
                calc._to_decimal(subtotal) + calc._to_decimal(tax_total)
            )


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
    amount_untaxed = fields.Monetary(
        string='Untaxed Amount',
        compute='_compute_amounts',
        store=True,
        tracking=True,
    )
    amount_tax = fields.Monetary(
        string='Tax Amount',
        compute='_compute_amounts',
        store=True,
        tracking=True,
    )

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for sub in self:
            sub.invoice_count = len(sub.invoice_ids)

    @api.depends('line_ids.price_subtotal', 'line_ids.price_tax', 'line_ids.price_total')
    def _compute_amounts(self):
        """Compute subscription-level untaxed, tax, and total amounts."""
        calc = InvoiceCalculator
        for sub in self:
            sub.amount_untaxed = calc._round(
                sum(calc._to_decimal(l.price_subtotal) for l in sub.line_ids)
            )
            sub.amount_tax = calc._round(
                sum(calc._to_decimal(l.price_tax) for l in sub.line_ids)
            )
            sub.amount_total = calc._round(
                calc._to_decimal(sub.amount_untaxed) + calc._to_decimal(sub.amount_tax)
            )

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
        """Prepare values dictionary for creating an invoice line from a subscription line.

        For fixed discounts, the discount amount is pre-applied into the price_unit
        so that Odoo's native invoice line (which only supports percentage discounts)
        works correctly.  The original values are preserved in the calculation snapshot.
        """
        self.ensure_one()
        calc = InvoiceCalculator

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

        # Handle discount: pre-apply fixed discounts into price_unit for Odoo compatibility
        discount_type = line.discount_type or 'percent'
        invoice_price_unit = line.price_unit
        invoice_discount = 0.0

        if discount_type == 'percent':
            invoice_discount = line.discount or 0.0
        elif discount_type == 'fixed':
            # Calculate effective unit price after fixed discount
            qty = line.quantity or 1.0
            if qty > 0:
                per_unit_discount = calc._round(
                    calc._to_decimal(line.discount_fixed or 0.0) / calc._to_decimal(qty)
                )
                invoice_price_unit = calc._round(
                    calc._to_decimal(line.price_unit) - calc._to_decimal(per_unit_discount)
                )
            invoice_discount = 0.0  # Already applied to price_unit

        return {
            'product_id': product.id,
            'name': name,
            'quantity': line.quantity,
            'price_unit': invoice_price_unit,
            'discount': invoice_discount,
            'tax_ids': [(6, 0, taxes.ids)] if taxes else [(5, 0, 0)],
        }

    def _build_lines_data_for_snapshot(self):
        """Build a list of line data dicts for the InvoiceCalculator from subscription lines."""
        self.ensure_one()
        lines_data = []
        for line in self.line_ids:
            taxes_data = []
            taxes = line.tax_ids
            if not taxes and line.product_id:
                taxes = line.product_id.taxes_id.filtered(
                    lambda t: t.company_id == self.company_id
                )
            for tax in taxes:
                taxes_data.append({
                    'name': tax.name,
                    'amount': tax.amount,
                    'amount_type': tax.amount_type,
                })

            lines_data.append({
                'product_name': line.product_id.display_name or line.product_id.name or '',
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount_type': line.discount_type or 'percent',
                'discount_percent': line.discount or 0.0,
                'discount_fixed': line.discount_fixed or 0.0,
                'taxes': taxes_data,
            })
        return lines_data

    def _prepare_invoice_vals(self, billing_date):
        """Prepare values dictionary for creating a customer invoice from a subscription."""
        self.ensure_one()
        calc = InvoiceCalculator
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

        # Build calculation snapshot
        lines_data = self._build_lines_data_for_snapshot()
        totals = calc.calculate_invoice_totals(lines_data)
        currency_name = (self.currency_id.name if self.currency_id
                         else self.env.company.currency_id.name)
        snapshot_json = calc.build_calculation_snapshot(
            lines_data=totals['lines'],
            totals=totals,
            currency_name=currency_name,
        )

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
            # Historical calculation snapshot
            'subscription_calculation_details': snapshot_json,
            'subscription_amount_untaxed': totals['amount_untaxed'],
            'subscription_amount_tax': totals['amount_tax'],
            'subscription_amount_total': totals['amount_total'],
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
        - Subscriptions must be in 'active' status to be billed.
        - Checks billing dates and plan frequency.
        - Prevents duplicate invoices for the same subscription and billing cycle (idempotency).
        - Generates unique invoice numbers.
        - Handles failures safely: advances next billing date ONLY upon successful invoice creation.
        """
        self.ensure_one()
        # 1. Validate subscription status
        if self.state != 'active':
            state_label = dict(self._fields['state'].selection).get(self.state, self.state)
            raise UserError(_(
                "Invoices can only be generated for active subscriptions. "
                "Contract '%s' is currently in '%s' status."
            ) % (self.name, state_label))

        if not self.partner_id:
            raise UserError(_("Cannot generate invoice for subscription '%s': no customer is assigned.") % self.name)

        if not self.line_ids:
            raise UserError(_("Cannot generate invoice for subscription '%s': no recurring product lines exist.") % self.name)

        target_billing_date = billing_date or self.next_billing_date or self.date_start or fields.Date.context_today(self)

        # Validate date boundaries
        if self.date_start and target_billing_date < self.date_start:
            raise UserError(_(
                "Cannot generate invoice for date %s prior to subscription start date (%s)."
            ) % (target_billing_date, self.date_start))

        if self.date_end and target_billing_date > self.date_end:
            raise UserError(_(
                "Cannot generate invoice for date %s past subscription end date (%s)."
            ) % (target_billing_date, self.date_end))

        # 2. Idempotency Check: prevent duplicate invoices for the same subscription and billing cycle
        existing_invoice = self.env['account.move'].search([
            ('subscription_id', '=', self.id),
            ('state', '!=', 'cancel'),
            '|',
            ('subscription_billing_date', '=', target_billing_date),
            ('invoice_date', '=', target_billing_date),
        ], limit=1)

        if existing_invoice:
            _logger.warning(
                "Subscription '%s' already has an active invoice (%s) for billing cycle %s. Skipping duplicate generation.",
                self.name, existing_invoice.name or existing_invoice.id, target_billing_date
            )
            return existing_invoice

        # 3. Build values and store invoice record in database
        invoice_vals = self._prepare_invoice_vals(target_billing_date)
        invoice = self.env['account.move'].create(invoice_vals)

        # 4. Generate unique invoice number
        if auto_post and hasattr(invoice, 'action_post'):
            try:
                invoice.action_post()
            except Exception as e:
                _logger.info("Could not auto-post invoice %s for subscription %s: %s", invoice.id, self.name, str(e))

        if not invoice.name or invoice.name in ('/', _('New'), 'False'):
            seq_num = (
                self.env['ir.sequence'].next_by_code('subscription.invoice')
                or self.env['ir.sequence'].next_by_code('account.move')
            )
            year_str = target_billing_date.strftime('%Y') if hasattr(target_billing_date, 'strftime') else str(fields.Date.today().year)
            invoice.name = seq_num or _('INV/%s/%05d') % (year_str, invoice.id)

        # 5. Advance next billing date ONLY after successful creation and numbering
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
        due for billing.

        Ensures:
        - Includes active subscriptions whose next billing date has arrived (or start date if not set).
        - Failed operations on individual subscriptions are isolated with savepoints and logged
          so that failed operations do not crash the batch or advance billing dates incorrectly.
        """
        today = fields.Date.context_today(self)
        due_subscriptions = self.search([
            ('state', '=', 'active'),
            '|',
            ('next_billing_date', '<=', today),
            '&',
            ('next_billing_date', '=', False),
            ('date_start', '<=', today),
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
