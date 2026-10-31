# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import http
from odoo.http import request


class SubscriptionTemplateController(http.Controller):
    """Example HTTP controller demonstrating public / internal JSON and web routes."""

    @http.route('/subscription/template/health', type='json', auth='public', methods=['POST'])
    def health_check(self):
        """Simple health check endpoint returning system status."""
        return {
            'status': 'ok',
            'module': 'subscription_module_template',
            'installed': True,
        }

    @http.route('/subscription/template/items', type='json', auth='user', methods=['POST'])
    def get_template_items(self):
        """Retrieve confirmed template items for authenticated users."""
        items = request.env['subscription.template.item'].search_read(
            [('state', '=', 'confirmed')],
            ['id', 'name', 'code', 'create_date']
        )
        return {
            'count': len(items),
            'items': items,
        }
