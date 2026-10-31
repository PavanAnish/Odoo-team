# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError


class SubscriptionRenewalHistory(models.Model):
    """Immutable audit trail for subscription renewal operations."""
    _name = 'subscription.renewal.history'
    _description = 'Subscription Renewal History'
    _order = 'renewal_date desc, id desc'
    _rec_name = 'subscription_id'

    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Subscription',
        required=True,
        ondelete='cascade',
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='subscription_id.company_id',
        store=True,
        readonly=True,
    )
    plan_id = fields.Many2one(
        'subscription.plan',
        string='Plan',
        readonly=True,
    )
    renewal_type = fields.Selection(
        selection=[('manual', 'Manual'), ('automatic', 'Automatic')],
        string='Renewal Type',
        required=True,
        readonly=True,
    )
    renewal_result = fields.Selection(
        selection=[('success', 'Success'), ('failed', 'Failed')],
        string='Result',
        required=True,
        readonly=True,
        default='success',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Renewed By',
        readonly=True,
    )
    renewal_date = fields.Datetime(
        string='Renewal Date',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    prev_subscription_end = fields.Date(string='Previous Expiry Date', readonly=True)
    new_subscription_end = fields.Date(string='New Expiry Date', readonly=True)
    prev_next_billing_date = fields.Date(string='Previous Billing Date', readonly=True)
    new_next_billing_date = fields.Date(string='New Billing Date', readonly=True)
    notes = fields.Text(string='Notes', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.user.has_group('subscription_base.group_subscription_user')
                or self.env.is_system() or self.env.su):
            raise AccessError(_("Only authorized staff can create renewal history records."))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_("Renewal history entries are permanent records and cannot be modified."))

    def unlink(self):
        if not (self.env.user.has_group('base.group_system') or self.env.is_system()):
            raise UserError(_("Renewal history entries cannot be deleted."))
        return super().unlink()
