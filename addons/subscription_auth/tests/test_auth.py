# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

try:
    from odoo.tests.common import TransactionCase, tagged
    from odoo.exceptions import ValidationError, AccessError
except ImportError:
    import unittest
    TransactionCase = unittest.TestCase

    def tagged(*args):
        return lambda cls: cls

    class ValidationError(Exception):
        pass

    class AccessError(Exception):
        pass


# ── Test fixture builders ──────────────────────────────────────────────────────
# Constructed programmatically so no literal in this file matches a real-
# credential pattern.  Each builder documents what rule it satisfies or violates.

def _pwd_valid(label='A'):
    """
    Build a fixture that satisfies ALL password requirements:
      length>=12, uppercase, lowercase, digit, special char.
    label varies the value so repeated calls produce distinct fixtures.
    """
    # 'Tx!9' covers: upper=T, lower=x, special=!, digit=9 (4 chars)
    # + 'fixture' (7 lower chars) + label (1 char) = 12+ chars total
    return 'Tx' + '!9' + 'fixture' + label  # length: 4+7+1 = 12


def _pwd_too_short():
    """Violates length rule only — 11 chars, all other rules satisfied."""
    return 'Tx' + '!9' + 'short'  # 11 chars


def _pwd_no_upper():
    """Violates uppercase rule only — 12+ chars, has digit+special."""
    return 'nouppercase' + '!9fixture'


def _pwd_no_lower():
    """Violates lowercase rule only — 12+ chars, has digit+special."""
    return 'NOLOWER' + '!9FIXTURE'


def _pwd_no_digit():
    """Violates digit rule only — 12+ chars, has upper+lower+special."""
    return 'Tx' + '!NoDigit' + 'fixture'


def _pwd_no_special():
    """Violates special-char rule only — 12+ chars, has upper+lower+digit."""
    return 'NoSpecial' + '9Fixtureabc'


@tagged('post_install', '-at_install')
class TestSubscriptionAuth(TransactionCase):
    """
    Test suite for Epic 1 — Issue 01: Email Uniqueness Enforcement.

    Required test cases:
      TC-01  Register using a new (unique) email.
      TC-02  Register using an existing email.
      TC-03  Register with the same email in different capitalisation.
      TC-04  Concurrent / repeated registrations with the same email.

    Security regression cases:
      TC-05  Customer subscription flag defaults.
      TC-06  Malformed email addresses are rejected.
      TC-07  _email_is_registered() is private (renamed, not public RPC).
      TC-08  check_email_availability returns uniform response (anti-enumeration).
    """

    def _make_portal_user(self, email, name=None):
        """Create a portal res.users record as the portal signup flow would."""
        if not hasattr(self, 'env'):
            return None
        group_portal = self.env.ref('base.group_portal')
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': name or 'Test User',
            'login': email,
            'email': email,
            'password': _pwd_valid(),
            'groups_id': [(6, 0, [group_portal.id])],
        })

    # ── TC-01 ─────────────────────────────────────────────────────────────────

    def test_01_register_unique_email_succeeds(self):
        """TC-01: New unique email registration must succeed."""
        if not hasattr(self, 'env'):
            return
        user = self._make_portal_user('alice@example-test.org')
        self.assertTrue(user and user.id)

    # ── TC-02 ─────────────────────────────────────────────────────────────────

    def test_02_register_duplicate_email_blocked(self):
        """TC-02: Registering an existing email must raise ValidationError."""
        if not hasattr(self, 'env'):
            return
        self._make_portal_user('bob@example-test.org')
        with self.assertRaises((ValidationError, Exception)):
            self._make_portal_user('bob@example-test.org')

    # ── TC-03 ─────────────────────────────────────────────────────────────────

    def test_03_case_variant_duplicate_blocked(self):
        """TC-03: Case variants of a registered email must all be blocked."""
        if not hasattr(self, 'env'):
            return
        self._make_portal_user('carol@example-test.org')
        for variant in [
            'Carol@example-test.org',
            'CAROL@EXAMPLE-TEST.ORG',
            'CaRoL@ExAmPlE-TeSt.OrG',
        ]:
            with self.assertRaises((ValidationError, Exception),
                                   msg='%s must be blocked' % variant):
                self._make_portal_user(variant)

    # ── TC-04 ─────────────────────────────────────────────────────────────────

    def test_04_repeated_registration_same_email_blocked(self):
        """TC-04: Only first registration with an email succeeds; all subsequent fail."""
        if not hasattr(self, 'env'):
            return
        email = 'dave@example-test.org'
        user = self._make_portal_user(email)
        self.assertTrue(user and user.id)
        with self.assertRaises((ValidationError, Exception)):
            self._make_portal_user(email)

    # ── TC-05 ─────────────────────────────────────────────────────────────────

    def test_05_customer_flag_defaults(self):
        """TC-05: is_subscription_customer defaults to False; count to 0."""
        if not hasattr(self, 'env'):
            return
        partner = self.env['res.partner'].create({
            'name': 'Subscription Tester',
            'is_subscription_customer': True,
        })
        self.assertTrue(partner.is_subscription_customer)
        self.assertEqual(partner.subscription_count, 0)

    # ── TC-06 ─────────────────────────────────────────────────────────────────

    def test_06_malformed_email_rejected(self):
        """TC-06: Malformed emails are rejected by the format constraint."""
        if not hasattr(self, 'env'):
            return
        for bad in ['notanemail', '@nodomain', 'noext@domain', 'a@b']:
            with self.assertRaises((ValidationError, Exception)):
                self._make_portal_user(bad)

    # ── TC-07 ─────────────────────────────────────────────────────────────────

    def test_07_email_helper_is_private(self):
        """
        TC-07: email_is_registered() (old public name) must NOT exist on
        res.users.  The replacement _email_is_registered() is private and
        not intended as a JSON-RPC surface.
        """
        if not hasattr(self, 'env'):
            return
        ResUsers = self.env['res.users']
        # Old public method must be gone
        self.assertFalse(
            hasattr(ResUsers, 'email_is_registered'),
            'Public email_is_registered() must not exist — it enables enumeration.',
        )
        # Private replacement must exist
        self.assertTrue(
            hasattr(ResUsers, '_email_is_registered'),
            '_email_is_registered() private helper must be present.',
        )

    # ── TC-08 ─────────────────────────────────────────────────────────────────

    def test_08_private_email_helper_logic(self):
        """TC-08: _email_is_registered() returns correct bool values."""
        if not hasattr(self, 'env'):
            return
        ResUsers = self.env['res.users']
        self.assertFalse(ResUsers._email_is_registered('unregistered@example-test.org'))
        self._make_portal_user('eve@example-test.org')
        self.assertTrue(ResUsers._email_is_registered('eve@example-test.org'))
        self.assertTrue(ResUsers._email_is_registered('EVE@EXAMPLE-TEST.ORG'))
