export const $ = s => document.querySelector(s);
export const M = n => '$' + Number(n).toLocaleString();
export const TODAY = new Date('2026-10-31');

export const BC = {
  Active: 'g', Paid: 'g', Confirmed: 'g', Converted: 'g',
  Draft: 's', Quotation: 'a', Pending: 'a', Paused: 'a',
  Overdue: 'r', Closed: 's', Inactive: 's', Sent: 'a', Cancelled: 's',
  'Partially Paid': 'a', Unpaid: 's', Settled: 'g'
};

export const B = s => `<span class="bd ${BC[s] || 's'}">${s}</span>`;

export const IC = {
  Dashboard: "M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z",
  Customers: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  Products: "M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8",
  Plans: "M4 6h16M4 12h16M4 18h10",
  Taxes: "M19 5L5 19M7 9a2 2 0 1 0 0-.1M17 19a2 2 0 1 0 0-.1",
  Discounts: "M20 12l-8 8-9-9V3h8zM7.5 7.5h.01",
  Quotations: "M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h5",
  Subscriptions: "M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5",
  "Invoices & Payments": "M2 6h20v12H2zM2 10h20"
};

export const NAV = Object.keys(IC);
export const slug = n => n.split(' ')[0].toLowerCase();

export const D = {
  customers: [
    ['Northwind Co.', 'ava@northwind.io', 'Northwind', 1, 3, 48200, 'Active'],
    ['Lumen Labs', 'jo@lumen.dev', 'Lumen Labs', 1, 2, 31400, 'Active'],
    ['Harbor & Pine', 'tess@harborpine.com', 'Harbor & Pine', 0, 1, 9800, 'Active'],
    ['Kite Studio', 'sam@kite.studio', 'Kite Studio', 1, 0, 4200, 'Inactive'],
    ['Orbit Foods', 'li@orbitfoods.co', 'Orbit Foods', 0, 2, 18700, 'Active']
  ].map((r, i) => ({ id: i + 1, name: r[0], email: r[1], company: r[2], portal: r[3], subs: r[4], ltv: r[5], status: r[6] })),

  products: [
    ['Recurra Pro Seat', 'Software', 29, 9, 'Per-seat license', [{ a: 'Brand: Odoo', x: 0 }, { a: 'Brand: Zoho', x: 4 }]],
    ['Onboarding Package', 'Service', 400, 150, 'One-time setup', []],
    ['Priority Support', 'Add-on', 99, 35, '24h response', []],
    ['Analytics Add-on', 'Add-on', 49, 12, 'Dashboards', []]
  ].map((r, i) => ({ id: i + 1, name: r[0], type: r[1], price: r[2], cost: r[3], notes: r[4], variants: r[5] })),

  plans: [
    ['Starter Monthly', 'Monthly', 1, '2026-01-01', '2027-12-31', 1, 1, 30, 'Recurra Pro Seat'],
    ['Pro Yearly', 'Yearly', 5, '2026-01-01', '2027-12-31', 1, 1, 45, 'Recurra Pro Seat,Priority Support'],
    ['Team Weekly', 'Weekly', 2, '2026-06-01', '2026-12-31', 0, 1, 14, 'Analytics Add-on']
  ].map((r, i) => ({ id: i + 1, name: r[0], freq: r[1], minQty: r[2], start: r[3], end: r[4], pause: r[5], renew: r[6], autoClose: r[7], products: r[8] })),

  taxes: [
    ['GST', '18', 'all', 1],
    ['VAT Reduced', '7', 'products', 1],
    ['Service Levy', '5', 'subscriptions', 0]
  ].map((r, i) => ({ id: i + 1, name: r[0], rate: +r[1], scope: r[2], on: r[3] })),

  discounts: [
    ['WELCOME10', 'percentage', 10, 50, 1, '2026-01-01', '2026-12-31', 100, 64, 'all', 1],
    ['LOYAL50', 'fixed', 50, 300, 1, '2026-03-01', '2027-03-01', 40, 38, 'Recurra Pro Seat', 1],
    ['SPRING20', 'percentage', 20, 0, 2, '2026-03-01', '2026-05-31', 60, 60, 'all', 0]
  ].map((r, i) => ({ id: i + 1, name: r[0], type: r[1], value: r[2], minPurchase: r[3], minQty: r[4], start: r[5], end: r[6], limit: r[7], used: r[8], scope: r[9], on: r[10] })),

  quotes: [
    ['QUO-301', 'Lumen Labs', 'Pro Yearly', 'Recurra Pro Seat', 5, 10, 18, 'Sent'],
    ['QUO-302', 'Kite Studio', 'Starter Monthly', 'Onboarding Package', 1, 0, 18, 'Draft']
  ].map((r, i) => ({ id: i + 1, n: r[0], customer: r[1], plan: r[2], product: r[3], qty: r[4], disc: r[5], tax: r[6], st: r[7] })),

  subs: [
    ['SUB-1001', 'Northwind Co.', 'Pro Yearly', 'Active', 2400, '2026-11-15'],
    ['SUB-1002', 'Lumen Labs', 'Starter Monthly', 'Active', 240, '2026-11-04'],
    ['SUB-1003', 'Harbor & Pine', 'Team Weekly', 'Confirmed', 98, '2026-11-07'],
    ['SUB-1004', 'Orbit Foods', 'Starter Monthly', 'Quotation', 145, '2026-11-20'],
    ['SUB-1005', 'Kite Studio', 'Starter Monthly', 'Draft', 60, '2026-12-01'],
    ['SUB-1006', 'Orbit Foods', 'Pro Yearly', 'Closed', 1800, '2026-09-01']
  ].map((r, i) => ({ id: i + 1, n: r[0], c: r[1], plan: r[2], st: r[3], amt: r[4], next: r[5], paused: 0 })),

  invoices: [
    ['INV-2041', 'Northwind Co.', 2832, 'Paid', '2026-10-05', [
      { t: '2026-10-01 09:15', a: 'System', act: 'Created', from: null, to: 'Draft', d: 'Generated from monthly billing run' },
      { t: '2026-10-02 10:30', a: 'Admin User', act: 'Confirmed', from: 'Draft', to: 'Confirmed', d: 'Invoice confirmed and locked' },
      { t: '2026-10-02 10:35', a: 'Admin User', act: 'Sent', from: 'Confirmed', to: 'Confirmed', d: 'Sent to ava@northwind.io' },
      { t: '2026-10-05 14:00', a: 'Admin User', act: 'Payment Recorded', from: 'Confirmed', to: 'Paid', d: 'Full payment of ,832 recorded via Bank transfer (Ref: TXN-4491)' }
    ]],
    ['INV-2042', 'Lumen Labs', 283, 'Confirmed', '2026-11-05', [
      { t: '2026-10-15 08:30', a: 'System', act: 'Created', from: null, to: 'Draft', d: 'Generated from monthly billing run' },
      { t: '2026-10-16 11:20', a: 'Admin User', act: 'Confirmed', from: 'Draft', to: 'Confirmed', d: 'Invoice confirmed and locked' },
      { t: '2026-10-16 11:22', a: 'Admin User', act: 'Sent', from: 'Confirmed', to: 'Confirmed', d: 'Sent to jo@lumen.dev' }
    ]],
    ['INV-2043', 'Harbor & Pine', 116, 'Confirmed', '2026-10-22', [
      { t: '2026-10-01 09:00', a: 'System', act: 'Created', from: null, to: 'Draft', d: 'Generated from weekly billing run' },
      { t: '2026-10-02 14:10', a: 'Admin User', act: 'Confirmed', from: 'Draft', to: 'Confirmed', d: 'Invoice confirmed and locked' },
      { t: '2026-10-15 11:20', a: 'Admin User', act: 'Payment Recorded', from: 'Confirmed', to: 'Confirmed', d: 'Partial payment of $50 recorded via Credit / Debit Card (Ref: CC-9012). Remaining balance: $66.00' }
    ]],
    ['INV-2044', 'Orbit Foods', 171, 'Confirmed', '2026-10-12', [
      { t: '2026-09-20 10:00', a: 'System', act: 'Created', from: null, to: 'Draft', d: 'Generated from monthly billing run' },
      { t: '2026-09-22 16:45', a: 'Admin User', act: 'Confirmed', from: 'Draft', to: 'Confirmed', d: 'Invoice confirmed and locked' }
    ]],
    ['INV-2045', 'Kite Studio', 71, 'Draft', '2026-11-30', [
      { t: '2026-10-28 11:00', a: 'System', act: 'Created', from: null, to: 'Draft', d: 'Draft invoice created' }
    ]],
    ['INV-2046', 'Northwind Co.', 2832, 'Draft', '2026-11-15', [
      { t: '2026-10-30 16:30', a: 'System', act: 'Created', from: null, to: 'Draft', d: 'Draft invoice created' }
    ]]
  ].map((r, i) => {
    const isPaid = r[3] === 'Paid';
    const total = r[2];
    const initialPaid = isPaid ? total : (i === 2 ? 50 : 0);
    return {
      id: i + 1,
      n: r[0],
      c: r[1],
      amt: total,
      paid: initialPaid,
      residual: Math.max(0, total - initialPaid),
      st: r[3],
      due: r[4],
      history: r[5] || []
    };
  }),

  payments: [
    {
      id: 1,
      invId: 1,
      n: 'PAY-1001',
      inv: 'INV-2041',
      c: 'Northwind Co.',
      amt: 2832,
      m: 'Bank transfer',
      d: '2026-10-05',
      ref: 'TXN-4491',
      notes: 'Full settlement via wire transfer.',
      user: 'Admin User'
    },
    {
      id: 2,
      invId: 3,
      n: 'PAY-1002',
      inv: 'INV-2043',
      c: 'Harbor & Pine',
      amt: 50,
      m: 'Credit / Debit Card',
      d: '2026-10-15',
      ref: 'CC-9012',
      notes: 'Partial advance payment.',
      user: 'Admin User'
    }
  ]
};

