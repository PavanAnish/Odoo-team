import {
  $, M, TODAY, BC, B, IC, NAV, slug, D, S, ds, dO,
  toast, modal, X, confirmD, form, del, tog, crud,
  currentUser, logInvoiceHistory
} from './shared/store.js';

import { dash } from './dashboard/dashboard.js';
import { customersView, cust } from './customers/customers.js';
import { productsView } from './products/products.js';
import { plansView } from './plans/plans.js';
import { taxesView } from './taxes/taxes.js';
import { discountsView } from './discounts/discounts.js';
import { quo, conv } from './quotations/quotations.js';
import { subs, subD } from './subscriptions/subscriptions.js';
import {
  invs, pay, invD,
  confirmInvoice, cancelInvoice, sendInvoice,
  printInvoice, downloadInvoice, deleteInvoice, runBilling,
  viewPaymentDetails
} from './invoices/invoices.js';

// Router mapping
export const P = {
  dashboard: dash,
  customers: customersView,
  products: productsView,
  plans: plansView,
  taxes: taxesView,
  discounts: discountsView,
  quotations: quo,
  subscriptions: subs,
  invoices: invs
};

let cur = 'dashboard';

export function R(keep) {
  const [a, b] = P[cur]();
  const t = NAV.find(n => slug(n) === cur);
  if (keep) {
    const match = b.match(/<div id="tbl">([\s\S]*)<\/div>$/);
    if (match) {
      const tblEl = $('#tbl');
      if (tblEl) tblEl.innerHTML = match[1];
      return;
    }
  }
  const mn = $('#mn');
  if (mn) {
    mn.innerHTML = `<div class="ph"><div><small>Admin Panel / ${t}</small><h1>${t}</h1></div><div>${a}</div></div>${b}`;
  }
  document.querySelectorAll('.cu').forEach(e => {
    const v = +e.dataset.v, t0 = performance.now(), p = e.dataset.p;
    (function f(n) {
      const k = Math.min(1, (n - t0) / 800);
      e.textContent = p + Math.round(v * (1 - Math.pow(1 - k, 3))).toLocaleString();
      if (k < 1) requestAnimationFrame(f);
    })(t0);
  });
}

export function go() {
  const hash = location.hash.slice(1);
  cur = P[hash] ? hash : 'dashboard';
  S.sel = null;
  S.inv = null;
  const appEl = $('#app');
  if (appEl) appEl.classList.remove('open');

  document.querySelectorAll('aside nav a').forEach(a => {
    a.classList.toggle('on', a.id === 'n_' + cur);
  });

  const mn = $('#mn');
  if (mn) {
    mn.innerHTML = '<div class="g g4"><div class="sk"></div><div class="sk"></div><div class="sk"></div><div class="sk"></div></div>';
  }
  setTimeout(R, 300);
}

export function ask() {
  const o = modal(`
<h3>Ask AI anything</h3>
<input id="aq" placeholder="Search pages or ask a question…" style="margin:12px 0">
${NAV.map(n => `<p><a href="#${slug(n)}" onclick="X()" style="color:var(--c);text-decoration:none;display:block;padding:6px 0">${n}</a></p>`).join('')}
<div class="ft"><button class="btn ai" id="aa">Ask</button></div>`);

  o.querySelector('#aa').onclick = () => {
    X();
    toast('3 invoices are overdue totaling ' + M(D.invoices.filter(i => ds(i) === 'Overdue').reduce((a, i) => a + i.amt, 0)));
  };
}

// Populate navigation sidebar
const nv = $('#nv');
if (nv) {
  nv.innerHTML = NAV.map(n => `<a href="#${slug(n)}" id="n_${slug(n)}"><svg class="i" viewBox="0 0 24 24"><path d="${IC[n]}"/></svg><span class="lb">${n}</span></a>`).join('');
}

// Expose on window for inline event handlers and global accessibility
window.$ = $;
window.M = M;
window.app = $('#app');
window.TODAY = TODAY;
window.BC = BC;
window.B = B;
window.IC = IC;
window.NAV = NAV;
window.slug = slug;
window.D = D;
window.S = S;
window.ds = ds;
window.dO = dO;
window.toast = toast;
window.modal = modal;
window.X = X;
window.confirmD = confirmD;
window.form = form;
window.del = del;
window.tog = tog;
window.crud = crud;
window.cust = cust;
window.conv = conv;
window.pay = pay;
window.confirmInvoice = confirmInvoice;
window.cancelInvoice = cancelInvoice;
window.sendInvoice = sendInvoice;
window.printInvoice = printInvoice;
window.downloadInvoice = downloadInvoice;
window.deleteInvoice = deleteInvoice;
window.runBilling = runBilling;
window.viewPaymentDetails = viewPaymentDetails;
window.currentUser = currentUser;
window.logInvoiceHistory = logInvoiceHistory;
window.P = P;
window.R = R;
window.go = go;
window.ask = ask;

// Event listeners
window.addEventListener('hashchange', go);
window.addEventListener('keydown', e => {
  if (e.key === 'Escape') X();
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    ask();
  }
});

// Initial boot
go();
