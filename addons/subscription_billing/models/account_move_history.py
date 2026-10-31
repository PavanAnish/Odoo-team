# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _


class AccountMoveHistory(models.Model):
    """Immutable audit trail of all lifecycle events and actions on invoices."""
    _name = 'account.move.history'
    _description = 'Invoice Lifecycle & Status History'
    _order = 'timestamp desc, id desc'

    move_id = fields.Many2one(
        'account.move',
        string='Invoice',
        required=True,
        ondelete='cascade',
        index=True,
        readonly=True,
        help='The invoice this history entry belongs to.'
    )
    timestamp = fields.Datetime(
        string='Timestamp',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
        index=True,
        help='Timestamp when the action was performed.'
    )
    user_id = fields.Many2one(
        'res.users',
        string='Actor',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        help='User who initiated or performed the action.'
    )
    user_name = fields.Char(
        string='Actor Name',
        readonly=True,
        help='Snapshot of the actor name at event time.'
    )
    action = fields.Selection(
        selection=[
            ('create', 'Created'),
            ('confirm', 'Confirmed'),
            ('register_payment', 'Payment Recorded'),
            ('cancel', 'Cancelled'),
            ('send', 'Sent'),
            ('print', 'Printed'),
            ('download', 'Downloaded'),
            ('modify', 'Modified'),
        ],
        string='Action',
        required=True,
        readonly=True,
        help='Lifecycle action performed.'
    )
    previous_status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('paid', 'Paid'),
            ('cancel', 'Cancelled'),
        ],
        string='Previous Status',
        readonly=True,
        help='Status before this action.'
    )
    current_status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('paid', 'Paid'),
            ('cancel', 'Cancelled'),
        ],
        string='Current Status',
        required=True,
        readonly=True,
        help='Status resulting from this action.'
    )
    details = fields.Text(
        string='Details',
        readonly=True,
        help='Additional context, payment reference, recipient email, or reason.'
    )

