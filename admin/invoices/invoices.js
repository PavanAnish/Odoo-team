import { D, S, M, B, ds, dO, toast, modal, X } from '../shared/store.js';

export function invs() {
  if (S.inv) {
    const selectedInv = D.invoices.find(i => i.id === S.inv);
    if (selectedInv) return invD(selectedInv);
  }
  const T = ['All', 'Draft', 'Confirmed', 'Paid', 'Overdue'];
  const rows = D.invoices.filter(i => S.tab === 'All' || ds(i) === S.tab);

  return [
    `<button class="btn" onclick="toast('Billing run complete: 2 draft invoices generated')">Run billing</button>`,
    `<div class="tabs">${T.map(t => `<button class="${S.tab === t ? 'on' : ''}" onclick="S.tab='${t}';R()">${t}</button>`).join('')}</div>${rows.length ? `<div class="card tp tw rt"><table><thead><tr><th>Invoice</th><th>Customer</th><th>Amount</th><th>Due</th><th>Status</th><th></th></tr></thead><tbody>${rows.map(i => `<tr class="r ${ds(i) === 'Overdue' ? 'ov' : ''}" onclick="S.inv=${i.id};R()"><td data-l="Invoice">${i.n} <small class="mut">auto</small></td><td data-l="Customer">${i.c}</td><td data-l="Amount">${M(i.amt)}</td><td data-l="Due">${i.due}${ds(i) === 'Overdue' ? ` <b class="dn">${dO(i)}d overdue</b>` : ''}</td><td data-l="Status">${B(ds(i))}</td><td>${i.st === 'Confirmed' ? `<button class="btn o" onclick="event.stopPropagation();pay(${i.id})">Record payment</button>` : ''}</td></tr>`).join('')}</tbody></table></div>` : '<div class="card empty"><b>No invoices</b>Nothing in this tab yet.</div>'}`
  ];
}

export function pay(id) {
  const i = D.invoices.find(x => x.id === id);
  const o = modal(`
<h2>Record payment · ${i.n}</h2>
<label>Amount</label>
<input id="pa" type="number" value="${i.amt}">
<label>Method</label>
<select><option>Card</option><option>Bank transfer</option><option>Cash</option></select>
<label>Date</label>
<input type="date" value="2026-10-31">
<label>Reference</label>
<input placeholder="e.g. TXN-9921">
<div class="ft">
  <button class="btn o" onclick="X()">Cancel</button>
  <button class="btn" id="ok">Record payment</button>
</div>`);

  o.querySelector('#ok').onclick = () => {
    const pa = o.querySelector('#pa');
    if (!(+pa.value > 0)) return toast('Enter an amount above zero');
    i.st = 'Paid';
    X();
    toast(i.n + ' marked as Paid');
    if (typeof window.R === 'function') window.R();
  };
}

export function invD(i) {
  return [
    `<button class="btn o np" onclick="S.inv=null;R()">← All invoices</button>`,
    `<div class="card" style="max-width:720px">
  <div style="display:flex;justify-content:space-between">
    <h2>Admin Panel<br><small class="mut">Invoice ${i.n}</small></h2>
    ${B(ds(i))}
  </div>
  <p style="margin:16px 0">Billed to <b>${i.c}</b><br>Due ${i.due}${ds(i) === 'Overdue' ? ` · <b class="dn">${dO(i)} days overdue</b>` : ''}</p>
  <table>
    <tr><td>Subscription charge</td><td>${M((i.amt / 1.18).toFixed(2))}</td></tr>
    <tr><td>Tax (18%)</td><td>${M((i.amt - i.amt / 1.18).toFixed(2))}</td></tr>
    <tr><td><b>Total</b></td><td><b>${M(i.amt)}</b></td></tr>
  </table>
  <div class="tb np" style="margin-top:16px">
    ${i.st === 'Draft' ? `<button class="btn" onclick="D.invoices.find(x=>x.id===${i.id}).st='Confirmed';toast('Invoice confirmed');R()">Confirm invoice</button>` : ''}
    ${i.st === 'Confirmed' ? `<button class="btn" onclick="pay(${i.id})">Record payment</button>` : ''}
    <button class="btn o" onclick="toast('Invoice PDF downloaded (mock)')">Download PDF</button>
    <button class="btn o" onclick="print()">Print</button>
  </div>
</div>`
  ];
}
