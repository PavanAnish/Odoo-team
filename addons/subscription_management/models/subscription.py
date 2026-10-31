# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

import logging
from datetime import timedelta
from dateutil.relativedelta import relativedelta
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
            ('quotation', 'Quotation'),
            ('confirmed', 'Confirmed'),
            ('active', 'Active'),
            ('closed', 'Closed'),
        ],
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        copy=False,
    )
    history_ids = fields.One2many(
        'subscription.status.history',
        'subscription_id',
        string='Status History',
        readonly=True,
        help='Permanent audit trail of all status transitions for this subscription.'
    )

    # Strict business lifecycle transitions: Draft -> Quotation -> Confirmed -> Active -> Closed
    VALID_STATE_TRANSITIONS = {
        'draft': ['quotation'],
        'quotation': ['confirmed'],
        'confirmed': ['active'],
        'active': ['closed'],
        'closed': [],
    }

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
    validity_days = fields.Integer(
        string='Validity Duration (Days)',
        default=lambda self: int(self.env['ir.config_parameter'].sudo().get_param(
            'subscription_base.default_validity_days', default='30'
        )),
        tracking=True,
        help='Number of days this quotation remains valid after its creation date. '
             'Changing this value will automatically recalculate the expiry date.'
    )
    expiration_status = fields.Selection(
        selection=[
            ('valid', 'Valid'),
            ('expiring_soon', 'Expiring Soon'),
            ('expired', 'Expired'),
        ],
        string='Expiration Status',
        compute='_compute_expiration_status',
        store=True,
        tracking=True,
        help='Current validity status: Valid (plenty of time), Expiring Soon (≤7 days), Expired (past expiry date).'
    )
    is_expired = fields.Boolean(
        string='Is Expired',
        compute='_compute_expiration_status',
        store=True,
        help='True when the quotation expiry date has passed and the quotation has not yet been confirmed.'
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
    date_subscription_end = fields.Date(
        string='Subscription Expiry Date',
        tracking=True,
        help='Calculated expiry date of the subscription, computed based on subscription start date and plan billing duration.'
    )

    # --- Subscription & Quotation Identification ---
    subscription_ref = fields.Char(
        string='Subscription Number',
        copy=False,
        readonly=True,
        index=True,
        tracking=True,
        help='Unique subscription reference generated when quotation is converted to active subscription (e.g. SUB/2026/00001).'
    )
    quotation_id = fields.Many2one(
        'subscription.subscription',
        string='Original Quotation',
        readonly=True,
        copy=False,
        index=True,
        help='Reference to the original quotation that generated this subscription.'
    )
    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Generated Subscription',
        readonly=True,
        copy=False,
        index=True,
        help='Reference to the active subscription generated from this quotation.'
    )
    is_converted = fields.Boolean(
        string='Converted to Subscription',
        default=False,
        copy=False,
        readonly=True,
        tracking=True,
        help='True once this confirmed quotation has been converted to a subscription. Prevents duplicate conversions.'
    )

    # --- Payment Terms ---
    payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Payment Terms',
        tracking=True,
        help='Payment terms associated with this quotation and subscription for billing and invoice due date calculation.'
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
        if not (self.env.user.has_group('subscription_base.group_subscription_user') or self.env.is_system() or self.env.su):
            raise AccessError(_("Access Denied: Only authorized internal staff can create subscription quotations."))
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                if vals.get('subscription_ref'):
                    vals['name'] = vals['subscription_ref']
                elif vals.get('quotation_id') or vals.get('state') == 'active':
                    vals['name'] = self.env['ir.sequence'].next_by_code('subscription.subscription.active') or _('SUB/%s/00001') % fields.Date.context_today(self).year
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code('subscription.subscription') or _('QT/%s/00001') % fields.Date.context_today(self).year
            if vals.get('name') and str(vals['name']).startswith('SUB/') and not vals.get('subscription_ref'):
                vals['subscription_ref'] = vals['name']
        records = super().create(vals_list)
        for rec in records:
            rec._check_duplicate_reference()
            rec._validate_quotation_integrity()
            # Record initial state audit history
            self.env['subscription.status.history'].sudo().create({
                'subscription_id': rec.id,
                'previous_state': False,
                'new_state': rec.state or 'draft',
                'user_id': self.env.uid,
                'change_date': fields.Datetime.now(),
                'reason': _("Initial record creation in status '%s'") % (rec.state or 'draft').capitalize(),
            })
        return records

    def write(self, vals):
        if not (self.env.user.has_group('subscription_base.group_subscription_user') or self.env.is_system() or self.env.su):
            raise AccessError(_("Access Denied: Only authorized internal staff can edit subscription quotations."))

        # Prevent editing locked / closed records unless updating notes
        for rec in self:
            if rec.state == 'closed' and not any(k in vals for k in ('state', 'notes')):
                raise UserError(_("Cannot modify a closed subscription record."))

        state_transitions = []
        if 'state' in vals:
            self._check_transition_permission()
            new_state = vals['state']
            for rec in self:
                old_state = rec.state
                if old_state != new_state:
                    rec._validate_state_transition(old_state, new_state)
                    state_transitions.append((rec, old_state, new_state))

        res = super().write(vals)

        # Record audit history for each successful transition in the same transaction
        for rec, old_state, new_state in state_transitions:
            self.env['subscription.status.history'].sudo().create({
                'subscription_id': rec.id,
                'previous_state': old_state,
                'new_state': new_state,
                'user_id': self.env.uid,
                'change_date': fields.Datetime.now(),
                'reason': self.env.context.get('transition_reason') or _("Status transitioned from '%s' to '%s'") % (
                    dict(self._fields['state'].selection).get(old_state, old_state),
                    dict(self._fields['state'].selection).get(new_state, new_state),
                ),
            })

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

    @api.constrains('subscription_ref')
    def _check_subscription_ref_unique(self):
        """Enforce uniqueness of subscription_ref per company at the ORM level."""
        for sub in self:
            if sub.subscription_ref:
                domain = [
                    ('subscription_ref', '=', sub.subscription_ref),
                    ('id', '!=', sub.id),
                    ('company_id', '=', sub.company_id.id),
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(_(
                        "Subscription number '%s' already exists for this company."
                    ) % sub.subscription_ref)

    @api.constrains('quotation_id')
    def _check_unique_quotation_conversion(self):
        """Ensure a single quotation cannot be linked to multiple subscriptions."""
        for sub in self:
            if sub.quotation_id:
                domain = [
                    ('quotation_id', '=', sub.quotation_id.id),
                    ('id', '!=', sub.id),
                    ('company_id', '=', sub.company_id.id),
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(_(
                        "Quotation '%s' has already been converted to another subscription."
                    ) % sub.quotation_id.name)

    def _validate_state_transition(self, old_state, new_state):
        """Validate whether the transition from old_state to new_state is allowed by business rules."""
        self.ensure_one()
        if old_state == new_state:
            return True

        allowed = self.VALID_STATE_TRANSITIONS.get(old_state, [])
        if new_state not in allowed:
            old_label = dict(self._fields['state'].selection).get(old_state, old_state)
            new_label = dict(self._fields['state'].selection).get(new_state, new_state)
            allowed_labels = [dict(self._fields['state'].selection).get(s, s) for s in allowed]
            allowed_str = ', '.join(allowed_labels) if allowed_labels else _('None (Closed is terminal)')
            raise ValidationError(_(
                "Invalid status transition: Cannot transition subscription '%s' from '%s' to '%s'. "
                "Allowed next status: %s."
            ) % (self.name, old_label, new_label, allowed_str))
        return True

    def _check_transition_permission(self):
        """Verify that the user is authorized to perform status changes."""
        if self.env.is_system() or self.env.su:
            return True
        if not self.env.user.has_group('subscription_base.group_subscription_user'):
            raise AccessError(_("Access Denied: Only authorized internal staff can modify subscription statuses."))
        return True

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


    # --- Expiration Status Computation ---

    @api.depends('date_expiration', 'state')
    def _compute_expiration_status(self):
        """Compute expiration_status and is_expired based on current date vs expiry date.

        Business rules:
        - Quotations already confirmed or beyond (active, paused, closed) are never 'expired'.
        - 'expiring_soon' threshold is 7 days before expiry.
        - 'expired' means date_expiration < today for draft/quotation state records.
        """
        _EXPIRING_SOON_DAYS = 7
        today = fields.Date.today()
        expiring_threshold = today + timedelta(days=_EXPIRING_SOON_DAYS)

        for sub in self:
            # Confirmed/active subscriptions are not subject to expiration logic
            if sub.state in ('confirmed', 'active', 'paused', 'closed'):
                sub.expiration_status = 'valid'
                sub.is_expired = False
            elif not sub.date_expiration:
                sub.expiration_status = 'valid'
                sub.is_expired = False
            elif sub.date_expiration < today:
                sub.expiration_status = 'expired'
                sub.is_expired = True
            elif sub.date_expiration <= expiring_threshold:
                sub.expiration_status = 'expiring_soon'
                sub.is_expired = False
            else:
                sub.expiration_status = 'valid'
                sub.is_expired = False

    @api.onchange('date_quotation', 'validity_days')
    def _onchange_validity_days(self):
        """Auto-calculate expiry date when quotation date or validity duration changes."""
        if self.date_quotation and self.validity_days and self.validity_days > 0:
            self.date_expiration = self.date_quotation + timedelta(days=self.validity_days)

    @api.constrains('validity_days')
    def _check_validity_days(self):
        """Ensure validity duration is a non-negative integer."""
        for sub in self:
            if sub.validity_days < 0:
                raise ValidationError(_(
                    "Validity duration cannot be negative. "
                    "Please enter zero or a positive number of days."
                ))

    # --- Scheduled Action for Expiration Refresh ---

    @api.model
    def _cron_refresh_expiration_status(self):
        """Scheduled action: recompute expiration_status for all open quotations.

        Triggered daily by ir.cron. Only processes draft and quotation-sent records
        to avoid touching confirmed/active subscriptions.
        """
        open_quotations = self.search([('state', 'in', ('draft', 'quotation'))])
        if open_quotations:
            open_quotations._compute_expiration_status()
            _logger.info(
                "Subscription cron: refreshed expiration_status for %d quotation(s).",
                len(open_quotations)
            )
        else:
            _logger.debug("Subscription cron: no open quotations to refresh.")

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
        """Activate a confirmed quotation or subscription into active status.
        Kept for backward compatibility with existing tests and workflows."""
        for sub in self:
            if sub.state != 'confirmed':
                raise ValidationError(_("Only confirmed quotations can be activated into active subscriptions."))
            if not sub.subscription_ref:
                sub_number = self.env['ir.sequence'].next_by_code('subscription.subscription.active')
                if not sub_number or sub_number in ('/', _('New'), 'False'):
                    year_str = str(fields.Date.context_today(self).year)
                    sub_number = f"SUB/{year_str}/{sub.id or 1:05d}"
                sub.subscription_ref = sub_number
            if not sub.date_subscription_end:
                sub.date_subscription_end = sub._compute_subscription_end_date()
            sub.state = 'active'
            sub.message_post(body=_("Subscription activated with reference %s.") % sub.subscription_ref)
        return True

    def action_create_subscription(self):
        """Convert confirmed quotation(s) into active subscription record(s).

        Business Rules:
        - Must be in 'confirmed' state.
        - Must not be expired (validated via _validate_expiration_date()).
        - Must not already be converted (idempotency / duplicate prevention).
        - Must contain at least one product line.
        - Generates unique subscription number via ir.sequence (SUB/%(year)s/NNNNN).
        - Atomically creates subscription record and copies product lines, pricing, discounts, taxes.
        - Computes subscription expiry date based on plan interval and calendar-aware relativedelta.
        - Marks original quotation as converted and links both records bidirectionally.
        """
        if not self.env.user.has_group('subscription_base.group_subscription_user'):
            raise AccessError(_("Access Denied: Only authorized internal staff can create subscriptions."))

        created_subs = self.env['subscription.subscription']
        for quotation in self:
            created_sub = quotation._action_create_subscription_single()
            created_subs |= created_sub

        if len(self) == 1 and self.env.context.get('open_subscription_form'):
            return {
                'type': 'ir.actions.act_window',
                'name': _('Subscription'),
                'res_model': 'subscription.subscription',
                'res_id': created_subs.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return created_subs if len(self) == 1 else True

    def _action_create_subscription_single(self):
        """Internal worker converting a single confirmed quotation into an active subscription."""
        self.ensure_one()

        # 1. State validation: only confirmed quotations can be converted
        if self.state != 'confirmed':
            raise ValidationError(_(
                "Only confirmed quotations can be converted into subscriptions. "
                "Current quotation '%s' is in '%s' status."
            ) % (self.name, self.state))

        # 2. Duplicate conversion validation
        if self.is_converted or self.subscription_id:
            sub_ref = self.subscription_id.name or self.subscription_ref or _('N/A')
            raise UserError(_(
                "Quotation '%s' has already been converted to subscription '%s'. "
                "Duplicate subscription creation is not allowed."
            ) % (self.name, sub_ref))

        # 3. Expiration validation (cannot convert expired quotation)
        self._validate_expiration_date()

        # 4. Product lines validation
        if not self.line_ids:
            raise ValidationError(_(
                "Cannot create a subscription from quotation '%s' without any product lines."
            ) % self.name)

        # 5. Customer & Plan availability validation
        if not self.partner_id or (hasattr(self.partner_id, 'active') and not self.partner_id.active):
            raise ValidationError(_("Customer is missing or inactive for quotation '%s'.") % self.name)

        if not self.plan_id or (hasattr(self.plan_id, 'active') and not self.plan_id.active):
            raise ValidationError(_("Subscription plan is missing or inactive for quotation '%s'.") % self.name)

        avail, reason = self.plan_id.is_available(target_date=self.date_start or fields.Date.context_today(self))
        if not avail:
            raise ValidationError(_("Subscription plan '%s' is not available: %s") % (self.plan_id.name, reason))

        # 6. Generate unique subscription reference number
        seq_code = 'subscription.subscription.active'
        sub_number = self.env['ir.sequence'].next_by_code(seq_code)
        if not sub_number or sub_number in ('/', _('New'), 'False'):
            year_str = str(fields.Date.context_today(self).year)
            sub_count = self.search_count([('name', 'like', 'SUB/%')]) + 1
            sub_number = f"SUB/{year_str}/{sub_count:05d}"

        # 7. Compute subscription dates
        sub_start_date = self.date_start or fields.Date.context_today(self)
        sub_end_date = self._compute_subscription_end_date(start_date=sub_start_date)

        # 8. Payment terms
        payment_term = self.payment_term_id
        if not payment_term and hasattr(self.partner_id, 'property_payment_term_id') and self.partner_id.property_payment_term_id:
            payment_term = self.partner_id.property_payment_term_id

        # 9. Prepare subscription line values
        sub_line_vals = []
        for line in self.line_ids:
            sub_line_vals.append((0, 0, {
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
            }))

        sub_vals = {
            'name': sub_number,
            'subscription_ref': sub_number,
            'quotation_id': self.id,
            'partner_id': self.partner_id.id,
            'plan_id': self.plan_id.id,
            'state': 'active',
            'payment_term_id': payment_term.id if payment_term else False,
            'date_quotation': self.date_quotation,
            'date_start': sub_start_date,
            'date_subscription_end': sub_end_date,
            'date_end': self.date_end or sub_end_date,
            'next_billing_date': sub_start_date,
            'discount_id': self.discount_id.id if self.discount_id else False,
            'company_id': self.company_id.id,
            'notes': self.notes,
            'line_ids': sub_line_vals,
        }

        # 10. Atomic creation with database savepoint
        with self.env.cr.savepoint():
            new_sub = self.env['subscription.subscription'].create(sub_vals)
            self.write({
                'is_converted': True,
                'subscription_id': new_sub.id,
                'subscription_ref': sub_number,
            })

            # Chatter audit trail
            if hasattr(self, 'message_post'):
                self.message_post(body=_(
                    "Quotation successfully converted to subscription <b>%s</b>."
                ) % sub_number)
            if hasattr(new_sub, 'message_post'):
                new_sub.message_post(body=_(
                    "Subscription created from quotation <b>%s</b>. Plan: %s | Start: %s | Expiry: %s."
                ) % (self.name, self.plan_id.name, sub_start_date, sub_end_date or _('Ongoing')))

        return new_sub

    def _compute_subscription_end_date(self, start_date=None):
        """Calculate subscription expiry date from start date and plan billing interval/period.

        Uses calendar-aware dateutil.relativedelta for monthly/yearly to accurately
        handle month-end dates and leap years. Respects date_end if already configured.
        """
        self.ensure_one()
        if self.date_end:
            return self.date_end
        if not self.plan_id:
            return False

        start = start_date or self.date_start or fields.Date.context_today(self)
        interval = self.plan_id.billing_interval or 1
        period = self.plan_id.billing_period or 'monthly'

        if period == 'daily':
            return start + timedelta(days=interval)
        elif period == 'weekly':
            return start + timedelta(weeks=interval)
        elif period == 'monthly':
            return start + relativedelta(months=interval)
        elif period == 'yearly':
            return start + relativedelta(years=interval)
        return start + relativedelta(months=1)

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
