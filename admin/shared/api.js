/**
 * api.js — Odoo JSON-RPC client for the Admin Dashboard SPA.
 *
 * All functions return Promises. On network or server error they
 * resolve to { error: string } so callers can detect failure without
 * catching exceptions.
 *
 * Odoo JSON-RPC 2.0 format:
 *   POST /web/dataset/call_kw  (model method calls)
 *   POST /admin/api/<endpoint> (our custom controller routes)
 */

const HEADERS = { 'Content-Type': 'application/json' };

async function rpc(url, params = {}) {
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: HEADERS,
      credentials: 'include',
      body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params }),
    });
    const json = await res.json();
    if (json.error) return { error: json.error.data?.message || json.error.message || 'Server error' };
    return json.result;
  } catch (e) {
    return { error: e.message || 'Network error' };
  }
}

// ── Dashboard ──────────────────────────────────────────────────────────
export const fetchDashboard = () => rpc('/admin/api/dashboard');

// ── Customers ──────────────────────────────────────────────────────────
export const fetchCustomers = (search = '', limit = 50, offset = 0) =>
  rpc('/admin/api/customers', { search, limit, offset });

export const fetchCustomer = (cid) =>
  rpc(`/admin/api/customer/${cid}`);

// ── Products ───────────────────────────────────────────────────────────
export const fetchProducts = (search = '', limit = 50, offset = 0) =>
  rpc('/admin/api/products', { search, limit, offset });

// ── Plans ──────────────────────────────────────────────────────────────
export const fetchPlans = (search = '', limit = 50, offset = 0) =>
  rpc('/admin/api/plans', { search, limit, offset });

// ── Subscriptions ──────────────────────────────────────────────────────
export const fetchSubscriptions = (search = '', state = '', limit = 50, offset = 0) =>
  rpc('/admin/api/subscriptions', { search, state, limit, offset });

export const fetchSubscription = (sid) =>
  rpc(`/admin/api/subscription/${sid}`);

export const subscriptionAction = (sid, action, reason = null) =>
  rpc(`/admin/api/subscription/${sid}/action`, { action, reason });

// ── Quotations ─────────────────────────────────────────────────────────
export const fetchQuotations = (search = '', limit = 50, offset = 0) =>
  rpc('/admin/api/quotations', { search, limit, offset });

export const convertQuotation = (qid) =>
  rpc(`/admin/api/quotation/${qid}/convert`);

// ── Invoices ───────────────────────────────────────────────────────────
export const fetchInvoices = (search = '', state = '', limit = 50, offset = 0) =>
  rpc('/admin/api/invoices', { search, state, limit, offset });

export const invoiceAction = (iid, action, amount = null, method = null, extra = {}) =>
  rpc(`/admin/api/invoice/${iid}/action`, { action, amount, method, ...extra });

export const getInvoicePdfUrl = (iid) => `/admin/api/invoice/${iid}/pdf`;

export const runBilling = () => rpc('/admin/api/billing/run');

// ── Taxes ──────────────────────────────────────────────────────────────
export const fetchTaxes = (search = '', limit = 50, offset = 0) =>
  rpc('/admin/api/taxes', { search, limit, offset });

// ── Discounts ──────────────────────────────────────────────────────────
export const fetchDiscounts = (search = '', limit = 50, offset = 0) =>
  rpc('/admin/api/discounts', { search, limit, offset });