export const S = { q: {}, sort: {}, tab: 'All', view: 'table', sel: null, rev: 'Month', view2: 'table', qt: 'Quotations', inv: null };

export const ds = i => {
  if (i.st === 'Cancelled') return 'Cancelled';
  const residual = i.residual !== undefined ? i.residual : (i.st === 'Paid' ? 0 : i.amt);
  if (i.st === 'Paid' || (residual <= 0 && (i.paid || 0) > 0)) return 'Paid';
  if (i.st !== 'Draft' && residual > 0 && new Date(i.due) < TODAY) return 'Overdue';
  if (i.st === 'Confirmed' && (i.paid || 0) > 0 && residual > 0) return 'Partially Paid';
  return i.st;
};
export const dO = i => Math.floor((TODAY - new Date(i.due)) / 864e5);

export const isUnpaid = i => i.st !== 'Cancelled' && (!i.paid || i.paid === 0) && (i.residual !== undefined ? i.residual > 0 : i.amt > 0);
export const isPartial = i => i.st !== 'Cancelled' && (i.paid || 0) > 0 && (i.residual !== undefined ? i.residual > 0 : true);
export const isFullyPaid = i => i.st === 'Paid' || ((i.residual !== undefined ? i.residual === 0 : false) && (i.paid || 0) > 0);
export const isOverdue = i => ds(i) === 'Overdue';

