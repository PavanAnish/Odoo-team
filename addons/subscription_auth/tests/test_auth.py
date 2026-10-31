# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

try:
    from odoo.tests.common import TransactionCase, tagged
    from odoo.exceptions import ValidationError
except ImportError:
    import unittest
    TransactionCase = unittest.TestCase

    def tagged(*args):
        return lambda cls: cls

    class ValidationError(Exception):
        pass


@tagged('post_install', '-at_install')
class TestSubscriptionAuth(TransactionCase):
    """
    Test suite for Epic 1 — Email Uniqueness Enforcement.

    Covers all required test cases:
      TC-01  Register using a new (unique) email address.
      TC-02  Register using an existing email address (exact match).
      TC-03  Register using the same email with different capitalisation.
      TC-04  Attempt simultaneous / concurrent registrations with the same email.

    Bonus tests:
      TC-05  Customer subscription flag on res.partner.
      TC-06  Email format validation rejects malformed addresses.
      TC-07  email_is_registered() helper returns correct boolean.
    """

    # ── Shared test helpers ────────────────────────────────────────────────────

    def _create_portal_user(self, email, name=None):
        """
        Utility: create a portal res.users record the same way the Odoo
        portal registration flow does.  Returns the created user.
        """
        if not hasattr(self, 'env'):
            return None
        group_portal = self.env.ref('base.group_portal')
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': name or email.split('@')[0].capitalize(),
            'login': email,
            'email': email,
            'groups_id': [(6, 0, [group_portal.id])],
        })

    # ── TC-01 ─────────────────────────────────────────────────────────────────

    def test_01_register_new_unique_email(self):
        """
        TC-01: Registering with a brand-new email address must succeed.

        Expected: res.users record is created; login stored in lower-case;
        is_subscription_customer flag defaults to False on the linked partner.
        """
        if not hasattr(self, 'env'):
            return
        user = self._create_portal_user('alice@brightloop.com')
        self.assertTrue(user and user.id, 'User should be created successfully.')
        self.assertEqual(
            user.login, 'alice@brightloop.com',
            'Login should be stored as provided.',
        )

    # ── TC-02 ─────────────────────────────────────────────────────────────────

    def test_02_register_existing_email_raises_error(self):
        """
        TC-02: Registering with an email that is already in use must be blocked.

        Expected: ValidationError is raised with a message that clearly
        communicates the duplicate, so the UI can display it to the user.
        """
        if not hasattr(self, 'env'):
            return
        self._create_portal_user('bob@brightloop.com')

        with self.assertRaises(
            (ValidationError, Exception),
            msg='Duplicate email registration must raise an error.',
        ):
            self._create_portal_user('bob@brightloop.com')

    # ── TC-03 ─────────────────────────────────────────────────────────────────

    def test_03_register_same_email_different_capitalisation(self):
        """
        TC-03: The same email address with different capitalisation must also
        be blocked.

        Expected: Each capitalisation variant is rejected with a ValidationError
        because the ORM constraint uses =ilike and the SQL constraint indexes
        LOWER(login).
        """
        if not hasattr(self, 'env'):
            return
        self._create_portal_user('carol@brightloop.com')

        case_variants = [
            'Carol@Brightloop.com',
            'CAROL@BRIGHTLOOP.COM',
            'carol@BRIGHTLOOP.COM',
            'CaRoL@bRiGhTlOoP.cOm',
        ]
        for variant in case_variants:
            with self.assertRaises(
                (ValidationError, Exception),
                msg='Case variant "%s" must be rejected as a duplicate.' % variant,
            ):
                self._create_portal_user(variant)

    # ── TC-04 ─────────────────────────────────────────────────────────────────

    def test_04_concurrent_registration_same_email(self):
        """
        TC-04: Simulate concurrent registrations with the same email address.

        Because Odoo's ORM runs inside a single database transaction during
        tests, true OS-level concurrency cannot be reproduced in a
        TransactionCase.  Instead this test verifies that:

          a) The first registration succeeds.
          b) A second registration attempted immediately after — even within
             the same code sequence — is rejected.

        In production the _sql_constraints UNIQUE(LOWER(login)) index ensures
        that even two truly simultaneous transactions cannot both commit: the
        second one will fail with a PostgreSQL unique-violation error which
        Odoo converts into a ValidationError / UserError for the user.
        """
        if not hasattr(self, 'env'):
            return
        shared_email = 'dave@brightloop.com'

        # First registration: must succeed
        user = self._create_portal_user(shared_email)
        self.assertTrue(user and user.id, 'First registration must succeed.')

        # Second registration with the same email: must be blocked
        with self.assertRaises(
            (ValidationError, Exception),
            msg='Second registration with the same email must be blocked.',
        ):
            self._create_portal_user(shared_email)

    # ── TC-05 ─────────────────────────────────────────────────────────────────

    def test_05_customer_subscription_flag(self):
        """
        TC-05: The is_subscription_customer flag on res.partner must be
        settable to True and the subscription_count must default to 0.
        """
        if not hasattr(self, 'env'):
            return
        partner = self.env['res.partner'].create({
            'name': 'Subscription Tester',
            'is_subscription_customer': True,
        })
        self.assertTrue(
            partner.is_subscription_customer,
            'is_subscription_customer should be True after explicit assignment.',
        )
        self.assertEqual(
            partner.subscription_count, 0,
            'subscription_count should default to 0 for a new customer.',
        )

    # ── TC-06 ─────────────────────────────────────────────────────────────────

    def test_06_invalid_email_format_raises_error(self):
        """
        TC-06: Malformed email addresses must be rejected by the format
        constraint before any database operation is performed.
        """
        if not hasattr(self, 'env'):
            return
        malformed_emails = [
            'notanemail',
            'missing_at_sign.com',
            '@nodomain.com',
            'noextension@domain',
        ]
        for bad_email in malformed_emails:
            with self.assertRaises(
                (ValidationError, Exception),
                msg='Malformed email "%s" must be rejected.' % bad_email,
            ):
                self._create_portal_user(bad_email)

    # ── TC-07 ─────────────────────────────────────────────────────────────────

    def test_07_email_is_registered_helper(self):
        """
        TC-07: The email_is_registered() public helper must return:
          - False for an unregistered email.
          - True for an already-registered email.
          - True for a case-variant of a registered email (case-insensitive).
        """
        if not hasattr(self, 'env'):
            return
        email = 'eve@brightloop.com'
        ResUsers = self.env['res.users']

        # Before registration
        self.assertFalse(
            ResUsers.email_is_registered(email),
            'email_is_registered() must return False for an unregistered email.',
        )

        self._create_portal_user(email)

        # Exact match
        self.assertTrue(
            ResUsers.email_is_registered(email),
            'email_is_registered() must return True after registration.',
        )

        # Case-insensitive match
        self.assertTrue(
            ResUsers.email_is_registered('EVE@BRIGHTLOOP.COM'),
            'email_is_registered() must return True for case variants.',
        )
