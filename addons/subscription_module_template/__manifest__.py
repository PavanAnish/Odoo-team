# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Subscription Module Template',
    'version': '17.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Reusable standard scaffold and template for Subscription Management modules',
    'description': """
Subscription Module Template
============================
Standardized architecture blueprint and boilerplate for developers creating new
features in the Subscription Management System.

Features included in this template:
-----------------------------------
* Consistent folder structure (models, views, controllers, security, data, demo, wizard, report, tests).
* Minimal example model with standard Odoo fields and chatter integration.
* Standard security access rights and user group definitions.
* Standardized XML IDs and menu structures.
* Minimal unit test suite covering CRUD operations.
    """,
    'author': 'Hackathon Team',
    'website': 'https://github.com/PavanAnish',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        # Security definitions must always be loaded first
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        # Data files
        'data/template_data.xml',
        # Views & Menus
        'views/template_model_views.xml',
        'views/template_menus.xml',
        # Wizards and Reports
        'wizard/template_wizard_views.xml',
        'report/template_report.xml',
    ],
    'demo': [
        'demo/template_demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
