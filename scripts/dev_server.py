#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Subscription Management — Complete Dev & Integration Server
-----------------------------------------------------------
Serves the Admin SPA and provides a full simulated Odoo JSON-RPC backend.
Run from project root:  python3 scripts/dev_server.py [port]
Default port: 8069
"""

import json
import logging
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_DIR = os.path.join(BASE_DIR, 'admin')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('dev_server')

MIME = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'application/javascript; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.json': 'application/json',
    '.svg':  'image/svg+xml',
    '.png':  'image/png',
    '.ico':  'image/x-icon',
    '.woff2':'font/woff2',
    '.woff': 'font/woff',
    '.ttf':  'font/ttf',
}

# ── In-memory DB (simulates Odoo records) ────────────────────────────────────
DB = {
    'customers': [
        {'id':1,'name':'Northwind Co.','email':'ava@northwind.io','company_name':'Northwind','subs':2,'status':'Active','portal':True},
        {'id':2,'name':'Lumen Labs','email':'jo@lumen.dev','company_name':'Lumen Labs','subs':2,'status':'Active','portal':True},
        {'id':3,'name':'Harbor & Pine','email':'tess@harborpine.com','company_name':'Harbor & Pine','subs':1,'status':'Active','portal':False},
        {'id':4,'name':'Kite Studio','email':'sam@kite.studio','company_name':'Kite Studio','subs':0,'status':'Inactive','portal':True},
        {'id':5,'name':'Orbit Foods','email':'li@orbitfoods.co','company_name':'Orbit Foods','subs':2,'status':'Active','portal':False},
    ],
    'plans': [
        {'id':1,'name':'Pro Yearly','billing_period':'Yearly','min_quantity':5,'date_start':'2026-01-01','date_end':'2027-12-31','allow_pause':True,'allow_renewal':True,'auto_closure':45,'auto_renewal':True},
        {'id':2,'name':'Starter Monthly','billing_period':'Monthly','min_quantity':1,'date_start':'2026-01-01','date_end':'2026-12-31','allow_pause':True,'allow_renewal':True,'auto_closure':30,'auto_renewal':True},
        {'id':3,'name':'Team Weekly','billing_period':'Weekly','min_quantity':2,'date_start':'2026-06-01','date_end':'2026-12-31','allow_pause':False,'allow_renewal':True,'auto_closure':14,'auto_renewal':False},
    ],
    'products': [
        {'id':1,'name':'Recurra Pro Seat','type':'service','type_label':'Service','price':29,'cost':9,'notes':'Per-seat license','active':True,'sku':'SKU-RPS-01','variant_count':2,'variants':[{'a':'Brand: Odoo','x':0,'attribute_name':'Brand: Odoo','price_extra':0},{'a':'Brand: Zoho','x':4,'attribute_name':'Brand: Zoho','price_extra':4}]},
        {'id':2,'name':'Onboarding Package','type':'service','type_label':'Service','price':400,'cost':150,'notes':'One-time setup','active':True,'sku':'SKU-OB-02','variant_count':0,'variants':[]},
        {'id':3,'name':'Priority Support','type':'service','type_label':'Service','price':99,'cost':35,'notes':'24h response','active':True,'sku':'SKU-PS-03','variant_count':0,'variants':[]},
        {'id':4,'name':'Analytics Add-on','type':'consu','type_label':'Consumable','price':49,'cost':12,'notes':'Dashboards','active':True,'sku':'SKU-AA-04','variant_count':0,'variants':[]},
    ],
    'subscriptions': [
        {'id':1,'subscription_ref':'SUB-1001','name':'SUB-1001','partner_id':[1,'Northwind Co.'],'plan_id':[1,'Pro Yearly'],'state':'active','amount_total':2400,'next_billing_date':'2026-11-15','date_subscription_end':'2027-01-15','date_start':'2026-01-15'},
        {'id':2,'subscription_ref':'SUB-1002','name':'SUB-1002','partner_id':[2,'Lumen Labs'],'plan_id':[2,'Starter Monthly'],'state':'active','amount_total':240,'next_billing_date':'2026-11-04','date_subscription_end':'2026-12-04','date_start':'2026-01-04'},
        {'id':3,'subscription_ref':'SUB-1003','name':'SUB-1003','partner_id':[3,'Harbor & Pine'],'plan_id':[3,'Team Weekly'],'state':'confirmed','amount_total':98,'next_billing_date':'2026-11-07','date_subscription_end':'2026-12-07','date_start':'2026-10-07'},
        {'id':4,'subscription_ref':'SUB-1004','name':'SUB-1004','partner_id':[5,'Orbit Foods'],'plan_id':[2,'Starter Monthly'],'state':'quotation','amount_total':145,'next_billing_date':'2026-11-20','date_subscription_end':'2026-12-20','date_start':'2026-10-20'},
        {'id':5,'subscription_ref':'SUB-1005','name':'SUB-1005','partner_id':[4,'Kite Studio'],'plan_id':[2,'Starter Monthly'],'state':'draft','amount_total':60,'next_billing_date':'2026-12-01','date_subscription_end':'2026-12-31','date_start':'2026-11-01'},
        {'id':6,'subscription_ref':'SUB-1006','name':'SUB-1006','partner_id':[5,'Orbit Foods'],'plan_id':[1,'Pro Yearly'],'state':'closed','amount_total':1800,'next_billing_date':'','date_subscription_end':'2026-09-01','date_start':'2025-09-01'},
        {'id':7,'subscription_ref':'SUB-1007','name':'SUB-1007','partner_id':[1,'Northwind Co.'],'plan_id':[2,'Starter Monthly'],'state':'active','amount_total':240,'next_billing_date':'2026-11-15','date_subscription_end':'2026-12-15','date_start':'2026-03-15'},
        {'id':8,'subscription_ref':'SUB-1008','name':'SUB-1008','partner_id':[2,'Lumen Labs'],'plan_id':[3,'Team Weekly'],'state':'paused','amount_total':98,'next_billing_date':'','date_subscription_end':'2026-12-01','date_start':'2026-06-01'},
    ],
    'quotations': [
        {'id':101,'name':'QUO-301','partner_id':[2,'Lumen Labs'],'plan_id':[1,'Pro Yearly'],'state':'quotation','amount_total':2832,'date_expiration':'2026-11-30','expiration_status':'valid','is_converted':False,'subscription_id':None,'product':'Recurra Pro Seat','qty':5,'disc':10,'tax':18},
        {'id':102,'name':'QUO-302','partner_id':[4,'Kite Studio'],'plan_id':[2,'Starter Monthly'],'state':'draft','amount_total':400,'date_expiration':'2026-11-05','expiration_status':'expiring_soon','is_converted':False,'subscription_id':None,'product':'Onboarding Package','qty':1,'disc':0,'tax':18},
    ],
    'invoices': [
        {'id':1,'name':'INV-2041','partner_id':[1,'Northwind Co.'],'amount_total':2832,'amount_residual':0,'payment_state':'paid','state':'posted','ui_state':'Paid','invoice_date_due':'2026-10-05'},
        {'id':2,'name':'INV-2042','partner_id':[2,'Lumen Labs'],'amount_total':283,'amount_residual':283,'payment_state':'not_paid','state':'posted','ui_state':'Confirmed','invoice_date_due':'2026-11-05'},
        {'id':3,'name':'INV-2043','partner_id':[3,'Harbor & Pine'],'amount_total':116,'amount_residual':66,'payment_state':'partial','state':'posted','ui_state':'Confirmed','invoice_date_due':'2026-10-22'},
        {'id':4,'name':'INV-2044','partner_id':[5,'Orbit Foods'],'amount_total':171,'amount_residual':171,'payment_state':'not_paid','state':'posted','ui_state':'Confirmed','invoice_date_due':'2026-10-12'},
        {'id':5,'name':'INV-2045','partner_id':[4,'Kite Studio'],'amount_total':71,'amount_residual':71,'payment_state':'not_paid','state':'draft','ui_state':'Draft','invoice_date_due':'2026-11-30'},
        {'id':6,'name':'INV-2046','partner_id':[1,'Northwind Co.'],'amount_total':2832,'amount_residual':2832,'payment_state':'not_paid','state':'draft','ui_state':'Draft','invoice_date_due':'2026-11-15'},
    ],
    'taxes': [
        {'id':1,'name':'GST','amount':18.0,'active':True,'scope':'all'},
        {'id':2,'name':'VAT Reduced','amount':7.0,'active':True,'scope':'products'},
        {'id':3,'name':'Service Levy','amount':5.0,'active':False,'scope':'subscriptions'},
    ],
    'discounts': [
        {'id':1,'name':'WELCOME10','discount_type':'percentage','value':10.0,'active':True,'min_purchase':50,'expiry':'2026-12-31','limit':100,'used':64},
        {'id':2,'name':'LOYAL50','discount_type':'fixed','value':50.0,'active':True,'min_purchase':300,'expiry':'2027-03-01','limit':40,'used':38},
        {'id':3,'name':'SPRING20','discount_type':'percentage','value':20.0,'active':False,'min_purchase':0,'expiry':'2026-05-31','limit':60,'used':60},
    ],
    'payments': [
        {'id':1,'invoice_id':1,'name':'PAY-1001','amount':2832,'method':'Bank transfer','date':'2026-10-05','ref':'TXN-4491','notes':'Full settlement via wire transfer.'},
        {'id':2,'invoice_id':3,'name':'PAY-1002','amount':50,'method':'Credit / Debit Card','date':'2026-10-15','ref':'CC-9012','notes':'Partial advance payment.'},
    ],
}


def _summary():
    """Compute financial summary from DB invoices."""
    total_paid = sum(i['amount_total'] - i.get('amount_residual', 0) for i in DB['invoices'] if i['state'] != 'cancel')
    total_outstanding = sum(i.get('amount_residual', 0) for i in DB['invoices'] if i['state'] == 'posted')
    total_overdue = sum(i.get('amount_residual', 0) for i in DB['invoices']
                       if i['state'] == 'posted' and i.get('invoice_date_due', '') < '2026-10-31' and i.get('amount_residual', 0) > 0)
    return total_paid, total_outstanding, total_overdue


class Handler(BaseHTTPRequestHandler):
    server_version = 'SubMgmt-DevServer/2.0'
    log_message = lambda self, *a: None  # suppress default

    def _cors(self):
        origin = self.headers.get('Origin') or '*'
        self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Requested-With, Authorization')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Vary', 'Origin')

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        # Redirect root to admin panel
        if path in ('', '/admin'):
            path = '/admin/index.html'

        # All static files must be under /admin/
        if not path.startswith('/admin/'):
            self._json(404, {'error': 'Not found'})
            return

        file_path = os.path.normpath(os.path.join(BASE_DIR, path.lstrip('/')))
        if not file_path.startswith(BASE_DIR):
            self._json(403, {'error': 'Forbidden'})
            return

        if not os.path.isfile(file_path):
            log.warning('404 %s', path)
            self._json(404, {'error': f'File not found: {path}'})
            return

        ext = os.path.splitext(file_path)[1].lower()
        mime = MIME.get(ext, 'application/octet-stream')
        with open(file_path, 'rb') as f:
            data = f.read()

        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(data)
        log.info('GET  200 %s', path)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0) or 0)
        raw = self.rfile.read(length).decode('utf-8', errors='replace') if length else '{}'
        try:
            req = json.loads(raw)
        except Exception:
            req = {}
        params = req.get('params') or {}
        if not isinstance(params, dict):
            params = {}
        result = self._handle(path, params)
        self._json_rpc(req.get('id', 1), result)
        log.info('POST 200 %s', path)

    def _json(self, code, body):
        data = json.dumps(body, default=str).encode('utf-8')
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_rpc(self, rid, result):
        self._json(200, {'jsonrpc': '2.0', 'id': rid, 'result': result})

    # ────────────────────────────────────────────────────────────────────────
    def _handle(self, path, p):

        # ── Session stubs ────────────────────────────────────────────────────
        if path in ('/web/session/get_session_info', '/web/session/authenticate',
                    '/web/dataset/call_kw'):
            return {'uid': 1, 'name': 'Admin', 'username': 'admin',
                    'session_id': 'demo-session', 'is_admin': True}

        # ── Dashboard ────────────────────────────────────────────────────────
        if path == '/admin/api/dashboard':
            subs = DB['subscriptions']
            invs = DB['invoices']
            total_paid, total_outstanding, total_overdue = _summary()
            active = sum(1 for s in subs if s['state'] == 'active')
            paused = sum(1 for s in subs if s['state'] == 'paused')
            closed = sum(1 for s in subs if s['state'] == 'closed')
            confirmed = sum(1 for s in subs if s['state'] == 'confirmed')
            draft_q = sum(1 for s in subs if s['state'] in ('draft', 'quotation'))
            mrr = sum(s['amount_total'] for s in subs if s['state'] == 'active')
            overdue_count = sum(1 for i in invs if i['state'] == 'posted'
                                and i.get('invoice_date_due', '') < '2026-10-31'
                                and i.get('amount_residual', 0) > 0)
            return {
                'kpis': {
                    'active_subscriptions': active,
                    'mrr': mrr,
                    'arr': mrr * 12,
                    'total_revenue': total_paid,
                    'expiring_soon_count': 2,
                    'overdue_invoices_count': overdue_count,
                    'overdue_amount': total_overdue,
                    'churn_rate': 2.3,
                },
                'subscriptions': {
                    'draft': draft_q, 'quotation': len(DB['quotations']),
                    'confirmed': confirmed, 'active': active,
                    'paused': paused, 'closed': closed, 'total': len(subs)
                },
                'invoices': {
                    'total': len(invs), 'paid': 1, 'unpaid': 3, 'overdue': overdue_count
                },
                'revenue': {
                    'collected': round(total_paid, 2),
                    'outstanding': round(total_outstanding, 2),
                    'total': round(total_paid + total_outstanding, 2),
                    'monthly': [
                        {'month': 'May 2026', 'amount': 42000},
                        {'month': 'Jun 2026', 'amount': 47000},
                        {'month': 'Jul 2026', 'amount': 51000},
                        {'month': 'Aug 2026', 'amount': 49000},
                        {'month': 'Sep 2026', 'amount': 58000},
                        {'month': 'Oct 2026', 'amount': round(total_paid, 0)},
                    ]
                },
            }

        # ── Customers ────────────────────────────────────────────────────────
        if path == '/admin/api/customers':
            search = (p.get('search') or '').lower()
            rows = [c for c in DB['customers']
                    if not search or search in c['name'].lower() or search in c['email'].lower()]
            # Enrich with computed ltv
            for c in rows:
                c['ltv'] = sum(i['amount_total'] - i.get('amount_residual', 0)
                               for i in DB['invoices'] if i['partner_id'][0] == c['id'])
                c['subs'] = sum(1 for s in DB['subscriptions'] if s['partner_id'][0] == c['id'])
            return {'records': rows, 'total': len(rows)}

        if path.startswith('/admin/api/customer/'):
            try:
                cid = int(path.split('/')[-1])
            except ValueError:
                return {'error': 'Invalid id'}
            c = next((x for x in DB['customers'] if x['id'] == cid), None)
            if not c:
                return {'error': 'Customer not found'}
            c_subs = [s for s in DB['subscriptions'] if s['partner_id'][0] == cid]
            c_invs = [i for i in DB['invoices'] if i['partner_id'][0] == cid]
            ltv = sum(i['amount_total'] - i.get('amount_residual', 0) for i in c_invs)
            return {**c, 'customer': c, 'ltv': ltv, 'portal_access': c.get('portal', False),
                    'subscriptions': c_subs, 'invoices': c_invs}

        # Customer write (create/update)
        if path == '/admin/api/customer/write':
            data = p.get('data', {})
            cid = data.get('id')
            if cid:
                c = next((x for x in DB['customers'] if x['id'] == cid), None)
                if c:
                    c.update({k: v for k, v in data.items() if k != 'id'})
                    return {'success': True, 'id': cid}
                return {'error': 'Not found'}
            new_id = max(c['id'] for c in DB['customers']) + 1
            new_c = {'id': new_id, 'subs': 0, 'portal': False, **data}
            DB['customers'].append(new_c)
            return {'success': True, 'id': new_id}

        # Customer delete
        if path.startswith('/admin/api/customer/') and path.endswith('/delete'):
            try:
                cid = int(path.split('/')[-2])
            except (ValueError, IndexError):
                return {'error': 'Invalid id'}
            DB['customers'] = [c for c in DB['customers'] if c['id'] != cid]
            return {'success': True}

        if path == '/admin/api/customer/toggle':
            cid = p.get('id')
            c = next((x for x in DB['customers'] if x['id'] == cid), None)
            if c:
                key = p.get('key', 'portal')
                c[key] = not c.get(key, False)
            return {'success': True}

        # ── Products ─────────────────────────────────────────────────────────
        if path == '/admin/api/products':
            search = (p.get('search') or '').lower()
            rows = [r for r in DB['products']
                    if not search or search in r['name'].lower()]
            return {'records': rows, 'total': len(rows)}

        if path == '/subscription/catalog/products/list':
            search = (p.get('search') or '').lower()
            product_type = p.get('product_type', 'all')
            active_filter = p.get('active_filter', 'active')
            rows = DB['products']
            if active_filter == 'active':
                rows = [x for x in rows if x.get('active', True)]
            elif active_filter == 'archived':
                rows = [x for x in rows if not x.get('active', True)]
            if product_type in ('service', 'consu'):
                rows = [x for x in rows if x.get('type', '').lower() == product_type]
            if search:
                rows = [x for x in rows if search in x.get('name', '').lower() or search in x.get('sku', '').lower()]
            return {
                'success': True,
                'data': {
                    'products': rows,
                    'total': len(rows),
                    'page': int(p.get('page') or 1),
                    'limit': int(p.get('limit') or 50),
                    'can_view_cost': True,
                    'can_edit': True,
                    'status': 'success'
                }
            }

        if path == '/subscription/catalog/products/get':
            pid = p.get('product_id')
            prod = next((x for x in DB['products'] if x['id'] == pid), None)
            if prod:
                return {'status': 'success', 'product': prod}
            return {'status': 'error', 'message': 'Product not found'}

        if path == '/subscription/catalog/products/create':
            name = (p.get('name') or '').strip()
            if not name:
                return {'status': 'error', 'error_type': 'validation_error', 'message': 'Product name is required.'}
            price = float(p.get('list_price') or p.get('price') or 0.0)
            cost = float(p.get('standard_price') or p.get('cost') or 0.0)
            sku = (p.get('default_code') or p.get('sku') or '').strip()
            notes = (p.get('description_sale') or p.get('notes') or '').strip()
            dtype = p.get('detailed_type') or p.get('type') or 'service'
            variants = p.get('variants') or []
            new_id = max(x['id'] for x in DB['products']) + 1 if DB['products'] else 1
            type_label = 'Service' if dtype == 'service' else ('Consumable' if dtype == 'consu' else 'Software')
            new_prod = {
                'id': new_id,
                'name': name,
                'sku': sku or f'SKU-{new_id:03d}',
                'type': dtype,
                'type_label': type_label,
                'price': price,
                'cost': cost,
                'notes': notes,
                'active': True,
                'is_subscription_product': True,
                'variant_count': len(variants),
                'variants': variants
            }
            DB['products'].append(new_prod)
            return {
                'success': True,
                'data': {
                    'message': f"Product '{name}' created successfully.",
                    'product': new_prod,
                    'status': 'success'
                }
            }

        if path == '/subscription/catalog/products/update':
            pid = p.get('product_id') or p.get('id')
            prod = next((x for x in DB['products'] if x['id'] == pid), None)
            if not prod:
                return {'status': 'error', 'error_type': 'not_found', 'message': 'Product not found'}
            if 'name' in p: prod['name'] = p['name']
            if 'list_price' in p or 'price' in p: prod['price'] = float(p.get('list_price') or p.get('price') or 0.0)
            if 'standard_price' in p or 'cost' in p: prod['cost'] = float(p.get('standard_price') or p.get('cost') or 0.0)
            if 'default_code' in p or 'sku' in p: prod['sku'] = p.get('default_code') or p.get('sku') or ''
            if 'description_sale' in p or 'notes' in p: prod['notes'] = p.get('description_sale') or p.get('notes') or ''
            if 'variants' in p:
                prod['variants'] = p['variants']
                prod['variant_count'] = len(p['variants'])
            return {
                'success': True,
                'data': {
                    'message': f"Product '{prod['name']}' updated successfully.",
                    'product': prod,
                    'status': 'success'
                }
            }

        if path == '/subscription/catalog/products/archive':
            pid = p.get('product_id')
            prod = next((x for x in DB['products'] if x['id'] == pid), None)
            if prod:
                prod['active'] = False
            return {'success': True, 'data': {'message': 'Product archived successfully.', 'status': 'success'}}

        if path == '/subscription/catalog/products/unarchive':
            pid = p.get('product_id')
            prod = next((x for x in DB['products'] if x['id'] == pid), None)
            if prod:
                prod['active'] = True
            return {'success': True, 'data': {'message': 'Product unarchived successfully.', 'status': 'success'}}

        if path == '/admin/api/product/write':
            data = p.get('data', {})
            pid = data.get('id')
            if pid:
                prod = next((x for x in DB['products'] if x['id'] == pid), None)
                if prod:
                    prod.update({k: v for k, v in data.items() if k != 'id'})
                    return {'success': True, 'id': pid}
            new_id = max(x['id'] for x in DB['products']) + 1
            DB['products'].append({'id': new_id, 'active': True, 'variants': [], **data})
            return {'success': True, 'id': new_id}

        if path.startswith('/admin/api/product/') and path.endswith('/delete'):
            try:
                pid = int(path.split('/')[-2])
            except (ValueError, IndexError):
                return {'error': 'Invalid id'}
            DB['products'] = [x for x in DB['products'] if x['id'] != pid]
            return {'success': True}

        # ── Plans ────────────────────────────────────────────────────────────
        if path == '/admin/api/plans':
            search = (p.get('search') or '').lower()
            rows = [r for r in DB['plans']
                    if not search or search in r['name'].lower()]
            return {'records': rows, 'total': len(rows)}

        if path == '/admin/api/plan/write':
            data = p.get('data', {})
            pid = data.get('id')
            if pid:
                plan = next((x for x in DB['plans'] if x['id'] == pid), None)
                if plan:
                    plan.update({k: v for k, v in data.items() if k != 'id'})
                    return {'success': True, 'id': pid}
            new_id = max(x['id'] for x in DB['plans']) + 1
            DB['plans'].append({'id': new_id, **data})
            return {'success': True, 'id': new_id}

        if path.startswith('/admin/api/plan/') and path.endswith('/delete'):
            try:
                pid = int(path.split('/')[-2])
            except (ValueError, IndexError):
                return {'error': 'Invalid id'}
            DB['plans'] = [x for x in DB['plans'] if x['id'] != pid]
            return {'success': True}

        if path == '/admin/api/plan/toggle':
            pid = p.get('id')
            plan = next((x for x in DB['plans'] if x['id'] == pid), None)
            if plan:
                key = p.get('key', 'allow_pause')
                if key == 'pause': key = 'allow_pause'
                plan[key] = not plan.get(key, False)
            return {'success': True}

        # ── Subscriptions ────────────────────────────────────────────────────
        if path == '/admin/api/subscriptions':
            search = (p.get('search') or '').lower()
            state = p.get('state', '')
            rows = DB['subscriptions']
            if state:
                rows = [s for s in rows if s['state'] == state.lower()]
            if search:
                rows = [s for s in rows
                        if search in s['name'].lower() or
                           search in s['partner_id'][1].lower()]
            return {'records': rows, 'total': len(rows)}

        if path.startswith('/admin/api/subscription/') and path.endswith('/action'):
            parts = path.split('/')
            try:
                sid = int(parts[-2])
            except (ValueError, IndexError):
                return {'error': 'Invalid id'}
            action = p.get('action', '')
            sub = next((s for s in DB['subscriptions'] if s['id'] == sid), None)
            if not sub:
                return {'error': 'Subscription not found'}
            state_map = {'confirm': 'confirmed', 'activate': 'active',
                         'pause': 'paused', 'resume': 'active', 'close': 'closed'}
            if action == 'close_early':
                sub['state'] = 'closed'
            elif action in state_map:
                sub['state'] = state_map[action]
            elif action == 'renew':
                sub['next_billing_date'] = '2027-01-01'
                sub['date_subscription_end'] = '2027-12-31'
            else:
                return {'error': f'Unknown action: {action}'}
            return {'success': True, 'subscription_id': sid, 'state': sub.get('state')}

        if path.startswith('/admin/api/subscription/'):
            try:
                sid = int(path.split('/')[-1])
            except ValueError:
                return {'error': 'Invalid id'}
            sub = next((s for s in DB['subscriptions'] if s['id'] == sid), None)
            return sub or {'error': 'Not found'}

        # ── Quotations ───────────────────────────────────────────────────────
        if path == '/admin/api/quotations':
            search = (p.get('search') or '').lower()
            rows = DB['quotations']
            if search:
                rows = [q for q in rows
                        if search in q['name'].lower() or
                           search in q['partner_id'][1].lower()]
            return {'records': rows, 'total': len(rows)}

        if path.startswith('/admin/api/quotation/') and path.endswith('/convert'):
            try:
                qid = int(path.split('/')[-2])
            except (ValueError, IndexError):
                return {'error': 'Invalid id'}
            q = next((x for x in DB['quotations'] if x['id'] == qid), None)
            if not q:
                return {'error': 'Quotation not found'}
            if q.get('is_converted'):
                return {'error': 'Already converted'}
            q['is_converted'] = True
            q['state'] = 'confirmed'
            new_id = max(s['id'] for s in DB['subscriptions']) + 1
            ref = f"SUB-{1000 + new_id}"
            new_sub = {
                'id': new_id, 'subscription_ref': ref, 'name': ref,
                'partner_id': q['partner_id'], 'plan_id': q['plan_id'],
                'state': 'confirmed', 'amount_total': q['amount_total'],
                'next_billing_date': '2026-12-01',
                'date_subscription_end': '2027-12-31', 'date_start': '2026-11-01'
            }
            DB['subscriptions'].append(new_sub)
            q['subscription_id'] = [new_id, ref]
            # Update customer sub count
            cust = next((c for c in DB['customers'] if c['id'] == q['partner_id'][0]), None)
            if cust:
                cust['subs'] = cust.get('subs', 0) + 1
            return {'success': True, 'subscription_id': new_id, 'subscription_ref': ref}

        if path == '/admin/api/quotation/write':
            data = p.get('data', {})
            qid = data.get('id')
            if qid:
                q = next((x for x in DB['quotations'] if x['id'] == qid), None)
                if q:
                    q.update({k: v for k, v in data.items() if k != 'id'})
                    return {'success': True, 'id': qid}
            new_id = max(x['id'] for x in DB['quotations']) + 1
            new_q = {
                'id': new_id, 'name': f'QUO-{300 + new_id}',
                'state': 'draft', 'is_converted': False, 'subscription_id': None,
                **data
            }
            DB['quotations'].append(new_q)
            return {'success': True, 'id': new_id}

        # ── Invoices ─────────────────────────────────────────────────────────
        if path == '/admin/api/invoices':
            search = (p.get('search') or '').lower()
            state = p.get('state', '')
            rows = DB['invoices']
            if state:
                rows = [i for i in rows if i['ui_state'].lower() == state.lower()
                        or i['state'].lower() == state.lower()]
            if search:
                rows = [i for i in rows
                        if search in i['name'].lower() or
                           search in i['partner_id'][1].lower()]
            return {'records': rows, 'total': len(rows)}

        if path.startswith('/admin/api/invoice/') and path.endswith('/action'):
            try:
                iid = int(path.split('/')[-2])
            except (ValueError, IndexError):
                return {'error': 'Invalid id'}
            action = p.get('action', '')
            inv = next((i for i in DB['invoices'] if i['id'] == iid), None)
            if not inv:
                return {'error': 'Invoice not found'}
            if action == 'confirm':
                if inv['state'] != 'draft':
                    return {'error': 'Only draft invoices can be confirmed'}
                inv['state'] = 'posted'
                inv['ui_state'] = 'Confirmed'
            elif action == 'cancel':
                inv['state'] = 'cancel'
                inv['ui_state'] = 'Cancelled'
                inv['amount_residual'] = 0
            elif action == 'pay':
                amt = float(p.get('amount') or inv.get('amount_residual', 0))
                if amt <= 0:
                    return {'error': 'Payment amount must be positive'}
                inv['amount_residual'] = max(0.0, inv.get('amount_residual', 0) - amt)
                pay_id = max(x['id'] for x in DB['payments']) + 1
                DB['payments'].append({
                    'id': pay_id, 'invoice_id': iid,
                    'name': f'PAY-{1000 + pay_id}', 'amount': amt,
                    'method': p.get('method', 'Bank transfer'),
                    'date': '2026-10-31', 'ref': p.get('ref', ''), 'notes': ''
                })
                if inv['amount_residual'] == 0:
                    inv['payment_state'] = 'paid'
                    inv['ui_state'] = 'Paid'
                else:
                    inv['payment_state'] = 'partial'
            else:
                return {'error': f'Unknown action: {action}'}
            return {'success': True, 'invoice_id': iid, 'state': inv['state']}

        # ── Billing run ──────────────────────────────────────────────────────
        if path == '/admin/api/billing/run':
            # Generate invoices for active subscriptions without recent draft invoice
            created = []
            for sub in DB['subscriptions']:
                if sub['state'] not in ('active',):
                    continue
                new_id = max(i['id'] for i in DB['invoices']) + 1
                new_inv = {
                    'id': new_id,
                    'name': f'INV-{2040 + new_id}',
                    'partner_id': sub['partner_id'],
                    'amount_total': sub['amount_total'],
                    'amount_residual': sub['amount_total'],
                    'payment_state': 'not_paid',
                    'state': 'draft', 'ui_state': 'Draft',
                    'invoice_date_due': sub.get('next_billing_date', '2026-11-30')
                }
                DB['invoices'].append(new_inv)
                created.append(new_id)
                # Only create one for demo
                break
            return {'success': True, 'invoices_created': len(created), 'invoice_ids': created}

        # ── Taxes ────────────────────────────────────────────────────────────
        if path == '/admin/api/taxes':
            return {'records': DB['taxes'], 'total': len(DB['taxes'])}

        if path == '/admin/api/tax/write':
            data = p.get('data', {})
            tid = data.get('id')
            if tid:
                t = next((x for x in DB['taxes'] if x['id'] == tid), None)
                if t:
                    t.update({k: v for k, v in data.items() if k != 'id'})
                    return {'success': True, 'id': tid}
            new_id = max(x['id'] for x in DB['taxes']) + 1
            DB['taxes'].append({'id': new_id, **data})
            return {'success': True, 'id': new_id}

        if path.startswith('/admin/api/tax/') and path.endswith('/delete'):
            try:
                tid = int(path.split('/')[-2])
            except (ValueError, IndexError):
                return {'error': 'Invalid id'}
            DB['taxes'] = [x for x in DB['taxes'] if x['id'] != tid]
            return {'success': True}

        if path == '/admin/api/tax/toggle':
            tid = p.get('id')
            t = next((x for x in DB['taxes'] if x['id'] == tid), None)
            if t:
                t['active'] = not t['active']
            return {'success': True}

        # ── Discounts ────────────────────────────────────────────────────────
        if path == '/admin/api/discounts':
            return {'records': DB['discounts'], 'total': len(DB['discounts'])}

        if path == '/admin/api/discount/write':
            data = p.get('data', {})
            did = data.get('id')
            if did:
                d = next((x for x in DB['discounts'] if x['id'] == did), None)
                if d:
                    d.update({k: v for k, v in data.items() if k != 'id'})
                    return {'success': True, 'id': did}
            new_id = max(x['id'] for x in DB['discounts']) + 1
            DB['discounts'].append({'id': new_id, 'used': 0, **data})
            return {'success': True, 'id': new_id}

        if path.startswith('/admin/api/discount/') and path.endswith('/delete'):
            try:
                did = int(path.split('/')[-2])
            except (ValueError, IndexError):
                return {'error': 'Invalid id'}
            DB['discounts'] = [x for x in DB['discounts'] if x['id'] != did]
            return {'success': True}

        if path == '/admin/api/discount/toggle':
            did = p.get('id')
            d = next((x for x in DB['discounts'] if x['id'] == did), None)
            if d:
                d['active'] = not d['active']
            return {'success': True}

        # ── Generic write/delete fallback ────────────────────────────────────
        if path == '/admin/api/write':
            model = p.get('model', '')
            data = p.get('data', {})
            key = model  # e.g. 'customers', 'plans'
            if key not in DB:
                return {'error': f'Unknown model: {model}'}
            rid = data.get('id')
            if rid:
                r = next((x for x in DB[key] if x['id'] == rid), None)
                if r:
                    r.update({k: v for k, v in data.items() if k != 'id'})
                    return {'success': True, 'id': rid}
            new_id = max(x['id'] for x in DB[key]) + 1 if DB[key] else 1
            DB[key].append({'id': new_id, **data})
            return {'success': True, 'id': new_id}

        if path == '/admin/api/delete':
            model = p.get('model', '')
            rid = p.get('id')
            if model in DB:
                DB[model] = [x for x in DB[model] if x['id'] != rid]
            return {'success': True}

        log.warning('Unhandled POST %s', path)
        return {'error': f'Endpoint not found: {path}'}


def main():
    port = 8069
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    server = HTTPServer(('0.0.0.0', port), Handler)
    log.info('=' * 62)
    log.info('  Subscription Management System — Dev & Integration Server')
    log.info('  Admin Panel → http://localhost:%d/admin/index.html', port)
    log.info('  API Base   → http://localhost:%d/admin/api/', port)
    log.info('  Press Ctrl+C to stop')
    log.info('=' * 62)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info('Server stopped.')
        server.server_close()


if __name__ == '__main__':
    main()
