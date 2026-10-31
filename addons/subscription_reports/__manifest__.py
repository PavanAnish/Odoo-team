# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Subscription Reports & Analytics',
    'version': '17.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Revenue analytics, MRR, churn rate, and financial dashboard reports',
    'description': """
Subscription Reports (Reporting Module)
=======================================
Provides multidimensional financial reporting, subscription pivot views,
cohort graphs, and revenue analytics for management dashboards.
    """,
    'author': 'Hackathon Team',
    'website': 'https://github.com/PavanAnish',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'subscription_base',
        'subscription_management',
        'subscription_billing',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/subscription_report_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
