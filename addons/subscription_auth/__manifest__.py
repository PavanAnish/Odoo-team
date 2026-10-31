# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Subscription Authentication & Customers',
    'version': '17.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Customer management, portal access, and role-based authentication',
    'description': """
Subscription Authentication & Customers (Module 1)
===================================================
Manages customer profiles, portal self-service access, and user role authentication.
Extends native Odoo `res.partner` and `res.users` without duplicating customer models.
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
