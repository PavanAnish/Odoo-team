# Subscription Management System - Development Guidelines

These development guidelines establish standard engineering practices, naming conventions, security policies, and Git workflows for the **Odoo Subscription Management System**. All team members must adhere strictly to these rules.

---

## 1. Python & Odoo Model Naming Conventions

### 1.1 Python Code Formatting
- Follow **PEP 8** standard for all Python files.
- Max line length: **120 characters**.
- Indentation: **4 spaces** (never use tabs).
- File encoding declaration: `# -*- coding: utf-8 -*-` at the first line of all Python files.
- Imports ordering:
  1. Standard library imports (e.g., `os`, `sys`, `logging`, `dateutil`)
  2. Third-party imports (e.g., `requests`, `pytz`)
  3. Odoo core imports: `from odoo import api, fields, models, _`
  4. Odoo exceptions: `from odoo.exceptions import UserError, ValidationError, AccessError`
  5. Module relative imports: `from . import <submodule>`

### 1.2 Model Technical Names
- Models use dot notation in lowercase: `<module_prefix>.<business_concept>`
- All project-specific models must start with `subscription.`
  - Core contract: `subscription.subscription`
  - Contract lines: `subscription.subscription.line`
  - Recurring plans: `subscription.plan`
  - Template items: `subscription.template.item`
  - Reporting SQL views: `subscription.report`
  - Wizards: `subscription.<action>.wizard` (e.g., `subscription.template.wizard`)
- Extended native Odoo models preserve their native `_inherit` names (e.g., `res.partner`, `product.template`, `account.move`).

### 1.3 Python Class Names
- Use **PascalCase** for Python classes matching the model dot notation:
  - `subscription.subscription` -> `class SubscriptionSubscription(models.Model):`
  - `subscription.plan` -> `class SubscriptionPlan(models.Model):`
  - `subscription.template.wizard` -> `class SubscriptionTemplateWizard(models.TransientModel):`

---

## 2. Database Field Naming Conventions

- Fields use **snake_case** in lowercase.
- Relational fields:
  - `Many2one`: Suffix with `_id` (e.g., `partner_id`, `plan_id`, `company_id`, `subscription_id`).
  - `One2many` / `Many2many`: Suffix with `_ids` (e.g., `line_ids`, `invoice_ids`, `user_ids`).
- Boolean fields: Prefix with `is_` or `has_` where applicable (e.g., `is_subscription_customer`, `is_subscription_product`, `has_trial`).
- State fields: Must be named `state` using `fields.Selection` with lowercase values.
- Monetary fields: Always specify `currency_field` (or default to `currency_id`).
- Date & Datetime: Prefix with `date_` (e.g., `date_start`, `date_end`, `next_billing_date`).
- Mandatory attributes:
  - Always provide `string` for user-facing labels.
  - Provide `help` tooltips on business-critical fields.
  - Set `tracking=True` on fields that require audit logging in the chatter.

---

## 3. XML View & Menu Naming Conventions

### 3.1 XML Record IDs
- Views: `view_<model_name_with_underscores>_<view_type>`
  - Examples:
    - `view_subscription_subscription_tree`
    - `view_subscription_subscription_form`
    - `view_subscription_subscription_search`
    - `view_subscription_plan_kanban`
- Inherited Views: `<original_view_id>_inherit_<module_name>`
  - Example: `view_partner_form_inherit_subscription`
- Action Windows: `action_<model_name_with_underscores>`
  - Example: `action_subscription_subscriptions`
- Menuitems: `menu_<descriptive_hierarchy>`
  - Root menu: `menu_subscription_root`
  - Section menus: `menu_subscription_operations`, `menu_subscription_catalog_menu`
  - Action menus: `menu_subscription_all_contracts`, `menu_subscription_customers`

### 3.2 View Design Standards
- Include a search view with default filters and group-by options for all primary business models.
- Forms must feature standard headers, statusbars, buttons, sheets, and chatters (`oe_chatter`).
- Multi-company: Company fields must use `groups="base.group_multi_company"`.

---

## 4. Manifest Configuration Standards

