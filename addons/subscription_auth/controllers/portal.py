# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request, route


class SubscriptionCustomerPortal(CustomerPortal):
    """
    Extends the native Odoo customer portal controller to:

      1. Surface subscription counters on the portal home page.
      2. Provide a JSON endpoint (/subscription/check-email) that the
         registration form uses to check email availability in real time
         (Layer 4 — HTTP / frontend-feedback layer).

    All business-rule enforcement (duplicate check, format validation) is
    done server-side in res.users constraints; this controller only exposes
    a user-friendly read path for immediate UI feedback.
    """

    def _prepare_home_portal_values(self, counters):
        """Add subscription count badge to the portal home page."""
        values = super()._prepare_home_portal_values(counters)
        if 'subscription_count' in counters:
            values['subscription_count'] = 0
        return values

    # ── Email availability endpoint (Layer 4) ────────────────────────────────
    @route(
        '/subscription/check-email',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def check_email_availability(self, email=None, **kwargs):
        """
        JSON endpoint consumed by the portal registration form to give
        real-time feedback on whether an email address is already registered.

        This is a *read-only* pre-flight check; it does NOT register the user.
        The authoritative rejection of duplicates happens in the ORM constraints
        on res.users (models/res_users.py).

        Request body (JSON):
            { "email": "candidate@example.com" }

        Response (JSON):
            { "available": true }   — email is free to register
            { "available": false,
              "reason": "already_registered",
              "message": "An account with this email already exists…" }
            { "available": false,
              "reason": "invalid_format",
              "message": "…is not a valid email address." }

        Test case coverage:
            TC-1  New unique email       → available: true
            TC-2  Existing email         → available: false, reason: already_registered
            TC-3  Case-variant duplicate → available: false, reason: already_registered
                  (=ilike search is case-insensitive)
        """
        import re
        EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')

        if not email or not isinstance(email, str):
            return {
                'available': False,
                'reason': 'invalid_format',
                'message': request.env['ir.translation']._get_source(
                    None, 'code', request.env.lang,
                    'Please enter an email address.',
                ) or 'Please enter an email address.',
            }

        email = email.strip()

        if not EMAIL_RE.match(email):
            return {
                'available': False,
                'reason': 'invalid_format',
                'message': (
                    '"%s" is not a valid email address. '
                    'Please enter a complete address in the format name@domain.com.' % email
                ),
            }

        already_registered = request.env['res.users'].sudo().search(
            [('login', '=ilike', email)],
            limit=1,
        )

        if already_registered:
            return {
                'available': False,
                'reason': 'already_registered',
                'message': (
                    'An account with the email address "%s" already exists. '
                    'Please sign in to your existing account or use a different email address.' % email
                ),
            }

        return {'available': True}