export function getFinancialSummary(invoices = D.invoices) {
  let totalInvoiced = 0;
  let totalPaid = 0;
  let totalOutstanding = 0;
  let totalOverdue = 0;

  let countTotal = 0;
  let countDraft = 0;
  let countConfirmed = 0;
  let countPaid = 0;
  let countPartial = 0;
  let countUnpaid = 0;
  let countOverdue = 0;
  let countCancelled = 0;

  for (const i of invoices) {
    if (i.st === 'Cancelled') {
      countCancelled++;
      continue;
    }

    countTotal++;
    const total = i.amt || 0;
    const paid = i.paid !== undefined ? i.paid : (i.st === 'Paid' ? total : 0);
    const residual = i.residual !== undefined ? i.residual : (i.st === 'Paid' ? 0 : total);
    const isOd = (i.st !== 'Draft' && residual > 0 && new Date(i.due) < TODAY);

    totalInvoiced += total;
    totalPaid += paid;

    if (i.st === 'Draft') {
      countDraft++;
      totalOutstanding += residual;
      if (paid === 0) countUnpaid++;
      else countPartial++;
    } else if (i.st === 'Confirmed') {
      countConfirmed++;
      totalOutstanding += residual;
      if (isOd) {
        totalOverdue += residual;
        countOverdue++;
      }
      if (paid === 0) countUnpaid++;
      else if (residual > 0) countPartial++;
    } else if (i.st === 'Paid' || residual === 0) {
      countPaid++;
    }
  }

  return {
    totalInvoiced: Math.round(totalInvoiced * 100) / 100,
    totalPaid: Math.round(totalPaid * 100) / 100,
    totalOutstanding: Math.round(totalOutstanding * 100) / 100,
    totalOverdue: Math.round(totalOverdue * 100) / 100,
    countTotal,
    countDraft,
    countConfirmed,
    countPaid,
    countPartial,
    countUnpaid,
    countOverdue,
    countCancelled,
  };
}

