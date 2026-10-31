# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError

_logger = logging.getLogger(__name__)


class SubscriptionSubscription(models.Model):
    """Core model managing quotations and subscription contracts."""
    _name = 'subscription.subscription'
    _description = 'Subscription Quotation & Contract'
    _inherit = ['subscription.audit.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date_quotation desc, id desc'

    # --- Reference and Header Information ---
    name = fields.Char(
        string='Quotation Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
        help='Unique quotation and subscription reference.'
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('quotation', 'Quotation Sent'),
            ('confirmed', 'Confirmed'),
            ('active', 'Active'),
            ('paused', 'Paused'),
            ('closed', 'Closed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        copy=False,
    )

    # --- Customer Information ---
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
        domain="[('is_subscription_customer', '=', True)]",
        help='Customer linked to this quotation or subscription.'
    )
    partner_email = fields.Char(
        string='Email',
        related='partner_id.email',
        readonly=True,
        help='Primary email of the customer.'
    )
    partner_phone = fields.Char(
        string='Phone',
        related='partner_id.phone',
        readonly=True,
        help='Contact phone number.'
    )
    partner_mobile = fields.Char(
        string='Mobile',
        related='partner_id.mobile',
        readonly=True,
        help='Mobile contact number.'
    )

    # --- Plan & Dates ---
    plan_id = fields.Many2one(
        'subscription.plan',
        string='Subscription Plan',
        required=True,
        tracking=True,
        help='Subscription plan defining billing frequency, trial period, and eligibility.'
    )
    date_quotation = fields.Date(
        string='Quotation Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True,
        help='Date when this quotation was prepared.'
    )
    date_expiration = fields.Date(
        string='Expiry Date',
        tracking=True,
        help='Date until which this quotation remains valid and eligible for confirmation.'
    )
    date_start = fields.Date(
        string='Start Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True,
        help='Effective contract start date once confirmed.'
    )
    date_end = fields.Date(
        string='End Date',
        help='Optional scheduled termination date.'
    )
    next_billing_date = fields.Date(
        string='Next Billing Date',
        tracking=True,
        help='Scheduled date for the next recurring invoice generation.'
    )

    # --- Discount Rules ---
    discount_id = fields.Many2one(
        'subscription.discount',
        string='Coupon / Discount Rule',
        tracking=True,
        help='Promotional or coupon discount rule applied to the overall quotation.'
    )
    discount_type = fields.Selection(
        related='discount_id.discount_type',
        string='Discount Type',
        readonly=True,
    )
    discount_value = fields.Float(
        related='discount_id.discount_value',
        string='Discount Rate',
        readonly=True,
    )

    # --- Product Lines ---
    line_ids = fields.One2many(
        'subscription.subscription.line',
        'subscription_id',
        string='Product Lines',
        copy=True,
    )

    # --- Financial Summary ---
    amount_untaxed = fields.Monetary(
        string='Subtotal (Untaxed)',
        compute='_compute_amounts',
        store=True,
        tracking=True,
        help='Sum of all product lines before order-level discounts and taxes.'
    )
    amount_discount = fields.Monetary(
        string='Discount Amount',
        compute='_compute_amounts',
        store=True,
        tracking=True,
        help='Total amount deducted via line discounts and coupon discount rules.'
    )
    amount_tax = fields.Monetary(
        string='Tax Amount',
        compute='_compute_amounts',
        store=True,
        tracking=True,
        help='Total calculated taxes applied across quotation lines.'
    )
    amount_total = fields.Monetary(
        string='Final Total Amount',
        compute='_compute_amounts',
        store=True,
        tracking=True,
        help='Final quotation total including taxes minus eligible discounts.'
    )

    _sql_constraints = [
        ('name_company_unique', 'unique(name, company_id)', 'The quotation reference must be unique per company!')
    ]

    # --- Access Control & Backend Security ---
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('subscription_base.group_subscription_user'):
            raise AccessError(_("Access Denied: Only authorized internal staff can create subscription quotations."))
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('subscription.subscription') or _('QT/%s/00001') % fields.Date.context_today(self).year
        records = super().create(vals_list)
        for rec in records:
            rec._check_duplicate_reference()
            rec._validate_quotation_integrity()
        return records

    def write(self, vals):
        if not self.env.user.has_group('subscription_base.group_subscription_user'):
            raise AccessError(_("Access Denied: Only authorized internal staff can edit subscription quotations."))
        # Prevent editing locked / cancelled / closed records unless resetting or updating state
        for rec in self:
            if rec.state in ('cancelled', 'closed') and not any(k in vals for k in ('state', 'notes')):
                raise UserError(_("Cannot modify a cancelled or closed subscription record."))
        res = super().write(vals)
        for rec in self:
            rec._check_duplicate_reference()
            rec._validate_quotation_integrity()
        return res

    # --- Calculation Engine ---
    @api.depends('line_ids.price_subtotal', 'line_ids.price_tax', 'discount_id', 'currency_id')
    def _compute_amounts(self):
        """Compute accurate quotation breakdown: untaxed subtotal, discounts, taxes, and final total."""
        for sub in self:
            currency = sub.currency_id or sub.company_id.currency_id
            raw_subtotal = sum(sub.line_ids.mapped('price_subtotal'))
            line_tax_total = sum(sub.line_ids.mapped('price_tax'))
            line_discounts = sum(
                (l.quantity * l.price_unit * (l.discount / 100.0)) for l in sub.line_ids if l.discount
            )

            # Calculate order-level discount if rule is present
            order_discount = 0.0
            if sub.discount_id:
                try:
                    sub.discount_id.validate_eligibility(
                        quotation_amount=raw_subtotal,
                        target_date=sub.date_quotation or fields.Date.context_today(sub)
                    )
                    order_discount = sub.discount_id.calculate_discount_amount(raw_subtotal)
                except ValidationError:
                    order_discount = 0.0

            total_discount = line_discounts + order_discount
            # Final total = raw_subtotal - order_discount + tax
            final_total = max(0.0, raw_subtotal - order_discount) + line_tax_total

            sub.amount_untaxed = currency.round(raw_subtotal) if currency else raw_subtotal
            sub.amount_discount = currency.round(total_discount) if currency else total_discount
            sub.amount_tax = currency.round(line_tax_total) if currency else line_tax_total
            sub.amount_total = currency.round(final_total) if currency else final_total

    # --- Integrity & Business Validations ---
    def _check_duplicate_reference(self):
        """Ensure no duplicate quotation reference exists in the same company."""
        self.ensure_one()
        if self.name and self.name != _('New'):
            domain = [
                ('name', '=', self.name),
                ('id', '!=', self.id),
                ('company_id', '=', self.company_id.id),
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(_("A quotation with reference '%s' already exists.") % self.name)

    def _validate_quotation_integrity(self):
        """Comprehensive quotation validation covering customer, plan, dates, and quantities."""
        self.ensure_one()
        # 1. Customer validation
        if not self.partner_id:
            raise ValidationError(_("Please select a customer for the quotation."))
        if hasattr(self.partner_id, 'active') and not self.partner_id.active:
            raise ValidationError(_("The selected customer '%s' is inactive.") % self.partner_id.name)
        if hasattr(self.partner_id, 'is_subscription_customer') and not self.partner_id.is_subscription_customer:
            # Auto-flag customer if authorized, or validate eligibility
            self.partner_id.is_subscription_customer = True

        # 2. Date consistency
        if self.date_quotation and self.date_expiration and self.date_expiration < self.date_quotation:
            raise ValidationError(_("Quotation expiration date (%s) cannot be earlier than quotation date (%s).")
                                  % (self.date_expiration, self.date_quotation))

        # 3. Plan validations
        if self.plan_id:
            # Plan availability and dates
            avail, reason = self.plan_id.is_available(target_date=self.date_quotation)
            if not avail:
                raise ValidationError(_("Invalid Subscription Plan: %s") % reason)

            # Plan minimum quantity
            if self.line_ids:
                total_qty = sum(self.line_ids.mapped('quantity'))
                if self.plan_id.min_quantity and total_qty < self.plan_id.min_quantity:
                    raise ValidationError(
                        _("The selected subscription plan '%s' requires a minimum product quantity of %s. Current total is %s.")
                        % (self.plan_id.name, self.plan_id.min_quantity, total_qty)
                    )

        # 4. Discount rule validation
        if self.discount_id and self.amount_untaxed > 0:
            self.discount_id.validate_eligibility(
                quotation_amount=self.amount_untaxed,
                target_date=self.date_quotation
            )

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Warn if an invalid or inactive customer is picked."""
        if self.partner_id and not self.partner_id.is_subscription_customer:
            self.partner_id.is_subscription_customer = True

    @api.onchange('plan_id', 'date_quotation')
    def _onchange_plan_id(self):
        """Feedback on plan selection."""
        if self.plan_id:
            avail, reason = self.plan_id.is_available(target_date=self.date_quotation)
            if not avail:
                return {'warning': {
                    'title': _("Plan Availability Warning"),
                    'message': reason,
                }}

    @api.onchange('discount_id')
    def _onchange_discount_id(self):
        """Validate coupon discount when selected on the form."""
        if self.discount_id:
            try:
                self.discount_id.validate_eligibility(
                    quotation_amount=self.amount_untaxed,
                    target_date=self.date_quotation
                )
            except ValidationError as e:
                return {'warning': {
                    'title': _("Ineligible Discount"),
                    'message': str(e),
                }}

    # --- Quotation Lifecycle Actions ---
    def action_send_quotation(self):
        """Transition quotation from draft to quotation sent."""
        for sub in self:
            if sub.state != 'draft':
                raise ValidationError(_("Only draft quotations can be marked as 'Quotation Sent'."))
            if not sub.line_ids:
                raise ValidationError(_("Cannot send a quotation without any product lines."))
            sub._validate_expiration_date()
            sub._validate_quotation_integrity()
            sub.state = 'quotation'
            sub.message_post(body=_("Quotation marked as sent to customer %s.") % sub.partner_id.name)
        return True

    def action_confirm(self):
        """Confirm customer quotation and prepare for subscription activation."""
        for sub in self:
            if sub.state not in ('draft', 'quotation'):
                raise ValidationError(_("Only draft or sent quotations can be confirmed."))
            if not sub.line_ids:
                raise ValidationError(_("Cannot confirm a quotation without product lines."))

            sub._validate_expiration_date()
            sub._validate_quotation_integrity()

            # Increment discount rule usage if applicable
            if sub.discount_id and sub.discount_id.max_usage > 0:
                sub.discount_id.usage_count += 1

            sub.state = 'confirmed'
            if not sub.next_billing_date:
                sub.next_billing_date = sub.date_start or fields.Date.context_today(sub)

            sub.message_post(body=_("Quotation confirmed successfully with total %s.") % sub.amount_total)
        return True

    def action_activate(self):
        """Activate a confirmed quotation into an active subscription."""
        for sub in self:
            if sub.state != 'confirmed':
                raise ValidationError(_("Only confirmed quotations can be activated into active subscriptions."))
            sub.state = 'active'
            sub.message_post(body=_("Subscription activated."))
        return True

    def action_cancel(self):
        """Cancel an eligible draft or sent quotation."""
        for sub in self:
            if sub.state not in ('draft', 'quotation', 'confirmed'):
                raise ValidationError(_("Only draft, sent, or confirmed quotations can be cancelled."))
            sub.state = 'cancelled'
            sub.message_post(body=_("Quotation has been cancelled."))
        return True

    def action_reset_to_draft(self):
        """Reset cancelled or sent quotation back to draft."""
        for sub in self:
            if sub.state not in ('quotation', 'cancelled'):
                raise ValidationError(_("Only sent or cancelled quotations can be reset to draft."))
            sub.state = 'draft'
            sub.message_post(body=_("Quotation reset to draft state."))
        return True

    def _validate_expiration_date(self):
        """Reject confirmation or sending of expired quotations."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        if self.date_expiration and self.date_expiration < today:
            raise ValidationError(
                _("This quotation expired on %s and cannot be processed (today is %s).")
                % (self.date_expiration, today)
            )


class SubscriptionSubscriptionLine(models.Model):
    """Product and variant lines within a subscription quotation."""
    _name = 'subscription.subscription.line'
    _description = 'Subscription Quotation Line'
    _order = 'id asc'

    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Quotation / Subscription',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product Variant',
        required=True,
        domain="[('is_subscription_product', '=', True)]",
        help='Select subscription product or variant.'
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        readonly=True,
    )
    variant_description = fields.Char(
        string='Variant Attributes',
        compute='_compute_variant_details',
        help='Display variant attributes and extra pricing.'
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
        help='Subscribed quantity (must be strictly positive).'
    )
    price_base = fields.Monetary(
        string='Base Price',
        compute='_compute_variant_details',
        currency_field='currency_id',
        help='Base product template list price.'
    )
    price_extra = fields.Monetary(
        string='Variant Extra',
        compute='_compute_variant_details',
        currency_field='currency_id',
        help='Additional price specific to the selected product variant.'
    )
    price_unit = fields.Monetary(
        string='Unit Price',
        required=True,
        currency_field='currency_id',
        help='Final unit price (Base price + Variant extra price, without double counting).'
    )
    discount = fields.Float(
        string='Discount (%)',
        digits='Discount',
        default=0.0,
        help='Discount percentage applied to this line (0 - 100).'
    )
    tax_ids = fields.Many2many(
        'account.tax',
        'subscription_billing_line_tax_rel',
        'line_id',
        'tax_id',
        string='Taxes',
        domain="[('type_tax_use', '=', 'sale')]",
        help='Taxes applicable to this product line.'
    )
    currency_id = fields.Many2one(
        related='subscription_id.currency_id',
        string='Currency',
        readonly=True,
    )
    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_line_totals',
        store=True,
        currency_field='currency_id',
        help='Untaxed line subtotal after applying line discount.'
    )
    price_tax = fields.Monetary(
        string='Tax Amount',
        compute='_compute_line_totals',
        store=True,
        currency_field='currency_id',
        help='Calculated tax for this line.'
    )
    price_total = fields.Monetary(
        string='Total',
        compute='_compute_line_totals',
        store=True,
        currency_field='currency_id',
        help='Total line amount including taxes.'
    )

    _sql_constraints = [
        ('quantity_positive', 'check(quantity > 0)', 'Product quantity must be strictly positive (greater than 0)!'),
        ('discount_valid', 'check(discount >= 0 and discount <= 100)', 'Discount percentage must be between 0 and 100!'),
    ]

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Product quantity must be strictly positive (greater than 0)."))

    @api.constrains('discount')
    def _check_discount(self):
        for line in self:
            if not (0.0 <= line.discount <= 100.0):
                raise ValidationError(_("Line discount must be between 0% and 100%."))

    @api.depends('product_id')
    def _compute_variant_details(self):
        for line in self:
            prod = line.product_id
            if prod:
                base = getattr(prod.product_tmpl_id, 'list_price', 0.0) or 0.0
                extra = getattr(prod, 'price_extra', 0.0) or 0.0
                line.price_base = base
                line.price_extra = extra
                # Attribute descriptions
                attrs = []
                if hasattr(prod, 'product_template_attribute_value_ids') and prod.product_template_attribute_value_ids:
                    attrs = [ptav.name for ptav in prod.product_template_attribute_value_ids]
                line.variant_description = ", ".join(attrs) if attrs else _("Standard")
            else:
                line.price_base = 0.0
                line.price_extra = 0.0
                line.variant_description = ""

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Fetch base price and variant extra accurately without duplicate addition."""
        if self.product_id:
            prod = self.product_id
            base_price = getattr(prod.product_tmpl_id, 'list_price', 0.0) or 0.0
            price_extra = getattr(prod, 'price_extra', 0.0) or 0.0
            # Standard Odoo lst_price is base_price + price_extra.
            # To ensure additional variant price is not added twice:
            if hasattr(prod, 'lst_price') and prod.lst_price != base_price:
                self.price_unit = prod.lst_price
            elif price_extra:
                self.price_unit = base_price + price_extra
            else:
                self.price_unit = getattr(prod, 'lst_price', base_price)

            # Assign default sales taxes from product
            if prod.taxes_id:
                self.tax_ids = prod.taxes_id

    @api.depends('quantity', 'price_unit', 'discount', 'tax_ids', 'currency_id')
    def _compute_line_totals(self):
        """Calculate line subtotal, tax amount, and total with native Odoo tax rules."""
        for line in self:
            currency = line.currency_id or line.subscription_id.company_id.currency_id
            discount_factor = 1.0 - (line.discount or 0.0) / 100.0
            subtotal = line.quantity * line.price_unit * discount_factor

            # Calculate taxes using native Odoo tax engine
            tax_amount = 0.0
            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line.price_unit * discount_factor,
                    currency=currency,
                    quantity=line.quantity,
                    product=line.product_id,
                    partner=line.subscription_id.partner_id
                )
                subtotal = taxes_res.get('total_excluded', subtotal)
                tax_amount = sum(t.get('amount', 0.0) for t in taxes_res.get('taxes', []))

            line.price_subtotal = currency.round(subtotal) if currency else subtotal
            line.price_tax = currency.round(tax_amount) if currency else tax_amount
            line.price_total = currency.round(subtotal + tax_amount) if currency else (subtotal + tax_amount)
