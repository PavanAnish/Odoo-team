# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SubscriptionTemplateWizard(models.TransientModel):
    """Transient wizard example demonstrating interactive modal workflows."""
    _name = 'subscription.template.wizard'
    _description = 'Subscription Template Transient Wizard'

    reason = fields.Char(
        string='Update Reason',
        required=True,
        help='Reason for batch state transition or update.'
    )
    item_ids = fields.Many2many(
        'subscription.template.item',
        string='Template Items',
        default=lambda self: self.env.context.get('active_ids', [])
    )

    def action_apply(self):
        """Perform batch operations on target records."""
        self.ensure_one()
        if not self.item_ids:
            raise UserError(_("No items selected for this operation."))
        for item in self.item_ids:
            item.message_post(body=_("Batch action triggered with reason: %s") % self.reason)
        return {'type': 'ir.actions.act_window_close'}