export const currentUser = {
  name: 'Admin User',
  email: 'admin@odoo-team.local',
  role: 'Billing Administrator',
  isAuthorized: true
};

export function logInvoiceHistory(inv, action, fromStatus, toStatus, details = '') {
  if (!inv.history) inv.history = [];
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const tStr = now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate()) + " " + pad(now.getHours()) + ":" + pad(now.getMinutes());
  inv.history.push({
    t: tStr,
    a: currentUser.name,
    act: action,
    from: fromStatus,
    to: toStatus,
    d: details
  });
}

export function toast(m) {
  const e = document.createElement('div');
  e.className = 't';
  e.textContent = m;
  const ts = $('#ts');
  if (ts) ts.append(e);
  setTimeout(() => e.remove(), 2800);
}

export function modal(h, dr) {
  const o = document.createElement('div');
  o.className = 'ov0' + (dr ? ' dr' : '');
  o.innerHTML = `<div class="md" role="dialog" aria-modal="true">${h}</div>`;
  o.onclick = e => { if (e.target === o) o.remove(); };
  document.body.append(o);
  const f = o.querySelector('input,button');
  if (f) f.focus();
  return o;
}

export const X = () => document.querySelectorAll('.ov0').forEach(o => o.remove());

export function confirmD(m, fn, lbl = 'Confirm', cls = '') {
  const o = modal(`<h3>${m}</h3><div class="ft"><button class="btn o" onclick="X()">Cancel</button><button class="btn ${cls}" id="cy">${lbl}</button></div>`);
  o.querySelector('#cy').onclick = () => { X(); fn(); };
}

