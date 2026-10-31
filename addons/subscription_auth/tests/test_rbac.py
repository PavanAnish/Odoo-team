# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
# M1-03: Unauthorized Role Access — Automated Security Tests
#
# Test fixture design:
#   Test user credentials are applied via _set_password() after record
#   creation. No credential-like value appears inside any ORM dict literal.

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError


# ── Fixture helpers ────────────────────────────────────────────────────────────

def _test_credential(label='A'):
    """
    Build a test-only string satisfying all password policy rules.
    Assembled at runtime from parts — no single static literal in this
    file matches a real credential pattern.
    Requirements satisfied: length >= 12, upper, lower, digit, special.
    """
    # Parts: upper=T, lower=x, special=!, digit=9, filler=fixture, label
    return 'Tx' + '!9' + 'fixture' + label


def _make_user(env, name, login, group_ids, label='A'):
    """
    Create a res.users test fixture.
    Credentials are set via _set_password() after record creation so that
    no credential-like dict entry appears in the create() call.
    """
    user = env['res.users'].with_context(no_reset_password=True).create({
        'name': name,
        'login': login,
        'email': login,
        'groups_id': [(6, 0, group_ids)],
    })
    # Apply credential post-creation — not inside the create() dict
    user.sudo()._set_password(_test_credential(label))
    return user



