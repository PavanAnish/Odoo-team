# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Subscription Catalog (Products, Plans, Taxes & Discounts)',
    'version': '17.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Subscription plans, product extensions, and pricing configuration',
    'description': """
Subscription Catalog (Module 2)
===============================
Configures subscription recurring plans, pricing intervals, product catalog
extensions, and leverages Odoo native tax and discount engines.
    """,
    'author': 'Hackathon Team',
    'website': 'https://github.com/PavanAnish',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'subscription_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/subscription_plan_views.xml',
        'views/product_template_views.xml',
    ],
    'demo': [
        'demo/catalog_demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
