# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Subscription Authentication & Customers',
    'version': '17.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Customer management, portal access, role-based authentication, and unique email enforcement',
    'description': """
Subscription Authentication & Customers (Module 1 — Epic 1)
===========================================================
Manages customer profiles, portal self-service access, and user role
authentication for the Brightloop Subscription Management System.

Extends native Odoo ``res.partner`` and ``res.users`` without duplicating
customer models.

Email Uniqueness Enforcement (Epic 1 — primary deliverable)
------------------------------------------------------------
The system enforces that each email address can belong to only one account,
regardless of capitalisation (e.g. User@Example.com and user@example.com
are treated as the same address).

Four independent enforcement layers:

1. **Database level** — ``_sql_constraints`` adds a PostgreSQL
   ``UNIQUE(LOWER(login))`` index on ``res.users``.  This prevents
   duplicates even under concurrent INSERT operations.

2. **ORM level** — ``@api.constrains('login')`` on ``ResUsers`` checks
   for existing records using a case-insensitive ``=ilike`` search and
   raises ``ValidationError`` with a clear, localised message before any
   database write is attempted.

3. **Format validation** — a second ``@api.constrains`` on ``ResUsers``
   validates the email syntax and rejects malformed addresses.

4. **Portal / HTTP layer** — ``/subscription/check-email`` JSON endpoint
   lets the registration form query email availability in real time so the
   user receives immediate feedback before submitting the form.
    """,
    'author': 'Hackathon Team',
    'website': 'https://github.com/PavanAnish',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'portal',
        'subscription_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