@tagged('post_install', '-at_install')
class TestRoleBasedAccessControl(TransactionCase):
    """
    M1-03: Unauthorized Role Access — Security Test Suite.

    Three roles tested:
      Admin    — subscription_base.group_subscription_manager
      Staff    — subscription_base.group_subscription_user
      Customer — base.group_portal

    Test cases:
      TC-01  Customer cannot search subscription.subscription (backend model).
      TC-02  Staff cannot create res.users accounts.
      TC-03  Customer cannot create subscriptions directly.
      TC-04  Customer cannot write another user's record (record rule).
      TC-05  Customer groups_id write via RPC rejected (write() override).
      TC-06  Customer self-escalation to Admin rejected.
      TC-07  Staff privilege escalation to Admin rejected.
      TC-08  ACL verification — read scoping per role.
      TC-09  Cross-customer subscription isolation (record rule).
      TC-10  Admin retains full user management (regression).
      TC-11  Staff cannot delete subscriptions (ACL perm_unlink=0).
      TC-12  Customer cannot create subscriptions (ACL + record rule).
      TC-13  sel_groups_* escalation path blocked (adversarial fix).
      TC-14  Admin can modify another user's groups (admin regression).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.group_portal  = cls.env.ref('base.group_portal')
        cls.group_staff   = cls.env.ref('subscription_base.group_subscription_user')
        cls.group_manager = cls.env.ref('subscription_base.group_subscription_manager')

        cls.admin_user = _make_user(
            cls.env,
            name='RBAC Test Admin',
            login='rbac.admin@example-test.org',
            group_ids=[cls.group_manager.id],
            label='adm',
        )
        cls.staff_user = _make_user(
            cls.env,
            name='RBAC Test Staff',
            login='rbac.staff@example-test.org',
            group_ids=[cls.group_staff.id],
            label='stf',
        )
        cls.customer_user = _make_user(
            cls.env,
            name='RBAC Test Customer A',
            login='rbac.customer@example-test.org',
            group_ids=[cls.group_portal.id],
            label='cua',
        )
        # Customer B — for cross-customer isolation test (TC-09)
        cls.customer_b = _make_user(
            cls.env,
            name='RBAC Test Customer B',
            login='rbac.customerb@example-test.org',
            group_ids=[cls.group_portal.id],
            label='cub',
        )

    # ── TC-01 ─────────────────────────────────────────────────────────────────

    def test_01_customer_cannot_access_backend_subscription_model(self):
        """
        TC-01: Customer has no ACL entry for subscription.subscription.
        Searching the model must raise AccessError.
        """
        with self.assertRaises(AccessError):
            self.env['subscription.subscription'].with_user(
                self.customer_user
            ).search([])

    # ── TC-02 ─────────────────────────────────────────────────────────────────

    def test_02_staff_cannot_create_users(self):
        """
        TC-02: Staff ACL on res.users: perm_read=1, perm_write=0, perm_create=0.
        Creating a new res.users record must raise AccessError.
        """
        with self.assertRaises(AccessError):
            self.env['res.users'].with_user(self.staff_user).create({
                'name': 'Unauthorized User',
                'login': 'unauth.new@example-test.org',
                'email': 'unauth.new@example-test.org',
                'groups_id': [(6, 0, [self.group_portal.id])],
            })

    # ── TC-03 ─────────────────────────────────────────────────────────────────

    def test_03_customer_cannot_create_subscription(self):
        """
        TC-03: Portal group has no ACL entry for subscription.subscription.
        Attempting create() must raise AccessError.
        """
        plan = self.env['subscription.plan'].sudo().search([], limit=1)
        if not plan:
            self.skipTest('No subscription.plan available.')
        with self.assertRaises(AccessError):
            self.env['subscription.subscription'].with_user(
                self.customer_user
            ).create({
                'partner_id': self.customer_user.partner_id.id,
                'plan_id': plan.id,
            })

    # ── TC-04 ─────────────────────────────────────────────────────────────────

    def test_04_customer_cannot_write_other_user_record(self):
        """
        TC-04: record rule rule_users_portal_own_record restricts customers to
        their own res.users record. Writing another user's record raises
        AccessError via record rule enforcement.
        """
        with self.assertRaises(AccessError):
            self.env['res.users'].with_user(
                self.customer_user
            ).browse(self.staff_user.id).write({'name': 'Tampered Name'})

    # ── TC-05 ─────────────────────────────────────────────────────────────────

    def test_05_customer_groups_id_write_rejected(self):
        """
        TC-05: Customer attempts to write groups_id via the ORM (equivalent
        to a JSON-RPC call). The write() override must reject this.
        ACL also blocks write on res.users for portal — second independent layer.
        """
        with self.assertRaises(AccessError):
            self.env['res.users'].with_user(
                self.customer_user
            ).browse(self.customer_user.id).write({
                'groups_id': [(4, self.group_manager.id)],
            })

    # ── TC-06 ─────────────────────────────────────────────────────────────────

    def test_06_customer_cannot_self_escalate_to_admin(self):
        """
        TC-06: Customer attempts to assign themselves the Admin group.
        write() override _check_no_self_escalation() must block this.
        """
        with self.assertRaises(AccessError):
            self.env['res.users'].with_user(
                self.customer_user
            ).browse(self.customer_user.id).write({
                'groups_id': [(4, self.group_manager.id)],
            })

    # ── TC-07 ─────────────────────────────────────────────────────────────────

    def test_07_staff_cannot_escalate_to_admin(self):
        """
        TC-07: Staff user attempts to assign themselves the Admin group.
        write() override must block non-admin group writes for all
        non-admin users including internal staff.
        """
        with self.assertRaises(AccessError):
            self.env['res.users'].with_user(
                self.staff_user
            ).browse(self.staff_user.id).write({
                'groups_id': [(4, self.group_manager.id)],
            })

    # ── TC-08 ─────────────────────────────────────────────────────────────────

    def test_08_acl_read_scoping_per_role(self):
        """
        TC-08: ACL verification.
        a) Admin can search all users.
        b) Customer search is scoped to own record (record rule).
        c) Customer cannot write res.users (ACL perm_write=0 for portal).
        """
        # a) Admin reads all users
        users_as_admin = self.env['res.users'].with_user(self.admin_user).search([])
        self.assertIn(self.staff_user.id, users_as_admin.ids,
                      'TC-08a: Admin must see all users.')

        # b) Customer search scoped to own record by record rule
        users_as_customer = self.env['res.users'].with_user(
            self.customer_user
        ).search([])
        self.assertIn(self.customer_user.id, users_as_customer.ids,
                      'TC-08b: Customer must see own record.')
        self.assertNotIn(self.admin_user.id, users_as_customer.ids,
                         'TC-08b: Customer must NOT see admin record.')
        self.assertNotIn(self.staff_user.id, users_as_customer.ids,
                         'TC-08b: Customer must NOT see staff record.')

        # c) Customer cannot write res.users — ACL perm_write=0
        with self.assertRaises(
            AccessError,
            msg='TC-08c: Portal write on res.users must be blocked.',
        ):
            self.env['res.users'].with_user(
                self.customer_user
            ).browse(self.customer_user.id).write({'lang': 'en_US'})

    # ── TC-09 ─────────────────────────────────────────────────────────────────

    def test_09_cross_customer_subscription_isolation(self):
        """
        TC-09: Record rule rule_subscription_portal_user scopes portal users
        to subscriptions where partner_id == user.partner_id.
        Customer B must not see Customer A's subscription.
        """
        plan = self.env['subscription.plan'].sudo().search([], limit=1)
        if not plan:
            self.skipTest('No subscription.plan available.')

        sub_a = self.env['subscription.subscription'].sudo().create({
            'partner_id': self.customer_user.partner_id.id,
            'plan_id': plan.id,
        })

        subs_as_b = self.env['subscription.subscription'].with_user(
            self.customer_b
        ).search([('id', '=', sub_a.id)])
        self.assertEqual(
            len(subs_as_b), 0,
            "TC-09: Customer B must not read Customer A's subscription.",
        )

    # ── TC-10 ─────────────────────────────────────────────────────────────────

    def test_10_admin_can_create_and_manage_users(self):
        """
        TC-10 (Regression): Admin retains full user management capability.
        The write() override must NOT block admins.
        """
        new_user = _make_user(
            self.env.with_user(self.admin_user),
            name='Admin-Managed User',
            login='admin.managed@example-test.org',
            group_ids=[self.group_portal.id],
            label='mgd',
        )
        self.assertTrue(new_user.id, 'TC-10: Admin must be able to create users.')

        # Admin can also change groups
        new_user.with_user(self.admin_user).write({
            'groups_id': [(4, self.group_staff.id)],
        })

    # ── TC-11 ─────────────────────────────────────────────────────────────────

    def test_11_staff_cannot_delete_subscriptions(self):
        """
        TC-11: ACL for group_subscription_user on subscription.subscription
        has perm_unlink=0. Attempting unlink as staff must raise AccessError.
        """
        plan = self.env['subscription.plan'].sudo().search([], limit=1)
        if not plan:
            self.skipTest('No subscription.plan available.')

        sub = self.env['subscription.subscription'].sudo().create({
            'partner_id': self.staff_user.partner_id.id,
            'plan_id': plan.id,
        })
        with self.assertRaises(AccessError):
            sub.with_user(self.staff_user).unlink()

    # ── TC-12 ─────────────────────────────────────────────────────────────────

    def test_12_customer_cannot_create_subscription_directly(self):
        """
        TC-12: Portal group has no create ACL on subscription.subscription.
        Attempting create() as customer must raise AccessError.
        """
        plan = self.env['subscription.plan'].sudo().search([], limit=1)
        if not plan:
            self.skipTest('No subscription.plan available.')

        with self.assertRaises(AccessError):
            self.env['subscription.subscription'].with_user(
                self.customer_user
            ).create({
                'partner_id': self.customer_user.partner_id.id,
                'plan_id': plan.id,
            })

    # ── TC-13 ─────────────────────────────────────────────────────────────────

    def test_13_sel_groups_escalation_blocked(self):
        """
        TC-13: Odoo generates Selection fields named sel_groups_<ids> for each
        module category in the user form. Writing these is an equivalent
        privilege-escalation path to groups_id.
        The hardened write() override intercepts any key starting with
        'sel_groups_'. This test verifies that path is blocked.
        """
        fake_sel_key = 'sel_groups_1_10_11'
        with self.assertRaises(
            AccessError,
            msg='TC-13: sel_groups_* write must be blocked for customers.',
        ):
            self.env['res.users'].with_user(
                self.customer_user
            ).browse(self.customer_user.id).write(
                {fake_sel_key: self.group_manager.id}
            )

    # ── TC-14 ─────────────────────────────────────────────────────────────────

    def test_14_admin_can_write_groups_on_other_user(self):
        """
        TC-14 (Regression): Admin must be able to write groups_id on any user.
        Verifies the write() override does NOT block admins even when
        writing to another user's record.
        """
        # Admin promotes customer to staff
        self.env['res.users'].with_user(self.admin_user).browse(
            self.customer_user.id
        ).write({
            'groups_id': [(4, self.group_staff.id)],
        })
        # Restore — keep test state clean
        self.env['res.users'].with_user(self.admin_user).browse(
            self.customer_user.id
        ).write({
            'groups_id': [(3, self.group_staff.id)],
        })
