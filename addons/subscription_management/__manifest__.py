# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Subscription Management (Quotations & Subscriptions)',
    'version': '17.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Quotation workflows, recurring contract lifecycle, and subscription orders',
    'description': """
Subscription Management (Module 3)
==================================
Manages quotation creation, product and variant selection, pricing engine,
tax calculations, discount application, and quotation lifecycle:
(Draft -> Quotation Sent -> Confirmed -> Active Subscription).
    """,
    'author': 'Hackathon Team',
    'website': 'https://github.com/PavanAnish',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'account',
        'subscription_base',
        'subscription_auth',
        'subscription_catalog',
    ],
    'data': [
        'security/security_rules.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/ir_cron_renewal.xml',
        'data/ir_cron_expiration.xml',
        'views/subscription_views.xml',
    ],
    'demo': [
        'demo/subscription_demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