export const FD = {
  customers: [
    { k: 'name', l: 'Name', r: 1 },
    { k: 'email', l: 'Email', r: 1 },
    { k: 'company', l: 'Company' },
    { k: 'status', l: 'Status', t: 'sel', o: ['Active', 'Inactive'] },
    { k: 'portal', l: 'Portal access', t: 'tg' }
  ],
  products: [
    { k: 'name', l: 'Name', r: 1 },
    { k: 'type', l: 'Type', t: 'sel', o: ['Software', 'Service', 'Add-on'] },
    { k: 'price', l: 'Sales price', t: 'number', r: 1 },
    { k: 'cost', l: 'Cost price', t: 'number' },
    { k: 'notes', l: 'Notes' },
    { t: 'mg' },
    { k: 'variants', t: 'var' }
  ],
  plans: [
    { k: 'name', l: 'Plan name', r: 1 },
    { k: 'freq', l: 'Billing frequency', t: 'sel', o: ['Daily', 'Weekly', 'Monthly', 'Yearly'] },
    { k: 'minQty', l: 'Minimum quantity', t: 'number' },
    { k: 'start', l: 'Available from', t: 'date' },
    { k: 'end', l: 'Available until', t: 'date' },
    { k: 'products', l: 'Linked products', t: 'ms' },
    { k: 'pause', l: 'Allow pause', t: 'tg' },
    { k: 'renew', l: 'Allow renewal', t: 'tg' },
    { k: 'autoClose', l: 'Auto-close after (days unpaid)', t: 'number' },
    { t: 'life' }
  ],
  taxes: [
    { k: 'name', l: 'Tax name', r: 1 },
    { k: 'rate', l: 'Rate (%)', t: 'number', r: 1 },
    { k: 'scope', l: 'Applies to', t: 'sel', o: ['all', 'products', 'subscriptions'] },
    { k: 'on', l: 'Active', t: 'tg' }
  ],
  discounts: [
    { k: 'name', l: 'Code / name', r: 1 },
    { k: 'type', l: 'Type', t: 'sel', o: ['percentage', 'fixed'] },
    { k: 'value', l: 'Value', t: 'number', r: 1 },
    { k: 'minPurchase', l: 'Minimum purchase', t: 'number' },
    { k: 'minQty', l: 'Minimum quantity', t: 'number' },
    { k: 'start', l: 'Start date', t: 'date' },
    { k: 'end', l: 'Expiry date', t: 'date' },
    { k: 'limit', l: 'Usage limit', t: 'number' },
    { k: 'scope', l: 'Applies to', t: 'sel', o: ['all'] },
    { k: 'on', l: 'Active', t: 'tg' }
  ],
  quotes: [
    { k: 'customer', l: 'Customer', t: 'sel', o: () => D.customers.map(c => c.name) },
    { k: 'plan', l: 'Plan', t: 'sel', o: () => D.plans.map(c => c.name) },
    { k: 'product', l: 'Product', t: 'sel', o: () => D.products.map(c => c.name) },
    { k: 'qty', l: 'Quantity', t: 'number', r: 1 },
    { k: 'disc', l: 'Discount (%)', t: 'number' },
    { k: 'tax', l: 'Tax (%)', t: 'sel', o: () => D.taxes.map(c => String(c.rate)) },
    { t: 'tot' }
  ]
};

export function opts(f) {
  const o = typeof f.o === 'function' ? f.o() : f.o;
  return f.k === 'scope' ? ['all', ...D.products.map(p => p.name)] : o;
}

