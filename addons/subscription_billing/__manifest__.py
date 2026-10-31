# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Subscription Billing (Invoices & Payments)',
    'version': '17.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Recurring invoice generation, payment tracking, and accounting integration',
    'description': """
Subscription Billing (Module 4)
===============================
Extends Odoo native `account.move` and `account.payment` to handle automated
recurring invoice generation from active subscriptions, payment matching, and balance tracking.
    """,
    'author': 'Hackathon Team',
    'website': 'https://github.com/PavanAnish',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'subscription_base',
        'subscription_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/account_move_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
