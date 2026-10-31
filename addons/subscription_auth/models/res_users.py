# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# Password strength requirements (applied in _check_password_strength)
_PASSWORD_MIN_LENGTH = 9          # more than 8 characters
_PASSWORD_UPPER_RE  = re.compile(r'[A-Z]')
_PASSWORD_LOWER_RE  = re.compile(r'[a-z]')
_PASSWORD_SPECIAL_RE = re.compile(r'[^A-Za-z0-9]')


class ResUsers(models.Model):
    """
    Extend res.users to enforce:

    A. Unique, case-insensitive email addresses (Epic 1 — Issue 01).
    B. Password strength requirements       (Epic 1 — Issue 02).

    Both are validated server-side before any data reaches the database.

    Issue 02 — Password Strength:
        Password must satisfy ALL of the following:
          • More than 8 characters (minimum length 9).
          • At least one uppercase letter  (A-Z).
          • At least one lowercase letter  (a-z).
          • At least one special character (non-alphanumeric).

        Enforcement layers:
          1. _check_password_strength() — shared validator method.
          2. _set_password() override   — called by Odoo before hashing;
             this is the authoritative server-side gate regardless of how
             a password is set (portal signup, backend form, API call).
          3. Portal controller          — /subscription/validate-password
             endpoint gives the registration form real-time feedback.

    Issue 01 — Email Uniqueness:
        1. _sql_constraints  : UNIQUE(LOWER(login)) at database level.
        2. @api.constrains   : ORM-level =ilike duplicate check.
        3. _check_email_format: Format validator rejects malformed addresses.
        4. Portal controller  : /subscription/check-email pre-flight check.
    """
    _inherit = 'res.users'

    # ── Database-level constraint (Layer 1) ───────────────────────────────────
    # Odoo does not natively create a case-insensitive unique index on
    # res.users.login (which maps to email for portal users).  We add a named
    # PostgreSQL constraint here so that two rows with emails that differ only
    # in capitalisation cannot coexist, even under concurrent requests.
    _sql_constraints = [
        (
            'subscription_unique_email_lower',
            'UNIQUE(LOWER(login))',
            'An account with this email address already exists. '
            'Each email address must be unique regardless of capitalisation.'
        ),
    ]

    # ── ORM-level constraint (Layer 2) ────────────────────────────────────────
    @api.constrains('login')
    def _check_unique_email(self):
        """
        Raise ValidationError when a duplicate email (case-insensitive) is
        detected before the record reaches the database layer.

        Covers:
          • Standard registration (TC-1 / TC-2).
          • Case-variant duplicates: 'User@X.com' vs 'user@x.com' (TC-3).
          • Concurrent requests are ultimately caught by _sql_constraints (TC-4).
        """
        for user in self:
            if not user.login:
                continue
            duplicate = self.sudo().search([
                ('login', '=ilike', user.login),
                ('id', '!=', user.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'An account with the email address "%s" already exists. '
                    'Please use a different email address or sign in to your '
                    'existing account.',
                    user.login,
                ))

    # ── Format validation (Layer 3) ───────────────────────────────────────────
    @api.constrains('login')
    def _check_email_format(self):
        """
        Validate that the login (email) field contains a syntactically valid
        email address before any database operation is attempted.

        This is intentionally a separate constraint from _check_unique_email so
        that each constraint surfaces a focused, actionable error message.
        """
        import re
        email_re = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
        for user in self:
            if not user.login:
                continue
            if not email_re.match(user.login.strip()):
                raise ValidationError(_(
                    '"%s" is not a valid email address. '
                    'Please enter a complete email in the format name@domain.com.',
                    user.login,
                ))

    # ═══════════════════════════════════════════════════════════════════════
    # Issue 02 — Password Strength Enforcement
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def _check_password_strength(self, password):
        """
        Validate that *password* satisfies all strength requirements.

        Requirements (Issue 02):
          • More than 8 characters — minimum length is 9.
          • At least one uppercase letter (A-Z).
          • At least one lowercase letter (a-z).
          • At least one special character (non-alphanumeric).

        This method is the single source of truth for password rules.
        It is called from:
          • _set_password()  — server-side gate (always executed).
          • Portal controller — /subscription/validate-password endpoint
            (real-time feedback before form submission).

        Args:
            password (str): Plain-text password to validate.

        Raises:
            ValidationError: With a precise, localised message listing
                every unsatisfied requirement so the user knows exactly
                what to fix.
        """
        if not password or not isinstance(password, str):
            raise ValidationError(_(
                'A password is required to create an account.'
            ))

        errors = []

        if len(password) < _PASSWORD_MIN_LENGTH:
            errors.append(_(
                'be more than 8 characters long (current length: %d)',
                len(password),
            ))

        if not _PASSWORD_UPPER_RE.search(password):
            errors.append(_('contain at least one uppercase letter (A-Z)'))

        if not _PASSWORD_LOWER_RE.search(password):
            errors.append(_('contain at least one lowercase letter (a-z)'))

        if not _PASSWORD_SPECIAL_RE.search(password):
            errors.append(_(
                'contain at least one special character '
                '(e.g. @, #, $, !, %, &, *)'
            ))

        if errors:
            raise ValidationError(
                _('Your password does not meet the security requirements. '
                  'It must:\n• ') + '\n• '.join(errors)
            )

    def _set_password(self, password):
        """
        Override Odoo\'s password-setter to enforce strength rules BEFORE
        the password is hashed and written to the database.

        This is the authoritative server-side enforcement point.  It fires
        for every password change path in Odoo:
          • Portal self-registration.
          • Backend user form.
          • Programmatic API / management commands.

        Raises:
            ValidationError: Propagated from _check_password_strength().
        """
        self._check_password_strength(password)
        return super()._set_password(password)

    @api.model
    def password_meets_requirements(self, password):
        """
        Public boolean helper consumed by the portal registration controller
        to give the registration form real-time password-strength feedback.

        Returns:
            dict with keys:
              'valid'  (bool)  — True if all requirements are satisfied.
              'errors' (list)  — Human-readable list of failed requirements
                                 (empty when valid is True).
        """
        try:
            self._check_password_strength(password)
            return {'valid': True, 'errors': []}
        except ValidationError as exc:
            return {'valid': False, 'errors': [str(exc.args[0])]}

    # ═══════════════════════════════════════════════════════════════════════
    # Issue 01 — Email helpers
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def email_is_registered(self, email):
        """
        Public helper consumed by the portal registration controller to check
        whether an email address is already associated with an account.

        Returns True if the email is already registered (case-insensitive),
        False otherwise.  This enables the frontend to display an immediate,
        clear error message before the user submits the form.

        Args:
            email (str): The candidate email address to check.

        Returns:
            bool: True if a matching account already exists.
        """
        if not email:
            return False
        return bool(self.sudo().search(
            [('login', '=ilike', email.strip())],
            limit=1,
        ))
