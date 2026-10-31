# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System — Admin Dashboard API Controller

import logging
from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError, UserError

_logger = logging.getLogger(__name__)


def _require_admin():
    """Raise AccessError if the current user lacks subscription manager rights."""
    if not request.env.user.has_group('subscription_base.group_subscription_user'):
        raise AccessError(_("Admin access required."))


def _err(msg, code=400):
    return {'error': str(msg), 'code': code}


class AdminDashboardController(http.Controller):
    """JSON-RPC endpoints for the Admin Dashboard SPA."""

    # ------------------------------------------------------------------ #
    # Dashboard
    # ------------------------------------------------------------------ #

    @http.route('/admin/api/dashboard', type='json', auth='user', methods=['POST'], csrf=False)
    def dashboard(self):
        try:
            _require_admin()
            env = request.env
            Sub = env['subscription.subscription'].sudo()
            Move = env['account.move'].sudo()
            Partner = env['res.partner'].sudo()

            today = fields.Date.today()

            # Subscription counts
            sub_counts = {s: Sub.search_count([('state', '=', s)])
                          for s in ('draft', 'quotation', 'confirmed', 'active', 'paused', 'closed')}
            total_subs = sum(sub_counts.values())

            # Expiring soon: active/paused subs ending within 30 days
            from datetime import timedelta
            soon = today + timedelta(days=30)
            expiring_soon = Sub.search_count([
                ('state', 'in', ('active', 'paused')),
                ('date_subscription_end', '!=', False),
                ('date_subscription_end', '<=', soon),
                ('date_subscription_end', '>=', today),
            ])

            # Invoice stats
            inv_domain = [('move_type', '=', 'out_invoice')]
            total_inv = Move.search_count(inv_domain)
            paid_inv = Move.search_count(inv_domain + [('payment_state', '=', 'paid')])
            unpaid_inv = Move.search_count(inv_domain + [('payment_state', 'in', ('not_paid', 'partial')), ('state', '=', 'posted')])
            overdue_inv = Move.search_count(inv_domain + [
                ('payment_state', 'in', ('not_paid', 'partial')),
                ('state', '=', 'posted'),
                ('invoice_date_due', '<', today),
            ])

            # Revenue
            paid_moves = Move.search_read(inv_domain + [('payment_state', '=', 'paid')], ['amount_total'])
            total_revenue = sum(m['amount_total'] for m in paid_moves)
            outstanding_moves = Move.search_read(inv_domain + [
                ('payment_state', 'in', ('not_paid', 'partial')),
                ('state', '=', 'posted'),
            ], ['amount_residual'])
            outstanding = sum(m['amount_residual'] for m in outstanding_moves)

            # Catalog counts
            total_customers = Partner.search_count([('is_subscription_customer', '=', True)])
            total_products = env['product.product'].sudo().search_count([('is_subscription_product', '=', True)])
            total_plans = env['subscription.plan'].sudo().search_count([])

            # Monthly revenue (last 12 months) for chart
            monthly_revenue = _monthly_revenue(env)

            return {
                'customers': total_customers,
                'products': total_products,
                'plans': total_plans,
                'subscriptions': {
                    'total': total_subs,
                    'active': sub_counts.get('active', 0),
                    'paused': sub_counts.get('paused', 0),
                    'draft': sub_counts.get('draft', 0),
                    'quotation': sub_counts.get('quotation', 0),
                    'confirmed': sub_counts.get('confirmed', 0),
                    'closed': sub_counts.get('closed', 0),
                    'expiring_soon': expiring_soon,
                },
                'invoices': {
                    'total': total_inv,
                    'paid': paid_inv,
                    'unpaid': unpaid_inv,
                    'overdue': overdue_inv,
                },
                'revenue': {
                    'collected': round(total_revenue, 2),
                    'outstanding': round(outstanding, 2),
                    'monthly': monthly_revenue,
                },
            }
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Dashboard API error: %s", e)
            return _err(e)

    # ------------------------------------------------------------------ #
    # Customers
    # ------------------------------------------------------------------ #

    @http.route('/admin/api/customers', type='json', auth='user', methods=['POST'], csrf=False)
    def customers(self, search='', limit=50, offset=0):
        try:
            _require_admin()
            domain = [('is_subscription_customer', '=', True)]
            if search:
                domain += ['|', ('name', 'ilike', search), ('email', 'ilike', search)]
            records = request.env['res.partner'].sudo().search_read(
                domain,
                ['id', 'name', 'email', 'company_name', 'phone', 'active'],
                limit=limit, offset=offset, order='name asc',
            )
            total = request.env['res.partner'].sudo().search_count(domain)
            Sub = request.env['subscription.subscription'].sudo()
            for r in records:
                r['subs'] = Sub.search_count([('partner_id', '=', r['id']), ('state', '=', 'active')])
                r['status'] = 'Active' if r['active'] else 'Inactive'
            return {'records': records, 'total': total}
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Customers API error: %s", e)
            return _err(e)

    @http.route('/admin/api/customer/<int:cid>', type='json', auth='user', methods=['POST'], csrf=False)
    def customer_detail(self, cid):
        try:
            _require_admin()
            env = request.env
            partner = env['res.partner'].sudo().browse(cid)
            if not partner.exists():
                return _err('Not found', 404)
            subs = env['subscription.subscription'].sudo().search_read(
                [('partner_id', '=', cid)],
                ['id', 'name', 'state', 'plan_id', 'date_subscription_end', 'next_billing_date'],
            )
            invoices = env['account.move'].sudo().search_read(
                [('partner_id', '=', cid), ('move_type', '=', 'out_invoice')],
                ['id', 'name', 'invoice_date_due', 'amount_total', 'payment_state', 'state'],
                limit=20,
            )
            return {
                'id': partner.id,
                'name': partner.name,
                'email': partner.email,
                'phone': partner.phone,
                'company': partner.company_name,
                'subscriptions': subs,
                'invoices': invoices,
            }
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Customer detail API error: %s", e)
            return _err(e)

    # ------------------------------------------------------------------ #
    # Products
    # ------------------------------------------------------------------ #

    @http.route('/admin/api/products', type='json', auth='user', methods=['POST'], csrf=False)
    def products(self, search='', limit=50, offset=0):
        try:
            _require_admin()
            domain = [('is_subscription_product', '=', True)]
            if search:
                domain += [('name', 'ilike', search)]
            records = request.env['product.product'].sudo().search_read(
                domain,
                ['id', 'name', 'type', 'list_price', 'standard_price', 'description_sale'],
                limit=limit, offset=offset, order='name asc',
            )
            total = request.env['product.product'].sudo().search_count(domain)
            for r in records:
                r['price'] = r.pop('list_price', 0)
                r['cost'] = r.pop('standard_price', 0)
                r['notes'] = r.pop('description_sale', '') or ''
            return {'records': records, 'total': total}
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Products API error: %s", e)
            return _err(e)

    # ------------------------------------------------------------------ #
    # Plans
    # ------------------------------------------------------------------ #

    @http.route('/admin/api/plans', type='json', auth='user', methods=['POST'], csrf=False)
    def plans(self, search='', limit=50, offset=0):
        try:
            _require_admin()
            domain = []
            if search:
                domain += [('name', 'ilike', search)]
            records = request.env['subscription.plan'].sudo().search_read(
                domain,
                ['id', 'name', 'billing_interval', 'billing_period', 'min_quantity',
                 'date_start', 'date_end', 'allow_pause', 'allow_early_closure',
                 'auto_closure', 'allow_renewal', 'auto_renewal', 'active'],
                limit=limit, offset=offset, order='name asc',
            )
            total = request.env['subscription.plan'].sudo().search_count(domain)
            return {'records': records, 'total': total}
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Plans API error: %s", e)
            return _err(e)

    # ------------------------------------------------------------------ #
    # Subscriptions
    # ------------------------------------------------------------------ #

    @http.route('/admin/api/subscriptions', type='json', auth='user', methods=['POST'], csrf=False)
    def subscriptions(self, search='', state='', limit=50, offset=0):
        try:
            _require_admin()
            domain = []
            if state:
                domain += [('state', '=', state)]
            if search:
                domain += ['|', ('name', 'ilike', search), ('partner_id.name', 'ilike', search)]
            records = request.env['subscription.subscription'].sudo().search_read(
                domain,
                ['id', 'name', 'subscription_ref', 'partner_id', 'plan_id', 'state',
                 'date_start', 'date_subscription_end', 'next_billing_date',
                 'amount_total', 'date_last_renewal', 'renewal_count',
                 'date_paused', 'date_auto_closed'],
                limit=limit, offset=offset, order='id desc',
            )
            total = request.env['subscription.subscription'].sudo().search_count(domain)
            return {'records': records, 'total': total}
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Subscriptions API error: %s", e)
            return _err(e)

    @http.route('/admin/api/subscription/<int:sid>', type='json', auth='user', methods=['POST'], csrf=False)
    def subscription_detail(self, sid):
        try:
            _require_admin()
            env = request.env
            sub = env['subscription.subscription'].sudo().browse(sid)
            if not sub.exists():
                return _err('Not found', 404)
            history = sub.history_ids.read(['previous_state', 'new_state', 'user_id', 'change_date', 'reason'])
            renewal_history = sub.renewal_history_ids.read(
                ['renewal_type', 'renewal_result', 'renewal_date', 'prev_subscription_end',
                 'new_subscription_end', 'user_id', 'notes'])
            lines = sub.line_ids.read(['product_id', 'quantity', 'price_unit', 'discount', 'price_subtotal'])
            invoices = env['account.move'].sudo().search_read(
                [('invoice_origin', 'ilike', sub.name or sub.subscription_ref or ''),
                 ('move_type', '=', 'out_invoice')],
                ['id', 'name', 'invoice_date_due', 'amount_total', 'payment_state', 'state'],
                limit=20,
            )
            return {
                'id': sub.id, 'name': sub.name, 'subscription_ref': sub.subscription_ref,
                'state': sub.state, 'partner': sub.partner_id.name, 'partner_id': sub.partner_id.id,
                'plan': sub.plan_id.name, 'plan_id': sub.plan_id.id,
                'date_start': str(sub.date_start) if sub.date_start else None,
                'date_end': str(sub.date_subscription_end) if sub.date_subscription_end else None,
                'next_billing': str(sub.next_billing_date) if sub.next_billing_date else None,
                'amount_total': sub.amount_total,
                'renewal_count': sub.renewal_count,
                'date_last_renewal': str(sub.date_last_renewal) if sub.date_last_renewal else None,
                'date_paused': str(sub.date_paused) if sub.date_paused else None,
                'date_auto_closed': str(sub.date_auto_closed) if sub.date_auto_closed else None,
                'lines': lines,
                'history': history,
                'renewal_history': renewal_history,
                'invoices': invoices,
            }
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Subscription detail API error: %s", e)
            return _err(e)

    # ------------------------------------------------------------------ #
    # Subscription Actions
    # ------------------------------------------------------------------ #

    @http.route('/admin/api/subscription/<int:sid>/action', type='json', auth='user', methods=['POST'], csrf=False)
    def subscription_action(self, sid, action, reason=None):
        try:
            _require_admin()
            sub = request.env['subscription.subscription'].sudo().browse(sid)
            if not sub.exists():
                return _err('Not found', 404)
            ACTION_MAP = {
                'confirm': sub.action_confirm,
                'activate': sub.action_activate,
                'pause': lambda: sub.action_pause(reason=reason),
                'resume': sub.action_resume,
                'renew': sub.action_renew,
                'close': lambda: sub.action_close(reason=reason),
                'close_early': lambda: sub.action_close_early(reason=reason),
            }
            fn = ACTION_MAP.get(action)
            if not fn:
                return _err(f"Unknown action: {action}", 400)
            fn()
            return {'ok': True, 'state': sub.state}
        except (ValidationError, UserError) as e:
            return _err(e)
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Subscription action API error: %s", e)
            return _err(e)

    # ------------------------------------------------------------------ #
    # Quotations
    # ------------------------------------------------------------------ #

    @http.route('/admin/api/quotations', type='json', auth='user', methods=['POST'], csrf=False)
    def quotations(self, search='', limit=50, offset=0):
        try:
            _require_admin()
            domain = [('state', 'in', ('draft', 'quotation', 'confirmed'))]
            if search:
                domain += ['|', ('name', 'ilike', search), ('partner_id.name', 'ilike', search)]
            records = request.env['subscription.subscription'].sudo().search_read(
                domain,
                ['id', 'name', 'partner_id', 'plan_id', 'state', 'date_quotation',
                 'date_expiration', 'expiration_status', 'is_converted', 'amount_total', 'subscription_id'],
                limit=limit, offset=offset, order='date_quotation desc',
            )
            total = request.env['subscription.subscription'].sudo().search_count(domain)
            return {'records': records, 'total': total}
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Quotations API error: %s", e)
            return _err(e)

    @http.route('/admin/api/quotation/<int:qid>/convert', type='json', auth='user', methods=['POST'], csrf=False)
    def convert_quotation(self, qid):
        try:
            _require_admin()
            quotation = request.env['subscription.subscription'].sudo().browse(qid)
            if not quotation.exists():
                return _err('Not found', 404)
            result = quotation.action_create_subscription()
            sub_id = result.id if hasattr(result, 'id') else None
            return {'ok': True, 'subscription_id': sub_id}
        except (ValidationError, UserError) as e:
            return _err(e)
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Quotation convert API error: %s", e)
            return _err(e)

    # ------------------------------------------------------------------ #
    # Invoices
    # ------------------------------------------------------------------ #

    @http.route('/admin/api/invoices', type='json', auth='user', methods=['POST'], csrf=False)
    def invoices(self, search='', state='', limit=50, offset=0):
        try:
            _require_admin()
            domain = [('move_type', '=', 'out_invoice')]
            if state == 'Overdue':
                domain += [
                    ('payment_state', 'in', ('not_paid', 'partial')),
                    ('state', '=', 'posted'),
                    ('invoice_date_due', '<', fields.Date.today()),
                ]
            elif state == 'Paid':
                domain += [('payment_state', '=', 'paid')]
            elif state == 'Draft':
                domain += [('state', '=', 'draft')]
            elif state == 'Confirmed':
                domain += [('state', '=', 'posted'), ('payment_state', 'in', ('not_paid', 'partial'))]
            elif state == 'Cancelled':
                domain += [('state', '=', 'cancel')]
            if search:
                domain += ['|', ('name', 'ilike', search), ('partner_id.name', 'ilike', search)]
            records = request.env['account.move'].sudo().search_read(
                domain,
                ['id', 'name', 'partner_id', 'invoice_origin', 'invoice_date',
                 'invoice_date_due', 'amount_total', 'amount_residual', 'payment_state', 'state'],
                limit=limit, offset=offset, order='invoice_date desc, id desc',
            )
            total = request.env['account.move'].sudo().search_count(domain)
            today = fields.Date.today()
            for r in records:
                # Normalise status for the UI
                if r['state'] == 'cancel':
                    r['ui_state'] = 'Cancelled'
                elif r['payment_state'] == 'paid':
                    r['ui_state'] = 'Paid'
                elif r['state'] == 'draft':
                    r['ui_state'] = 'Draft'
                elif r['invoice_date_due'] and r['invoice_date_due'] < today:
                    r['ui_state'] = 'Overdue'
                else:
                    r['ui_state'] = 'Confirmed'
            return {'records': records, 'total': total}
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Invoices API error: %s", e)
            return _err(e)

    @http.route('/admin/api/invoice/<int:iid>/action', type='json', auth='user', methods=['POST'], csrf=False)
    def invoice_action(self, iid, action, amount=None, method=None):
        try:
            _require_admin()
            inv = request.env['account.move'].sudo().browse(iid)
            if not inv.exists():
                return _err('Not found', 404)
            if action == 'confirm':
                if inv.state != 'draft':
                    return _err('Only draft invoices can be confirmed')
                inv.action_post()
            elif action == 'cancel':
                inv.button_cancel()
            elif action == 'pay':
                if not amount:
                    return _err('Payment amount required')
                journal = request.env['account.journal'].sudo().search(
                    [('type', 'in', ('bank', 'cash')), ('company_id', '=', inv.company_id.id)],
                    limit=1
                )
                if not journal:
                    return _err('No payment journal found')
                payment_vals = {
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': inv.partner_id.id,
                    'amount': float(amount),
                    'journal_id': journal.id,
                }
                payment = request.env['account.payment'].sudo().create(payment_vals)
                payment.action_post()
                inv.js_assign_outstanding_line(payment.line_ids.filtered(
                    lambda l: l.account_id == inv.line_ids.filtered(
                        lambda x: x.account_id.account_type == 'asset_receivable'
                    )[:1].account_id
                )[:1].id)
            return {'ok': True, 'state': inv.state, 'payment_state': inv.payment_state}
        except (ValidationError, UserError) as e:
            return _err(e)
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Invoice action API error: %s", e)
            return _err(e)

    @http.route('/admin/api/billing/run', type='json', auth='user', methods=['POST'], csrf=False)
    def run_billing(self):
        try:
            _require_admin()
            result = request.env['subscription.subscription'].sudo()._cron_generate_recurring_invoices()
            count = len(result) if hasattr(result, '__len__') else 0
            return {'ok': True, 'invoices_created': count}
        except Exception as e:
            _logger.error("Run billing API error: %s", e)
            return _err(e)

    # ------------------------------------------------------------------ #
    # Taxes
    # ------------------------------------------------------------------ #

    @http.route('/admin/api/taxes', type='json', auth='user', methods=['POST'], csrf=False)
    def taxes(self, search='', limit=50, offset=0):
        try:
            _require_admin()
            domain = [('type_tax_use', '=', 'sale')]
            if search:
                domain += [('name', 'ilike', search)]
            records = request.env['account.tax'].sudo().search_read(
                domain,
                ['id', 'name', 'amount', 'amount_type', 'active'],
                limit=limit, offset=offset, order='name asc',
            )
            total = request.env['account.tax'].sudo().search_count(domain)
            return {'records': records, 'total': total}
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Taxes API error: %s", e)
            return _err(e)

    # ------------------------------------------------------------------ #
    # Discounts
    # ------------------------------------------------------------------ #

    @http.route('/admin/api/discounts', type='json', auth='user', methods=['POST'], csrf=False)
    def discounts(self, search='', limit=50, offset=0):
        try:
            _require_admin()
            domain = []
            if search:
                domain += [('name', 'ilike', search)]
            records = request.env['subscription.discount'].sudo().search_read(
                domain,
                ['id', 'name', 'discount_type', 'discount_value', 'date_start', 'date_end', 'active'],
                limit=limit, offset=offset, order='name asc',
            )
            total = request.env['subscription.discount'].sudo().search_count(domain)
            return {'records': records, 'total': total}
        except AccessError as e:
            return _err(e, 403)
        except Exception as e:
            _logger.error("Discounts API error: %s", e)
            # Return empty on model-not-found (discount model may differ)
            return {'records': [], 'total': 0}


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _monthly_revenue(env):
    """Return last 12 months of collected revenue as a list of {month, amount} dicts."""
    from datetime import date
    from dateutil.relativedelta import relativedelta
    result = []
    today = date.today()
    Move = env['account.move'].sudo()
    for i in range(11, -1, -1):
        month_start = (today.replace(day=1) - relativedelta(months=i))
        month_end = month_start + relativedelta(months=1) - relativedelta(days=1)
        moves = Move.search_read([
            ('move_type', '=', 'out_invoice'),
            ('payment_state', '=', 'paid'),
            ('invoice_date', '>=', month_start),
            ('invoice_date', '<=', month_end),
        ], ['amount_total'])
        result.append({
            'month': month_start.strftime('%b %Y'),
            'amount': round(sum(m['amount_total'] for m in moves), 2),
        })
    return result
