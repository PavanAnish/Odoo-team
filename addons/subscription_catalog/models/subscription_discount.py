# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SubscriptionDiscount(models.Model):
    """Discount rules for Subscription Management System."""
    _name = 'subscription.discount'
    _description = 'Subscription Discount Rule'
    _inherit = ['subscription.audit.mixin', 'mail.thread']
    _order = 'name asc'

    name = fields.Char(
        string='Discount Name',
        required=True,
        tracking=True,
        help='Descriptive name for the discount rule (e.g., Early Bird 10%, Annual Promo).'
    )
    code = fields.Char(
        string='Coupon / Discount Code',
        required=True,
        copy=False,
        tracking=True,
        help='Unique code used to apply this discount.'
    )
    discount_type = fields.Selection(
        selection=[
            ('percent', 'Percentage (%)'),
            ('fixed', 'Fixed Amount'),
        ],
        string='Discount Type',
        required=True,
        default='percent',
        tracking=True,
    )
    discount_value = fields.Float(
        string='Discount Value',
        required=True,
        default=0.0,
        tracking=True,
        help='Percentage rate (0-100) or fixed amount to deduct.'
    )
    date_start = fields.Date(
        string='Start Date',
        help='Date when this discount becomes eligible.'
    )
    date_end = fields.Date(
        string='Expiry Date',
        help='Date after which this discount expires.'
    )
    min_amount = fields.Monetary(
        string='Minimum Order Amount',
        default=0.0,
        help='Minimum quotation untaxed subtotal required to qualify for this discount.'
    )
    max_usage = fields.Integer(
        string='Maximum Usage Limit',
        default=0,
        help='Maximum number of times this discount can be applied across quotations (0 = unlimited).'
    )
    usage_count = fields.Integer(
        string='Times Used',
        default=0,
        readonly=True,
        help='Number of confirmed quotations using this discount rule.'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to disable this discount rule.'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code, company_id)', 'The discount code must be unique per company!'),
        ('value_positive', 'check(discount_value >= 0)', 'Discount value must be non-negative!'),
    ]

    @api.constrains('discount_type', 'discount_value')
    def _check_discount_value(self):
        for rec in self:
            if rec.discount_type == 'percent' and not (0.0 <= rec.discount_value <= 100.0):
                raise ValidationError(_("Percentage discount must be between 0 and 100."))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Discount expiry date cannot be earlier than its start date."))

    def validate_eligibility(self, quotation_amount=0.0, target_date=None):
        """Validate if this discount rule is eligible for a given quotation."""
        self.ensure_one()
        if not self.active:
            raise ValidationError(_("The discount rule '%s' is inactive.") % self.name)

        check_date = target_date or fields.Date.context_today(self)
        if self.date_start and check_date < self.date_start:
            raise ValidationError(
                _("The discount rule '%s' is only valid from %s.") % (self.name, self.date_start)
            )
        if self.date_end and check_date > self.date_end:
            raise ValidationError(
                _("The discount rule '%s' expired on %s.") % (self.name, self.date_end)
            )
        if self.max_usage > 0 and self.usage_count >= self.max_usage:
            raise ValidationError(
                _("The discount rule '%s' has reached its maximum usage limit (%s).")
                % (self.name, self.max_usage)
            )
        if self.min_amount > 0 and quotation_amount < self.min_amount:
            raise ValidationError(
                _("Quotation subtotal (%s) is below the minimum required amount (%s) for discount '%s'.")
                % (quotation_amount, self.min_amount, self.name)
            )
        return True

    def calculate_discount_amount(self, subtotal):
        """Calculate the discount amount for a given untaxed subtotal."""
        self.ensure_one()
        if subtotal <= 0:
            return 0.0
        if self.discount_type == 'percent':
            return (subtotal * self.discount_value) / 100.0
        elif self.discount_type == 'fixed':
            return min(self.discount_value, subtotal)
        return 0.0
