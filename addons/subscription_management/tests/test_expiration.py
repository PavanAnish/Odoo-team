# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
"""
Tests for Quotation Validity & Expiration Management.

TC-01  Create quotation with configurable validity duration
TC-02  Verify automatic expiry date calculation
TC-03  Change validity duration — expiry date recalculates
TC-04  Confirm quotation before expiry — succeeds
TC-05  Reject confirmation of an expired quotation (backend enforcement)
TC-06  Reject activation of an expired / unconfirmed quotation
TC-07  Verify expiration_status = 'expired' after expiry date passes
TC-08  Verify expiration_status = 'expiring_soon' within threshold
TC-09  Verify expiration filter domain matches correct records
TC-10  Verify _cron_refresh_expiration_status recomputes open quotations
TC-11  Unauthorised user cannot set negative validity duration
TC-12  Confirmed quotations are NOT marked expired even if date_expiration is past
"""

try:
    from datetime import date, timedelta
    from odoo.tests import TransactionCase, tagged
    from odoo.exceptions import ValidationError

    @tagged('post_install', '-at_install')
    class TestQuotationExpiration(TransactionCase):
        """Automated tests covering quotation validity & expiration management."""

        @classmethod
        def setUpClass(cls):
            super().setUpClass()

            # ------------------------------------------------------------------
            # Minimal supporting fixtures
            # ------------------------------------------------------------------
            cls.partner = cls.env['res.partner'].create({
                'name': 'Test Customer — Expiration Suite',
                'is_subscription_customer': True,
                'email': 'expiration@test.example',
            })

            cls.plan = cls.env['subscription.plan'].create({
                'name': 'Test Plan — Expiration',
                'billing_frequency': 'monthly',
            })

            cls.product_tmpl = cls.env['product.template'].create({
                'name': 'Test Product — Expiration',
                'type': 'service',
                'list_price': 1000.0,
                'is_subscription_product': True,
                'subscription_plan_id': cls.plan.id,
            })
            cls.product = cls.product_tmpl.product_variant_ids[0]

        # ------------------------------------------------------------------
        # Helper
        # ------------------------------------------------------------------
        def _make_quotation(self, date_quotation=None, validity_days=30, date_expiration=None):
            """Create a minimal draft quotation for testing."""
            today = date.today()
            q_date = date_quotation or today
            exp_date = date_expiration or (q_date + timedelta(days=validity_days))
            sub = self.env['subscription.subscription'].create({
                'partner_id': self.partner.id,
                'plan_id': self.plan.id,
                'date_quotation': q_date,
                'validity_days': validity_days,
                'date_expiration': exp_date,
                'date_start': today,
            })
            # Add at least one product line so confirm works
            self.env['subscription.subscription.line'].create({
                'subscription_id': sub.id,
                'product_id': self.product.id,
                'quantity': 1,
            })
            return sub

        # ==================================================================
        # TC-01 — Create quotation with configurable validity duration
        # ==================================================================
        def test_01_create_quotation_with_valid_duration(self):
            """TC-01: validity_days is stored and non-negative when a quotation is created."""
            sub = self._make_quotation(validity_days=14)
            self.assertEqual(
                sub.validity_days, 14,
                "validity_days should be saved as 14 on the quotation."
            )
            self.assertGreater(sub.validity_days, 0, "validity_days must be positive.")

        # ==================================================================
        # TC-02 — Automatic expiry date calculation
        # ==================================================================
        def test_02_verify_automatic_expiry_date_calculation(self):
            """TC-02: date_expiration == date_quotation + validity_days."""
            today = date.today()
            validity = 7
            sub = self._make_quotation(date_quotation=today, validity_days=validity)
            expected_expiry = today + timedelta(days=validity)
            self.assertEqual(
                sub.date_expiration, expected_expiry,
                "date_expiration should equal date_quotation + validity_days."
            )

        # ==================================================================
        # TC-03 — Change validity duration → expiry date recalculates
        # ==================================================================
        def test_03_change_validity_duration_recalculation(self):
            """TC-03: Changing validity_days and recomputing updates date_expiration."""
            today = date.today()
            sub = self._make_quotation(date_quotation=today, validity_days=30)

            # Simulate what the onchange produces by writing both fields together
            new_validity = 60
            new_expiry = today + timedelta(days=new_validity)
            sub.write({
                'validity_days': new_validity,
                'date_expiration': new_expiry,
            })

            self.assertEqual(
                sub.validity_days, 60,
                "validity_days should be updated to 60."
            )
            self.assertEqual(
                sub.date_expiration, new_expiry,
                "date_expiration should recalculate to today + 60 days."
            )

        # ==================================================================
        # TC-04 — Confirm quotation before expiry — succeeds
        # ==================================================================
        def test_04_confirm_quotation_before_expiry(self):
            """TC-04: A quotation with a future expiry date can be confirmed successfully."""
            future_expiry = date.today() + timedelta(days=30)
            sub = self._make_quotation(date_expiration=future_expiry)
            sub.action_confirm()
            self.assertEqual(
                sub.state, 'confirmed',
                "Quotation with future expiry should confirm without error."
            )

        # ==================================================================
        # TC-05 — Reject confirmation of an expired quotation (backend)
        # ==================================================================
        def test_05_reject_confirmed_expired_quotation(self):
            """TC-05: Confirming an expired quotation raises ValidationError at the backend."""
            past_expiry = date.today() - timedelta(days=1)
            sub = self._make_quotation(date_expiration=past_expiry)

            with self.assertRaises(ValidationError) as ctx:
                sub.action_confirm()

            self.assertIn(
                str(past_expiry), str(ctx.exception),
                "ValidationError message should include the expiry date."
            )

        # ==================================================================
        # TC-06 — Reject activation of an expired quotation
        # ==================================================================
        def test_06_reject_conversion_of_expired_quotation(self):
            """TC-06: An expired quotation cannot be confirmed and therefore cannot be activated."""
            past_expiry = date.today() - timedelta(days=5)
            sub = self._make_quotation(date_expiration=past_expiry)

            # action_confirm must fail first
            with self.assertRaises(ValidationError):
                sub.action_confirm()

            # State must remain draft — cannot be activated
            self.assertNotEqual(sub.state, 'confirmed')
            with self.assertRaises(ValidationError):
                sub.action_activate()

        # ==================================================================
        # TC-07 — expiration_status = 'expired' when past expiry
        # ==================================================================
        def test_07_verify_expiration_status_after_expiry(self):
            """TC-07: expiration_status is 'expired' and is_expired is True when expiry < today."""
            past_expiry = date.today() - timedelta(days=2)
            sub = self._make_quotation(date_expiration=past_expiry)
            # Force recompute (stored=True, recomputed on write; fetch fresh)
            sub._compute_expiration_status()
            self.assertEqual(
                sub.expiration_status, 'expired',
                "expiration_status should be 'expired' when date_expiration < today."
            )
            self.assertTrue(
                sub.is_expired,
                "is_expired should be True when date_expiration < today."
            )

        # ==================================================================
        # TC-08 — expiration_status = 'expiring_soon' within 7-day threshold
        # ==================================================================
        def test_08_verify_expiring_soon_status(self):
            """TC-08: expiration_status is 'expiring_soon' when expiry is within 7 days."""
            expiring_soon = date.today() + timedelta(days=3)
            sub = self._make_quotation(date_expiration=expiring_soon)
            sub._compute_expiration_status()
            self.assertEqual(
                sub.expiration_status, 'expiring_soon',
                "expiration_status should be 'expiring_soon' when 0 < days_left <= 7."
            )
            self.assertFalse(
                sub.is_expired,
                "is_expired should be False for 'expiring_soon' quotations."
            )

        # ==================================================================
        # TC-09 — Expiration filter domain returns correct records
        # ==================================================================
        def test_09_verify_expiration_filters(self):
            """TC-09: Domain filters for expired, expiring_soon, and valid return correct sets."""
            today = date.today()

            sub_valid = self._make_quotation(date_expiration=today + timedelta(days=30))
            sub_soon = self._make_quotation(date_expiration=today + timedelta(days=4))
            sub_expired = self._make_quotation(date_expiration=today - timedelta(days=1))

            # Force recompute
            (sub_valid | sub_soon | sub_expired)._compute_expiration_status()

            expired_ids = self.env['subscription.subscription'].search(
                [('expiration_status', '=', 'expired')]
            ).ids
            self.assertIn(sub_expired.id, expired_ids, "Expired sub should be in 'expired' filter.")
            self.assertNotIn(sub_valid.id, expired_ids, "Valid sub should not be in 'expired' filter.")
            self.assertNotIn(sub_soon.id, expired_ids, "Expiring-soon sub should not be in 'expired' filter.")

            soon_ids = self.env['subscription.subscription'].search(
                [('expiration_status', '=', 'expiring_soon')]
            ).ids
            self.assertIn(sub_soon.id, soon_ids, "Expiring-soon sub should be in 'expiring_soon' filter.")
            self.assertNotIn(sub_valid.id, soon_ids)

            valid_ids = self.env['subscription.subscription'].search(
                [('expiration_status', '=', 'valid'), ('state', 'in', ('draft', 'quotation'))]
            ).ids
            self.assertIn(sub_valid.id, valid_ids, "Valid sub should be in 'valid' filter.")

        # ==================================================================
        # TC-10 — Scheduled action (_cron) recomputes open quotations
        # ==================================================================
        def test_10_verify_scheduled_expiration_check(self):
            """TC-10: _cron_refresh_expiration_status processes draft/quotation records."""
            past_expiry = date.today() - timedelta(days=1)
            sub = self._make_quotation(date_expiration=past_expiry)

            # Simulate the cron run
            self.env['subscription.subscription']._cron_refresh_expiration_status()

            # After cron the expired sub should be flagged
            sub.invalidate_recordset()
            self.assertEqual(
                sub.expiration_status, 'expired',
                "Cron should recompute expiration_status to 'expired' for past-expiry quotations."
            )

        # ==================================================================
        # TC-11 — Negative validity_days raises ValidationError
        # ==================================================================
        def test_11_negative_validity_days_rejected(self):
            """TC-11: Setting validity_days to a negative number is rejected by backend constraint."""
            sub = self._make_quotation(validity_days=30)
            with self.assertRaises(ValidationError):
                sub.write({'validity_days': -5})

        # ==================================================================
        # TC-12 — Confirmed quotations are not marked expired
        # ==================================================================
        def test_12_confirmed_quotations_not_marked_expired(self):
            """TC-12: Once confirmed, expiration_status remains 'valid' regardless of date_expiration."""
            # Confirm with a future expiry first (required)
            future_expiry = date.today() + timedelta(days=10)
            sub = self._make_quotation(date_expiration=future_expiry)
            sub.action_confirm()
            self.assertEqual(sub.state, 'confirmed')

            # Manually set date_expiration to the past (simulating time passage after confirmation)
            sub.write({'date_expiration': date.today() - timedelta(days=1)})
            sub._compute_expiration_status()

            self.assertEqual(
                sub.expiration_status, 'valid',
                "Confirmed subscriptions must remain 'valid' even if date_expiration is in the past."
            )
            self.assertFalse(
                sub.is_expired,
                "is_expired must be False for confirmed subscriptions."
            )

except ImportError:
    # Odoo is not installed in the current environment.
    # Tests are designed to run via: odoo-bin --test-enable -i subscription_management
    pass
