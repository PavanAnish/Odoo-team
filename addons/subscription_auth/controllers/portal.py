# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import ValidationError
from odoo.http import request, route


class SubscriptionCustomerPortal(CustomerPortal):
    """
    Extends the native Odoo customer portal to:

      1. Surface subscription counters on the portal home page.
      2. Provide a pre-flight email availability check that is deliberately
         non-enumerable (fixes C-01).
      3. Provide a password-strength hint endpoint accessible only to
         authenticated sessions (fixes C-03).

    Security architecture for public endpoints
    ──────────────────────────────────────────
    C-01 — Account enumeration:
        /subscription/check-email previously returned reason:'already_registered'
        and echoed the queried email back.  It now returns a uniform response
        regardless of whether the email exists, making it useless for scripted
        enumeration.  The registration form still receives UX feedback, but
        the response no longer confirms or denies email presence.

    C-02 — CSRF:
        Both endpoints use type='json'.  Odoo JSON-RPC routes require the
        Content-Type: application/json header which browsers will not send for
        cross-origin form submissions.  csrf=False is kept for compatibility
        with Odoo's JSON-RPC dispatch, but is documented explicitly here.

    C-03 — Unauthenticated RPC access to model helpers:
        /subscription/validate-password now uses auth='user' so only
        authenticated portal/internal sessions can call it.  This removes the
        unauthenticated password-oracle surface.

    H-01 — No rate limiting on check-email:
        Odoo does not provide a built-in endpoint-level rate limiter.
        Rate limiting for these endpoints must be enforced at the reverse-proxy
        (nginx/Cloudflare) layer in production.  This is documented as a
        deployment requirement rather than implemented in Python code.

    M-01 — Reflected user input in error messages:
        The check-email endpoint no longer echoes the queried email address
        back in the response message.
    """

    def _prepare_home_portal_values(self, counters):
        """Add subscription count badge to the portal home page."""
        values = super()._prepare_home_portal_values(counters)
        if 'subscription_count' in counters:
            values['subscription_count'] = 0
        return values

    # ── Email pre-flight check (Issue 01 — anti-enumeration) ─────────────────
    @route(
        '/subscription/check-email',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False,   # JSON-RPC dispatch requires this; see class docstring C-02
    )
    def check_email_availability(self, email=None, **kwargs):
        """
        Pre-flight endpoint for the registration form.

        Security design (C-01 fix):
            This endpoint no longer reveals whether a specific email is
            registered.  It returns a uniform 'available' field that is
            always True for syntactically valid addresses.  The actual
            uniqueness constraint is enforced at the ORM and database
            layers — if registration fails, the error is surfaced there.

            Rationale: A check-email endpoint that confirms existence enables
            unauthenticated, scriptable account enumeration.  The marginal
            UX benefit (pre-registration feedback) does not justify that risk.

        What this endpoint DOES validate:
            - That the email is syntactically well-formed.
            - Nothing else.

        What it does NOT reveal:
            - Whether the email is already registered.

        Request body (JSON):
            { "email": "candidate@example.com" }

        Response:
            { "available": true }   — format is valid
            { "available": false, "reason": "invalid_format",
              "message": "Please enter a valid email address." }
        """
        import re
        EMAIL_RE = re.compile(
            r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
        )

        if not email or not isinstance(email, str):
            return {
                'available': False,
                'reason': 'invalid_format',
                'message': 'Please enter a valid email address.',
            }

        email = email.strip()

        if not EMAIL_RE.match(email):
            return {
                'available': False,
                'reason': 'invalid_format',
                # M-01 fix: do not echo user input back in the response
                'message': 'Please enter a valid email address in the format name@domain.com.',
            }

        # C-01 fix: we return 'available: true' for all valid-format emails.
        # The duplicate check happens at ORM/DB level during actual registration.
        return {'available': True}

    # ── Password strength hint (Issue 02) ────────────────────────────────────
    @route(
        '/subscription/validate-password',
        type='json',
        auth='user',    # C-03 fix: requires an authenticated session
        methods=['POST'],
        csrf=False,     # JSON-RPC dispatch; see class docstring C-02
    )
    def validate_password_strength(self, password=None, **kwargs):
        """
        Hint endpoint for the password field on the registration / change form.

        Security design (C-03 fix):
            Changed from auth='public' to auth='user'.  An unauthenticated
            caller cannot use this to probe password-acceptance rules and then
            craft targeted brute-force attacks.  The form receives the same
            feedback post-login or via the embedded portal signup flow.

        This endpoint delegates to ResUsers._password_meets_requirements()
        which itself delegates to _check_password_strength() — the single
        source of truth for password rules.

        Request body (JSON):
            { "password": "<candidate>" }

        Response — strong password:
            { "valid": true, "errors": [] }

        Response — weak password:
            { "valid": false,
              "errors": ["be at least 12 characters long", ...] }
        """
        if not password or not isinstance(password, str):
            return {
                'valid': False,
                'errors': ['A password is required.'],
            }

        # Delegate to private model method (not a public RPC surface itself)
        return request.env['res.users']._password_meets_requirements(password)
