# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Subscription Base (Shared Foundation)',
    'version': '17.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Shared foundation, core security groups, menus, and mixins for Subscription Management',
    'description': """
Subscription Base Module
========================
This module serves as the foundational dependency for the entire Subscription Management System.
It provides:
* Central security user groups (Portal, User, Manager/Admin).
* Top-level root menus and shared action definitions.
* Reusable abstract mixins for audit trails, lifecycle tracking, and currency formatting.
* Centralized system parameters and configuration settings.
    """,
    'author': 'Hackathon Team',
    'website': 'https://github.com/PavanAnish',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/subscription_base_menus.xml',
        'views/res_config_settings_views.xml',
    ],
    'demo': [
        'demo/base_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