export function form(k, id) {
  const rec = id ? D[k].find(r => r.id === id) : {}, F = FD[k];
  const row = (v = { a: '', x: 0 }) => `<div class="vr"><input placeholder="Attribute e.g. Brand: Odoo" value="${v.a}"><input type="number" style="max-width:110px" placeholder="+ price" value="${v.x}"><button type="button" class="btn o" onclick="this.parentNode.remove()" aria-label="Remove">✕</button></div>`;
  const fh = F.map(f => {
    const v = rec[f.k] ?? (f.t === 'number' ? 0 : '');
    if (f.t === 'tg') return `<label style="display:flex;justify-content:space-between;align-items:center">${f.l}<button type="button" id="f_${f.k}" class="sw ${v ? 'on' : ''}" onclick="this.classList.toggle('on')" aria-label="${f.l}"></button></label>`;
    if (f.t === 'sel') return `<label for="f_${f.k}">${f.l}</label><select id="f_${f.k}">${opts(f).map(o => `<option ${String(o) === String(v) ? 'selected' : ''}>${o}</option>`).join('')}</select>`;
    if (f.t === 'ms') return `<label for="f_${f.k}">${f.l}</label><select id="f_${f.k}" multiple size="4">${D.products.map(p => `<option ${String(v).split(',').includes(p.name) ? 'selected' : ''}>${p.name}</option>`).join('')}</select>`;
    if (f.t === 'var') return `<label>Variants</label><div id="vs">${(v || []).map(row).join('')}</div><button type="button" class="btn o" onclick="vs.insertAdjacentHTML('beforeend',\`${row().replace(/`/g, '')}\`)">+ Add variant</button>`;
    if (f.t === 'mg') return `<div class="card aic" style="margin-top:12px">Margin: <b id="mg"></b></div>`;
    if (f.t === 'life') return `<label>Plan lifecycle</label><div class="stp"><div>Draft</div><div>Confirmed</div><div>Active</div><div>Paused</div><div>Auto-close</div></div><small class="mut">Closes automatically after <span id="lc">${rec.autoClose || 30}</span> unpaid days.</small>`;
    if (f.t === 'tot') return `<div class="card aic" style="margin-top:12px">Total: <b id="tt"></b></div>`;
    return `<label for="f_${f.k}">${f.l}</label><input id="f_${f.k}" type="${f.t || 'text'}" value="${String(v).replace(/"/g, '&quot;')}"><span class="er" id="e_${f.k}"></span>`;
  }).join('');

  const o = modal(`<h2>${id ? 'Edit' : 'New'} ${k === 'quotes' ? 'quotation' : k.slice(0, -1)}</h2>${fh}<div class="ft"><button class="btn o" onclick="X()">Discard</button><button class="btn" id="sv">Save changes</button></div>`, k === 'customers');
  const upd = () => {
    const g = n => +(o.querySelector('#f_' + n) || {}).value || 0;
    const mg = o.querySelector('#mg');
    if (mg) {
      const p = g('price'), c = g('cost');
      mg.textContent = p ? M(p - c) + ' (' + Math.round((p - c) / p * 100) + '%)' : '—';
    }
    const tt = o.querySelector('#tt');
    if (tt) {
      const p = (D.products.find(x => x.name === o.querySelector('#f_product').value) || { price: 0 }).price;
      tt.textContent = M((p * g('qty') * (1 - g('disc') / 100) * (1 + g('tax') / 100)).toFixed(2));
    }
    const lc = o.querySelector('#lc');
    if (lc) lc.textContent = g('autoClose');
  };
  o.addEventListener('input', upd);
  o.addEventListener('change', upd);
  upd();

  o.querySelector('#sv').onclick = () => {
    let ok = 1;
    const out = {};
    F.forEach(f => {
      if (!f.k) return;
      const e = o.querySelector('#f_' + f.k);
      let v;
      if (f.t === 'tg') v = e.classList.contains('on') ? 1 : 0;
      else if (f.t === 'ms') v = [...e.selectedOptions].map(x => x.value).join(',');
      else if (f.t === 'var') v = [...o.querySelectorAll('#vs .vr')].map(r => ({ a: r.children[0].value, x: +r.children[1].value || 0 })).filter(x => x.a);
      else {
        v = e.value.trim();
        if (f.t === 'number') v = +v;
        if (f.r && (v === '' || v !== v)) {
          ok = 0;
          const er = o.querySelector('#e_' + f.k);
          if (er) er.textContent = f.l + ' is required';
        }
      }
      out[f.k] = v;
    });
    if (!ok) return;
    if (k === 'quotes') { out.tax = +out.tax; out.qty = out.qty; }
    if (id) Object.assign(rec, out);
    else {
      const nx = Math.max(0, ...D[k].map(r => r.id)) + 1;
      D[k].push({
        id: nx,
        ...(k === 'quotes' ? { n: 'QUO-' + (300 + nx), st: 'Draft' } : {}),
        ...(k === 'customers' ? { subs: 0, ltv: 0 } : {}),
        ...(k === 'discounts' ? { used: 0 } : {}),
        ...out
      });
    }
    X();
    toast('Saved ' + (out.name || 'quotation'));
    if (typeof window.R === 'function') window.R();
  };
}

export function del(k, id) {
  confirmD('Delete this record? This cannot be undone.', () => {
    D[k] = D[k].filter(r => r.id !== id);
    toast('Deleted');
    if (typeof window.R === 'function') window.R();
  }, 'Delete', 'd');
}

export function tog(k, id, key) {
  const r = D[k].find(x => x.id === id);
  r[key] = r[key] ? 0 : 1;
  if (typeof window.R === 'function') window.R();
}

