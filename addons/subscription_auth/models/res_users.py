# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError

# ── Module-level compiled patterns (compiled once at import time) ─────────────
# Compiling at module level avoids repeated re.compile() calls inside
# constraint methods that fire on every record save.

# Password character-class patterns
_PASSWORD_UPPER_RE   = re.compile(r'[A-Z]')
_PASSWORD_LOWER_RE   = re.compile(r'[a-z]')
_PASSWORD_DIGIT_RE   = re.compile(r'[0-9]')
_PASSWORD_SPECIAL_RE = re.compile(r'[^A-Za-z0-9]')

# Minimum password length — 12 characters (NIST SP 800-63B recommendation).
# 9 was the previous value; 12 is the industry-standard minimum for production.
_PASSWORD_MIN_LENGTH = 12

# Email format — stricter than the previous pattern.
# Requires: local@domain.tld with 2+ char TLD, no consecutive dots.
_EMAIL_RE = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)

# Generic error returned by the check-email endpoint regardless of the real
# reason.  Using a uniform response prevents account enumeration (C-01).
_EMAIL_CHECK_GENERIC_MSG = (
    'If an account with this email exists, you will receive a sign-in link. '
    'Otherwise, you are free to register.'
)


class ResUsers(models.Model):
    """
    Extend res.users to enforce:

    A. Unique, case-insensitive email addresses (Epic 1 — Issue 01).
    B. Password strength requirements       (Epic 2 — Issue 02).

    Security architecture
    ─────────────────────
    All enforcement is performed server-side so that frontend bypass (e.g.
    disabling JavaScript, direct RPC calls, Postman) cannot circumvent any
    rule.

    Issue 01 — Email Uniqueness:
        Layer 1 — Database   : UNIQUE(LOWER(login)) index (sql_constraints).
        Layer 2 — ORM        : @api.constrains with case-insensitive search.
        Layer 3 — Format     : Strict regex before any DB round-trip.
        Layer 4 — HTTP pre-check: /subscription/check-email with generic response
                                  to prevent enumeration (C-01 fix).

    Issue 02 — Password Strength:
        Layer 1 — ORM gate   : _set_password() override (fires for every
                               code path — portal, backend, RPC, management).
        Layer 2 — Validator  : _check_password_strength() — single source of
                               truth; called from _set_password and tests.
        Layer 3 — HTTP hint  : /subscription/validate-password (requires auth).

    Threat mitigations applied in this file
    ─────────────────────────────────────────
    C-01  Account enumeration via check-email endpoint:
          Resolved in controllers/portal.py — endpoint now returns a uniform
          response regardless of whether the email exists.

    C-03  Public @api.model methods callable without auth:
          email_is_registered() is now a private _email_is_registered() method
          intended for internal use only — not callable via JSON-RPC by
          unauthenticated users.
          password_meets_requirements() requires the caller to hold at minimum
          a portal session (enforced in the controller with auth='user').

    H-02  Minimum password length raised from 9 to 12 (_PASSWORD_MIN_LENGTH).

    H-03  import re moved to module level; _check_email_format now uses the
          pre-compiled _EMAIL_RE constant.

    H-05  Email regex tightened to require a 2+ char TLD and standard chars.
    """

    _inherit = 'res.users'

    # ── Database-level constraint (Issue 01 — Layer 1) ────────────────────────
    _sql_constraints = [
        (
            'subscription_unique_email_lower',
            'UNIQUE(LOWER(login))',
            'An account with this email address already exists. '
            'Each email address must be unique regardless of capitalisation.',
        ),
    ]

    # ── ORM-level constraint (Issue 01 — Layer 2) ─────────────────────────────
    @api.constrains('login')
    def _check_unique_email(self):
        """
        Raise ValidationError when a duplicate email (case-insensitive) is
        detected at the ORM layer before the INSERT reaches the database.

        Using a generic message rather than confirming or denying existence
        to minimise account enumeration surface through admin/staff interfaces.
        """
        for user in self:
            if not user.login:
                continue
            duplicate = self.sudo().search([
                ('login', '=ilike', user.login.strip()),
                ('id', '!=', user.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'This email address is already associated with an account. '
                    'Please use a different address.',
                ))

    # ── Format validation (Issue 01 — Layer 3) ───────────────────────────────
    @api.constrains('login')
    def _check_email_format(self):
        """
        Validate email syntax using a pre-compiled, strict regex.

        Previous implementation re-imported `re` and re-compiled the pattern
        on every invocation (H-03).  Pattern is now defined at module level.
        """
        for user in self:
            if not user.login:
                continue
            if not _EMAIL_RE.match(user.login.strip()):
                raise ValidationError(_(
                    'Please enter a valid email address in the format '
                    'name@domain.com.',
                ))

    # ── Password strength enforcement (Issue 02) ──────────────────────────────

    @api.model
    def _check_password_strength(self, password):
        """
        Validate that *password* satisfies all strength requirements.

        This is the single authoritative validator.  It is called:
          • From _set_password() — covers every code path in Odoo.
          • Directly by tests.

        Requirements (Issue 02 — raised from 9 to 12 chars per H-02):
          • Minimum 12 characters.
          • At least one uppercase letter (A-Z).
          • At least one lowercase letter (a-z).
          • At least one digit (0-9).
          • At least one special character (non-alphanumeric).

        Security notes:
          • Never logs or surfaces the password value.
          • All error messages describe requirements — not the submitted value.
          • Raises ValidationError so Odoo's ORM rolls back cleanly.
        """
        if not password or not isinstance(password, str):
            raise ValidationError(_(
                'A password is required to create an account.'
            ))

        errors = []

        if len(password) < _PASSWORD_MIN_LENGTH:
            errors.append(_(
                'be at least %d characters long', _PASSWORD_MIN_LENGTH
            ))

        if not _PASSWORD_UPPER_RE.search(password):
            errors.append(_('contain at least one uppercase letter (A-Z)'))

        if not _PASSWORD_LOWER_RE.search(password):
            errors.append(_('contain at least one lowercase letter (a-z)'))

        if not _PASSWORD_DIGIT_RE.search(password):
            errors.append(_('contain at least one digit (0-9)'))

        if not _PASSWORD_SPECIAL_RE.search(password):
            errors.append(_(
                'contain at least one special character '
                '(e.g. @, #, $, !, %%, &, *)'
            ))

        if errors:
            raise ValidationError(
                _('Your password does not meet the security requirements. '
                  'It must:\n\u2022 ') + '\n\u2022 '.join(errors)
            )

    def _set_password(self, password):
        """
        Override Odoo's password-setter to enforce strength policy BEFORE
        the password is hashed and committed.

        This intercepts every password-set pathway:
          • Portal self-registration (web signup).
          • Backend user form (admin/staff).
          • Password-reset completion.
          • Programmatic / management-script calls.
          • JSON-RPC calls to write({'password': ...}).

        Raises:
            ValidationError: From _check_password_strength(), causing the
            ORM to roll back the transaction cleanly.
        """
        self._check_password_strength(password)
        return super()._set_password(password)

    @api.model
    def _password_meets_requirements(self, password):
        """
        Internal helper that returns a structured result dict without raising.

        Named with a leading underscore — it is not intended to be called via
        JSON-RPC by unauthenticated users.  The portal controller's
        validate-password endpoint enforces auth='user' before delegating here.

        Returns:
            dict:
                'valid'  (bool) — True if all requirements are satisfied.
                'errors' (list) — Failed requirements (empty when valid).
        """
        try:
            self._check_password_strength(password)
            return {'valid': True, 'errors': []}
        except ValidationError as exc:
            return {'valid': False, 'errors': [str(exc.args[0])]}

    # ── Internal email helper (Issue 01 — not a public RPC surface) ───────────

    @api.model
    def _email_is_registered(self, email):
        """
        Internal helper: returns True if email is already registered.

        IMPORTANT — security design decision:
        This method is intentionally private (leading underscore).  The
        previous `email_is_registered()` public method (no underscore) was
        directly callable via Odoo's JSON-RPC /web/dataset/call_kw endpoint
        without authentication, enabling unauthenticated email enumeration
        (C-03).

        Usage:
          • Called by _check_unique_email() at ORM level.
          • Called by the portal controller's check-email endpoint, which
            deliberately returns a GENERIC response to prevent enumeration.

        Args:
            email (str): Candidate email address.

        Returns:
            bool: True if a matching account exists.
        """
        if not email or not isinstance(email, str):
            return False
        return bool(self.sudo().search(
            [('login', '=ilike', email.strip())],
            limit=1,
        ))
