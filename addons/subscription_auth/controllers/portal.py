# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request


class SubscriptionCustomerPortal(CustomerPortal):
    """Extends customer portal controller to provide subscription counters and views."""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'subscription_count' in counters:
            values['subscription_count'] = 0
        return values