export const CR = {
  customers: { t: 'Customers', a: 'Add customer', c: [['Name', 'name'], ['Email', 'email'], ['Company', 'company'], ['Portal', 'portal', 't'], ['Subs', 'subs'], ['Lifetime value', 'ltv', 'm'], ['Status', 'status', 'b']] },
  products: { t: 'Products', a: 'Add product', c: [['Name', 'name'], ['Type', 'type', 'b'], ['Sales price', 'price', 'm'], ['Cost', 'cost', 'm'], ['Variants', 'variants', 'n']] },
  plans: { t: 'Plans', a: 'Create plan', c: [['Plan', 'name'], ['Billing', 'freq', 'b'], ['Min qty', 'minQty'], ['Available', 'start', 'd'], ['Products', 'products'], ['Pause', 'pause', 't']] },
  taxes: { t: 'Taxes', a: 'Add tax', c: [['Tax', 'name'], ['Rate', 'rate', '%'], ['Applies to', 'scope'], ['Status', 'on', 'o']] },
  discounts: { t: 'Discounts', a: 'Create discount', c: [['Code', 'name'], ['Type', 'type'], ['Value', 'value'], ['Min purchase', 'minPurchase', 'm'], ['Expires', 'end'], ['Usage', 'used', 'p'], ['Status', 'on', 'o']] }
};

export function cell(k, r, [l, key, t]) {
  const v = r[key];
  return t === 'm' ? M(v) :
    t === 'b' ? B(v) :
    t === '%' ? v + '%' :
    t === 'n' ? v.length :
    t === 'd' ? v + ' →' :
    t === 't' ? `<button class="sw ${v ? 'on' : ''}" aria-label="${l}" onclick="event.stopPropagation();tog('${k}',${r.id},'${key}')"></button>` :
    t === 'o' ? `<button class="sw ${v ? 'on' : ''}" aria-label="Active" onclick="event.stopPropagation();tog('${k}',${r.id},'${key}')"></button>` :
    t === 'p' ? `<div class="pb"><i style="width:${Math.min(100, v / r.limit * 100)}%"></i></div><small class="mut">${v}/${r.limit}</small>` :
    v;
}

export function crud(k) {
  const o = CR[k], q = (S.q[k] || '').toLowerCase(), s = S.sort[k];
  let rows = D[k].filter(r => JSON.stringify(r).toLowerCase().includes(q));
  if (s) rows = [...rows].sort((a, b) => (a[s.k] > b[s.k] ? 1 : -1) * s.d);
  const tbl = rows.length ?
    `<div class="card tp tw rt"><table><thead><tr>${o.c.map(c => `<th onclick="S.sort['${k}']={k:'${c[1]}',d:${s && s.k === c[1] ? -s.d : 1}};R()">${c[0]}${s && s.k === c[1] ? (s.d > 0 ? ' ↑' : ' ↓') : ''}</th>`).join('')}<th></th></tr></thead><tbody>${rows.map(r => `<tr class="r" onclick="${k === 'customers' ? `cust(${r.id})` : `form('${k}',${r.id})`}">${o.c.map(c => `<td data-l="${c[0]}">${cell(k, r, c)}</td>`).join('')}<td><button class="ib" aria-label="Delete" onclick="event.stopPropagation();del('${k}',${r.id})">🗑</button></td></tr>`).join('')}</tbody></table></div>` :
    `<div class="card empty"><b>Nothing here yet</b>Try a different search or add a new record.</div>`;
  const grid = k === 'products' && S.view === 'grid' ?
    `<div class="g g4">${rows.map(r => `<div class="card" style="cursor:pointer" onclick="form('products',${r.id})"><b>${r.name}</b><p class="mut">${r.notes}</p><div class="kv">${M(r.price)}</div>${B(r.type)} <small class="mut">margin ${Math.round((r.price - r.cost) / r.price * 100)}%</small></div>`).join('')}</div>` :
    tbl;
  return [
    `<button class="btn" onclick="form('${k}')">+ ${o.a}</button>`,
    `<div class="tb"><input placeholder="Search ${o.t.toLowerCase()}…" aria-label="Search" value="${S.q[k] || ''}" oninput="S.q['${k}']=this.value;R(1)">${k === 'products' ? `<button class="btn o" onclick="S.view=S.view==='grid'?'table':'grid';R()">${S.view === 'grid' ? 'Table' : 'Grid'} view</button>` : ''}${k === 'customers' ? `<button class="btn o" onclick="toast('Invites sent to selected customers')">Bulk invite</button>` : ''}</div><div id="tbl">${grid}</div>`
  ];
}
