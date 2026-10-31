# Standardized Odoo Project Structure

This document outlines the standard repository layout, directory conventions, and module architecture for the **Odoo Subscription Management System**. All team members must adhere to this structure to ensure seamless integration, consistent code reviews, and reproducible deployments.

---

## 1. Top-Level Repository Layout

```text
subscription-management/
│
├── addons/                         # All custom Odoo modules developed for the project
│   ├── subscription_base/          # Shared foundation (root menus, groups, audit mixins)
│   ├── subscription_auth/          # Customer profiles, portal access & authentication (Module 1)
│   ├── subscription_catalog/       # Products, recurring plans, taxes & discounts (Module 2)
│   ├── subscription_management/    # Contracts, quotations & subscription lifecycle (Module 3)
│   ├── subscription_billing/       # Recurring invoicing, payments & accounting integration (Module 4)
│   ├── subscription_reports/       # Dedicated analytics, pivot analysis & financial reporting
│   └── subscription_module_template/# Standard reusable scaffold template for new features
│
├── config/                         # Odoo server configuration files
│   └── odoo.conf.example           # Version-controlled configuration template (no secrets)
│
├── docs/                           # Architecture, guidelines, and integration documentation
│   ├── PROJECT_STRUCTURE.md        # Comprehensive folder hierarchy & component layout
│   ├── DEVELOPMENT_GUIDELINES.md   # Coding standards, naming conventions, ACL & Git rules
│   └── MODULE_DEPENDENCIES.md      # Dependency graph, DAG hierarchy, and native model mappings
│
├── scripts/                        # Automation, validation, and developer tooling
│   ├── setup_dev.sh                # Virtual environment & configuration setup script
│   ├── validate_modules.py         # Syntax, manifest, and dependency cycle validator
│   └── run_tests.sh                # Test runner and validation pipeline script
│
├── .gitignore                      # Git exclusion rules for Python, Odoo filestore, logs, & IDEs
├── README.md                       # Main project overview, objectives, setup, and workflow
└── requirements.txt                # Python runtime dependencies & quality toolchain
```

---

## 2. Standardized Odoo Module Anatomy

Every module located inside `addons/` follows the standard Odoo 16.0 / 17.0 / 18.0 multi-tier directory structure. When creating or extending any module, maintain this exact layout:

```text
<module_technical_name>/
│
├── __init__.py                     # Package entry point importing models, controllers, wizard
├── __manifest__.py                 # Odoo module metadata descriptor
│
├── models/                         # Business ORM models (models.Model, models.AbstractModel)
│   ├── __init__.py                 # Imports all model definition files
│   └── <model_name>.py             # Model declarations, fields, constraints, methods
│
├── views/                          # XML view definitions
│   ├── <model_name>_views.xml      # Tree, form, search, kanban, and calendar views
│   └── <module>_menus.xml          # Action windows and menu item hierarchies
│
├── security/                       # Access control lists and record-level rules
│   ├── security_groups.xml         # Module categories and res.groups definitions
│   ├── security_rules.xml          # Record rules (ir.rule) for multi-company & user isolation
│   └── ir.model.access.csv         # Table permissions (read, write, create, unlink)
│
├── controllers/                    # Web and REST/JSON HTTP controllers
│   ├── __init__.py
│   └── main.py                     # Public or portal web routes and API handlers
│
├── wizard/                         # Transient models (models.TransientModel)
│   ├── __init__.py
│   ├── <wizard_name>.py            # Wizard business logic and transient fields
│   └── <wizard_name>_views.xml     # Wizard modal dialog forms and action triggers
│
├── report/                         # QWeb PDF and Excel report definitions
│   └── <model_name>_report.xml     # ir.actions.report and QWeb document templates
│
├── data/                           # Master data, ir.sequence, ir.cron scheduled actions
│   └── <module>_data.xml           # System data loaded with noupdate="1"
│
├── demo/                           # Demonstration and seed data for development
│   └── <module>_demo.xml           # Sample records loaded when demo data is enabled
│
└── tests/                          # Automated unit and integration test suites
    ├── __init__.py
    └── test_<feature>.py           # TransactionCase and HttpCase implementations
```

---

## 3. Directory and Component Responsibilities

### `addons/`
Contains the business logic decoupled across discrete, modular boundaries:
- **`subscription_base`**: Shared core containing the top-level application menu, system-wide configuration settings (`res.config.settings`), shared abstract mixins (`subscription.audit.mixin`), and global user groups (`User`, `Administrator`).
- **`subscription_auth`**: Extends customer data (`res.partner`) and authentication (`res.users`), handling customer portal self-service access and role-based permissions.
- **`subscription_catalog`**: Defines recurring subscription plans (`subscription.plan`), product extensions (`product.template`), pricing intervals, and leverages native Odoo tax engines.
- **`subscription_management`**: The subscription engine managing contracts (`subscription.subscription`), contract lines, quotation workflows, lifecycle state machines, and activation transitions.
- **`subscription_billing`**: The billing bridge connecting subscriptions with native financial models (`account.move`, `account.payment`). Implements automated invoice generation via scheduled actions (`ir.cron`).
- **`subscription_reports`**: Provides analytical reporting, SQL materialized views (`subscription.report`), pivot tables, and dashboard summaries.
- **`subscription_module_template`**: A clean, operational scaffold that developers can copy to start any new feature or module.

### `config/`
Houses configuration templates for the Odoo server.
- `odoo.conf.example`: Master template containing documented parameters (ports, addons_path, database settings, log levels, concurrency limits). Developers duplicate this file to `config/odoo.conf`, which is automatically ignored by Git.

### `docs/`
Authoritative documentation for team collaboration:
- `PROJECT_STRUCTURE.md`: Architectural map and file responsibilities (this file).
- `DEVELOPMENT_GUIDELINES.md`: Coding standards, naming conventions, security policies, and review rules.
- `MODULE_DEPENDENCIES.md`: Dependency hierarchy, DAG flowcharts, and native Odoo integration contracts.

### `scripts/`
Developer utilities to enforce code quality and automate routine setups:
- `validate_modules.py`: Automated validator for AST syntax, manifest syntax, XML well-formedness, CSV column checks, and cyclic dependency prevention.
- `setup_dev.sh`: Quick bootstrap script for Python virtual environment, dependencies, and configuration setup.
- `run_tests.sh`: Validation pipeline running static checks and triggering test cases.

---

## 4. Reusable Module Template Workflow

When starting a new feature or sub-module:
1. Copy `addons/subscription_module_template` into `addons/<new_module_name>`.
2. Update `__manifest__.py`:
   - Set technical and display names.
   - Specify accurate dependencies in `'depends'`.
   - Update file listings in `'data'` and `'demo'`.
3. Rename models in `models/` following the `subscription.<feature>` naming convention.
4. Update `security/ir.model.access.csv` to match new model IDs.
5. Run `python3 scripts/validate_modules.py` to confirm syntax and dependency integrity.
