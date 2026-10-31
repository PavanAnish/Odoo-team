import { D, M, B, ds, modal, X, form, toast, crud } from '../shared/store.js';

export function cust(id) {
  const c = D.customers.find(x => x.id === id);
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
