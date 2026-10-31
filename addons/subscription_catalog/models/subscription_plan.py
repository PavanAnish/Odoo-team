# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SubscriptionPlan(models.Model):
    """Defines recurring subscription plans and billing schedules."""
    _name = 'subscription.plan'
    _description = 'Subscription Plan'
    _inherit = ['subscription.audit.mixin', 'mail.thread']
    _order = 'name asc'

    name = fields.Char(
        string='Plan Name',
        required=True,
        tracking=True,
        help='Display name of the subscription plan (e.g., Monthly Pro, Annual Enterprise).'
    )
    code = fields.Char(
        string='Plan Code',
        required=True,
        copy=False,
        help='Unique internal reference identifier for the plan.'
    )
    billing_interval = fields.Integer(
        string='Billing Interval',
        required=True,
        default=1,
        help='Number of billing units per recurring cycle (e.g., 1 month, 3 months).'
    )
    billing_period = fields.Selection(
        selection=[
            ('daily', 'Days'),
            ('weekly', 'Weeks'),
            ('monthly', 'Months'),
            ('yearly', 'Years'),
        ],
        string='Billing Period',
        required=True,
        default='monthly',
        help='Recurring frequency unit.'
    )
    trial_period_days = fields.Integer(
        string='Trial Period (Days)',
        default=0,
        help='Number of free trial days before the first invoice cycle begins.'
    )
    date_start = fields.Date(
        string='Start Date',
        help='Date when this plan becomes available for quotations.'
    )
    date_end = fields.Date(
        string='End Date',
        help='Expiration date after which this plan is no longer available for new quotations.'
    )
    min_quantity = fields.Float(
        string='Minimum Quantity',
        default=1.0,
        help='Minimum product quantity required to subscribe to this plan.'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to deactivate the plan for new subscriptions.'
    )

    # --- Renewal Settings ---
    allow_renewal = fields.Boolean(
        string='Allow Renewal',
        default=True,
        help='Whether subscriptions on this plan can be renewed.',
    )
    auto_renewal = fields.Boolean(
        string='Automatic Renewal',
        default=False,
        help='If enabled, eligible subscriptions are renewed automatically by a scheduled job.',
    )

    # --- Pause & Early Closure Settings ---
    allow_pause = fields.Boolean(
        string='Allow Pause',
        default=True,
        help='Whether subscriptions on this plan can be paused temporarily.',
    )
    allow_early_closure = fields.Boolean(
        string='Allow Early Closure',
        default=True,
        help='Whether subscriptions can be closed before their scheduled end date.',
    )
    pause_billing_policy = fields.Selection(
        selection=[
            ('shift', 'Shift Next Billing Date by Pause Duration'),
            ('no_change', 'Keep Original Billing Schedule'),
        ],
        string='Pause Billing Policy',
        default='shift',
        required=True,
        help='Determines how next_billing_date is adjusted when a subscription is resumed.',
    )

    _sql_constraints = [
        ('code_unique', 'unique(code, company_id)', 'The plan code must be unique per company!')
    ]

    @api.constrains('date_start', 'date_end')
    def _check_plan_dates(self):
        for plan in self:
            if plan.date_start and plan.date_end and plan.date_end < plan.date_start:
                raise ValidationError(_("Plan end date cannot be earlier than its start date."))

    @api.constrains('min_quantity')
    def _check_min_quantity(self):
        for plan in self:
            if plan.min_quantity < 0:
                raise ValidationError(_("Minimum quantity cannot be negative."))

    def is_available(self, target_date=None, quantity=None):
        """Check whether this plan is active, valid for the target date, and meets min quantity."""
        self.ensure_one()
        if not self.active:
            return False, _("The plan '%s' is inactive.") % self.name
        check_date = target_date or fields.Date.context_today(self)
        if self.date_start and check_date < self.date_start:
            return False, _("The plan '%s' is not active until %s.") % (self.name, self.date_start)
        if self.date_end and check_date > self.date_end:
            return False, _("The plan '%s' expired on %s.") % (self.name, self.date_end)
        if quantity is not None and self.min_quantity and quantity < self.min_quantity:
            return False, _("The plan '%s' requires a minimum quantity of %s.") % (self.name, self.min_quantity)
        return True, ""
