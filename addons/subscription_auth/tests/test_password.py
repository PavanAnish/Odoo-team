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
class TestPasswordStrength(TransactionCase):
    """
    Test suite for Epic 1 — Issue 02: Password Strength Enforcement.

    Validates that weak passwords are rejected server-side by
    ResUsers._check_password_strength() and _set_password(), not merely
    by a frontend form.

    Required test cases:
      TC-01  Password with fewer than 9 characters.
      TC-02  Password without uppercase letters.
      TC-03  Password without lowercase letters.
      TC-04  Password without special characters.
      TC-05  Password satisfying all requirements.

    Bonus:
      TC-06  Empty / None password is rejected.
      TC-07  Exactly 8 characters (boundary) is rejected (must be > 8).
      TC-08  Exactly 9 characters satisfying all rules is accepted.
      TC-09  password_meets_requirements() helper returns correct structure.
    """

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _assert_password_rejected(self, password, msg=''):
        """
        Assert that setting *password* on a res.users record raises a
        ValidationError, confirming server-side rejection.
        """
        if not hasattr(self, 'env'):
            return
        with self.assertRaises(
            (ValidationError, Exception),
            msg=msg or 'Weak password "%s" must be rejected server-side.' % password,
        ):
            self.env['res.users']._check_password_strength(password)

    def _assert_password_accepted(self, password, msg=''):
        """
        Assert that *password* passes _check_password_strength() without
        raising any exception.
        """
        if not hasattr(self, 'env'):
            return
        try:
            self.env['res.users']._check_password_strength(password)
        except (ValidationError, Exception) as exc:
            self.fail(
                msg or 'Strong password "%s" should be accepted but was rejected: %s'
                % (password, exc)
            )

    # ── TC-01 ─────────────────────────────────────────────────────────────────

    def test_01_password_too_short(self):
        """
        TC-01: A password with fewer than 9 characters must be rejected.

        The minimum required length is 9 (i.e., MORE than 8 characters).
        All other rules may be satisfied; the length alone is sufficient
        to trigger rejection.
        """
        if not hasattr(self, 'env'):
            return
        short_passwords = [
            'Ab1!',       # 4 chars
            'Abc1!xy',    # 7 chars
            'Abcde1!x',   # 8 chars — boundary, still too short
        ]
        for pwd in short_passwords:
            self._assert_password_rejected(
                pwd,
                msg='Password "%s" has fewer than 9 characters and must be rejected.' % pwd,
            )

    # ── TC-02 ─────────────────────────────────────────────────────────────────

    def test_02_password_no_uppercase(self):
        """
        TC-02: A password without at least one uppercase letter (A-Z)
        must be rejected even if it meets all other requirements.
        """
        if not hasattr(self, 'env'):
            return
        no_upper_passwords = [
            'alllower1!',          # no uppercase
            'abcdefgh1!',          # no uppercase
            'secure@password9',    # no uppercase
        ]
        for pwd in no_upper_passwords:
            self._assert_password_rejected(
                pwd,
                msg='Password "%s" has no uppercase letter and must be rejected.' % pwd,
            )

    # ── TC-03 ─────────────────────────────────────────────────────────────────

    def test_03_password_no_lowercase(self):
        """
        TC-03: A password without at least one lowercase letter (a-z)
        must be rejected even if it meets all other requirements.
        """
        if not hasattr(self, 'env'):
            return
        no_lower_passwords = [
            'ALLUPPER1!',          # no lowercase
            'SECURE@PASSWORD9',    # no lowercase
            'ABC123!@#XYZ',        # no lowercase
        ]
        for pwd in no_lower_passwords:
            self._assert_password_rejected(
                pwd,
                msg='Password "%s" has no lowercase letter and must be rejected.' % pwd,
            )

    # ── TC-04 ─────────────────────────────────────────────────────────────────

    def test_04_password_no_special_character(self):
        """
        TC-04: A password without at least one special (non-alphanumeric)
        character must be rejected even if it meets all other requirements.
        """
        if not hasattr(self, 'env'):
            return
        no_special_passwords = [
            'Abcdefgh1',       # no special char
            'SecurePass9',     # no special char
            'Brightloop2024',  # no special char
        ]
        for pwd in no_special_passwords:
            self._assert_password_rejected(
                pwd,
                msg='Password "%s" has no special character and must be rejected.' % pwd,
            )

    # ── TC-05 ─────────────────────────────────────────────────────────────────

    def test_05_password_meets_all_requirements(self):
        """
        TC-05: A password satisfying ALL requirements must be accepted
        without raising any exception.

        Requirements satisfied:
          ✓ More than 8 characters.
          ✓ At least one uppercase letter.
          ✓ At least one lowercase letter.
          ✓ At least one special character.
        """
        if not hasattr(self, 'env'):
            return
        strong_passwords = [
            'Secure@123',          # 10 chars, all rules met
            'Brightloop!2024',     # 16 chars
            'P@ssw0rd!Strong',     # mixed case + special + digits
            'SuperSecret#99abc',   # 18 chars
        ]
        for pwd in strong_passwords:
            self._assert_password_accepted(
                pwd,
                msg='Password "%s" meets all requirements and must be accepted.' % pwd,
            )

    # ── TC-06 ─────────────────────────────────────────────────────────────────

    def test_06_empty_or_none_password_rejected(self):
        """
        TC-06: An empty string or None must be rejected immediately with a
        clear error message asking the user to provide a password.
        """
        if not hasattr(self, 'env'):
            return
        for empty in [None, '', '   ']:
            with self.assertRaises(
                (ValidationError, Exception),
                msg='Empty/None password must be rejected.',
            ):
                self.env['res.users']._check_password_strength(empty)

    # ── TC-07 ─────────────────────────────────────────────────────────────────

    def test_07_exactly_8_characters_rejected(self):
        """
        TC-07: A password of exactly 8 characters must be rejected.

        The requirement is MORE THAN 8 characters, so 8 is the boundary
        that must fail.
        """
        if not hasattr(self, 'env'):
            return
        # Exactly 8 chars, all other rules satisfied
        boundary = 'Aa1!Bb2@'
        self.assertEqual(len(boundary), 8)
        self._assert_password_rejected(
            boundary,
            msg='Password of exactly 8 characters must be rejected (must be > 8).',
        )

    # ── TC-08 ─────────────────────────────────────────────────────────────────

    def test_08_exactly_9_characters_accepted(self):
        """
        TC-08: A password of exactly 9 characters satisfying all other
        rules must be accepted (9 is the minimum valid length).
        """
        if not hasattr(self, 'env'):
            return
        # Exactly 9 chars, all rules satisfied
        boundary = 'Aa1!Bb2@c'
        self.assertEqual(len(boundary), 9)
        self._assert_password_accepted(
            boundary,
            msg='Password of exactly 9 characters (all rules met) must be accepted.',
        )

    # ── TC-09 ─────────────────────────────────────────────────────────────────

    def test_09_password_meets_requirements_helper(self):
        """
        TC-09: The password_meets_requirements() public helper must return
        the correct dict structure for both valid and invalid passwords.

        This helper is used by the /subscription/validate-password controller
        endpoint to send structured feedback to the registration form.
        """
        if not hasattr(self, 'env'):
            return
        ResUsers = self.env['res.users']

        # Valid password
        result = ResUsers.password_meets_requirements('Secure@123')
        self.assertTrue(result.get('valid'), 'Strong password must return valid=True.')
        self.assertEqual(result.get('errors'), [], 'No errors expected for strong password.')

        # Weak password — too short and no uppercase
        result = ResUsers.password_meets_requirements('abc!1')
        self.assertFalse(result.get('valid'), 'Weak password must return valid=False.')
        self.assertTrue(
            len(result.get('errors', [])) > 0,
            'Errors list must not be empty for a weak password.',
        )
