# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError


class SubscriptionStatusHistory(models.Model):
    """Immutable audit trail for subscription lifecycle status transitions."""
    _name = 'subscription.status.history'
    _description = 'Subscription Status History'
    _order = 'change_date desc, id desc'
    _rec_name = 'new_state'

    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Subscription',
        required=True,
        ondelete='cascade',
        index=True,
        readonly=True,
        help='Subscription record this status change belongs to.'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='subscription_id.company_id',
        store=True,
        readonly=True,
    )
    previous_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('quotation', 'Quotation'),
            ('confirmed', 'Confirmed'),
            ('active', 'Active'),
            ('closed', 'Closed'),
        ],
        string='Previous Status',
        readonly=True,
        help='State before this transition took place.'
    )
    new_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('quotation', 'Quotation'),
            ('confirmed', 'Confirmed'),
            ('active', 'Active'),
            ('closed', 'Closed'),
        ],
        string='New Status',
        required=True,
        readonly=True,
        help='State after this transition was completed.'
    )
    user_id = fields.Many2one(
        'res.users',
        string='Changed By',
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
        help='User who initiated or authorized this status transition.'
    )
    change_date = fields.Datetime(
        string='Change Date & Time',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        help='Exact timestamp when the status change was recorded.'
    )
    reason = fields.Text(
        string='Reason / Description',
        readonly=True,
        help='Operational context, reason or notes associated with this transition.'
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Allow creation only by authorized internal staff or system operations."""
        if not (self.env.user.has_group('subscription_base.group_subscription_user') or self.env.is_system() or self.env.su):
            raise AccessError(_("Access Denied: Only authorized staff can create status history records."))
        return super().create(vals_list)

    def write(self, vals):
        """Prevent modification of historical audit records."""
        raise UserError(_("Subscription status history entries are permanent audit records and cannot be modified."))

    def unlink(self):
        """Prevent deletion of historical audit records by ordinary users."""
        if not (self.env.user.has_group('base.group_system') or self.env.is_system()):
            raise UserError(_("Subscription status history entries are permanent audit records and cannot be deleted."))
        return super().unlink()
