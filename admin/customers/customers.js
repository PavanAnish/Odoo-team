import { D, M, B, ds, modal, X, form, toast, crud } from '../shared/store.js';
import { fetchCustomer } from '../shared/api.js';

export async function cust(id) {
  // Try to fetch real data from backend
  try {
    const r = await fetchCustomer(id);
    if (r && !r.error) {
      const subs = r.subscriptions || [];
      const invs = r.invoices || [];
      modal(`
<h2>${r.name}</h2>
<p class="mut">${r.email || ''} · ${r.company || ''}</p>
<p style="margin:12px 0">${B(r.active ? 'Active' : 'Inactive')} Lifetime value <b>${M(r.ltv || 0)}</b></p>
<h3>Subscriptions</h3>
${subs.map(s => `<p>${s.name} ${B(s.state)} ${M(s.amount_total)}</p>`).join('') || '<p class="mut">None</p>'}
<h3 style="margin-top:12px">Invoices</h3>
${invs.map(s => `<p>${s.name} ${B(s.state)} ${M(s.amount_total)}</p>`).join('') || '<p class="mut">None</p>'}
<div class="ft">
  <button class="btn o" onclick="X();form('customers',${id})">Edit</button>
  <button class="btn" onclick="toast('Portal invite sent to ${(r.email || '').replace(/'/g, "\\'")}');X()">${r.portal_access ? 'Resend' : 'Send'} portal invite</button>
</div>`, 1);
      return;
    }
  } catch (e) {
    // fall through to mock
  }

  // Fallback: use local D object
  const c = D.customers.find(x => x.id === id);
  if (!c) return toast('Customer not found');
  modal(`
<h2>${c.name}</h2>
<p class="mut">${c.email} · ${c.company}</p>
<p style="margin:12px 0">${B(c.status)} Lifetime value <b>${M(c.ltv)}</b></p>
<h3>Subscriptions</h3>
${D.subs.filter(s => s.c === c.name).map(s => `<p>${s.n} ${B(s.st)} ${M(s.amt)}</p>`).join('') || '<p class="mut">None</p>'}
<h3 style="margin-top:12px">Invoices</h3>
${D.invoices.filter(s => s.c === c.name).map(s => `<p>${s.n} ${B(ds(s))} ${M(s.amt)}</p>`).join('') || '<p class="mut">None</p>'}
<div class="ft">
  <button class="btn o" onclick="X();form('customers',${id})">Edit</button>
  <button class="btn" onclick="toast('Portal invite sent to ${c.email}');X()">${c.portal ? 'Resend' : 'Send'} portal invite</button>
</div>`, 1);
}

export function customersView() {
  return crud('customers');
}