Every `__manifest__.py` file must be a valid Python dictionary containing:
```python
{
    'name': 'Subscription <Subsystem Name>',
    'version': '17.0.1.0.0', # Format: <odoo_version>.<major>.<minor>.<patch>
    'category': 'Sales/Subscriptions',
    'summary': 'Short single-line description',
    'description': """Multi-line detailed functional description...""",
    'author': 'Hackathon Team',
    'website': 'https://github.com/PavanAnish',
    'license': 'LGPL-3',
    'depends': ['base', 'subscription_base', ...],
    'data': [
        'security/security_groups.xml',
        'security/security_rules.xml',
        'security/ir.model.access.csv',
        'data/...',
        'views/...',
        'wizard/...',
        'report/...',
    ],
    'demo': ['demo/...'],
    'installable': True,
    'application': False, # True only for root app module
    'auto_install': False,
}
```
- **Order of data loading:** Always load security groups and ACLs before loading views that reference them.

---

## 5. Security, Access Controls & Record Rules

### 5.1 User Roles and Group Hierarchy
1. **Portal User (`base.group_portal`)**: Customers accessing their own account and subscriptions via the web portal.
2. **Subscription User (`subscription_base.group_subscription_user`)**: Internal staff handling day-to-day operations (read, create, edit subscriptions and quotations).
3. **Subscription Administrator (`subscription_base.group_subscription_manager`)**: Managers and admins with full configuration, deletion, and financial reporting privileges.

### 5.2 Access Control Lists (`ir.model.access.csv`)
- Every new model must have an explicit entry in `ir.model.access.csv`.
- Normal users must **never** be granted `perm_unlink=1` (deletion) on primary operational records. Only managers may unlink records.
- All column headers must follow: `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink`.

### 5.3 Record Rules (`ir.rule`)
- **Multi-Company Isolation:** Every business model containing `company_id` must have a record rule:
  ```xml
  ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
  ```
- **Customer Portal Scoping:** Customers must only access their own records:
  ```xml
  [('partner_id', '=', user.partner_id.id)]
  ```
- Never rely on hiding UI elements in frontend templates to enforce authorization. Always enforce constraints in Python models and `ir.rule`.

---

## 6. Error Handling & Validation

- Use **`ValidationError`** for data constraint violations and state progression validation:
  ```python
  if record.state != 'draft':
      raise ValidationError(_("Only draft records can be confirmed."))
  ```
- Use **`UserError`** for user workflow mistakes or missing prerequisite actions:
  ```python
  if not self.line_ids:
      raise UserError(_("Cannot confirm a subscription without line items."))
  ```
- Use **`AccessError`** when unauthorized actions are attempted programmatically.
- Always wrap user-facing error messages in translation helpers `_("...")`.
- Do not let unhandled Python exceptions crash execution; catch expected I/O or network failures gracefully.

---

## 7. Automated Testing Expectations

- Each module must include an automated test suite located in `tests/`.
- Test classes must inherit from `odoo.tests.common.TransactionCase` (or `HttpCase` for controller testing).
- Mark test classes with the `@tagged('post_install', '-at_install')` decorator.
- Test suites must cover:
  1. Default field computations and constraints.
  2. Lifecycle state machine transitions.
  3. Positive and negative validation cases (e.g., verifying `ValidationError` on illegal state changes).
  4. Multi-company and access-right isolation.

---

## 8. Git Branching, Commits & Code Review Standards

### 8.1 Branching Strategy
- Main branch: `main` (stable, deployable code).
- Feature / Epic branches:
  - `epic-1-auth`: Authentication & Customers
  - `epic-2-catalog`: Products, Plans, Taxes & Discounts
  - `epic-3-management`: Quotations & Subscriptions
  - `epic-4-billing`: Invoices, Payments & Reports
  - `feature/<module>-<short-description>`

### 8.2 Commit Message Format
Follow the Conventional Commits specification:
```text
<type>(<scope>): <short imperative summary>

[optional body explaining WHY this change was made]

[optional footer referencing issue or PR number]
```
- Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
- Examples:
  - `feat(catalog): add billing intervals to subscription plans`
  - `fix(billing): prevent duplicate invoice generation on retry`
  - `test(management): add unit tests for quotation confirmation`

### 8.3 Pull Request & Code Review Checklist
Before any pull request is merged into `main`:
1. [ ] Code follows PEP 8 and Odoo naming conventions.
2. [ ] `python3 scripts/validate_modules.py` passes with zero errors.
3. [ ] All XML IDs and menus are uniquely namespaced.
4. [ ] Security access rights (`ir.model.access.csv`) are defined for all new models.
5. [ ] Automated test cases are written and pass.
6. [ ] No native Odoo models are duplicated.
7. [ ] PR is reviewed and approved by at least one other team member.
