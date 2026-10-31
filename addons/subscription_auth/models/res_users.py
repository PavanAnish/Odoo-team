# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    """
    Extend res.users to enforce unique, case-insensitive email addresses
    across all customer registrations in the Subscription Management System.

    Problem addressed (Epic 1):
        The system may allow multiple accounts to register using the same
        email address (including case variants such as User@Example.com vs
        user@example.com).

    Solution — four enforcement layers:
        1. _sql_constraints  : Database-level UNIQUE constraint on LOWER(email)
                               prevents duplicates even under concurrent inserts.
        2. @api.constrains   : ORM-level validator raises ValidationError before
                               any INSERT/UPDATE reaches the database.
        3. _check_email_format: Format validator rejects malformed addresses.
        4. Portal controller  : HTTP layer returns a clear JSON error to the
                               registration form (see controllers/auth.py).
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
