import { D, S, M, B, ds, dO, toast, modal, X, confirmD, currentUser, logInvoiceHistory } from '../shared/store.js';

export function invs() {
  if (S.inv) {
    const selectedInv = D.invoices.find(i => i.id === S.inv);
    if (selectedInv) return invD(selectedInv);
  }
  const T = ['All', 'Draft', 'Confirmed', 'Paid', 'Cancelled', 'Overdue'];
  const rows = D.invoices.filter(i => {
    if (S.tab === 'All') return true;
    if (S.tab === 'Overdue') return ds(i) === 'Overdue';
    if (S.tab === 'Confirmed') return ds(i) === 'Confirmed';
    return i.st === S.tab;
  });

  return [
    `<button class="btn" onclick="runBilling()">+ Run billing (New Draft)</button>`,
    `<div class="tabs">${T.map(t => `<button class="${S.tab === t ? 'on' : ''}" onclick="S.tab='${t}';R()">${t}</button>`).join('')}</div>${rows.length ? `<div class="card tp tw rt"><table><thead><tr><th>Invoice</th><th>Customer</th><th>Amount</th><th>Due</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows.map(i => `<tr class="r ${ds(i) === 'Overdue' ? 'ov' : ''}" onclick="S.inv=${i.id};R()"><td data-l="Invoice"><b>${i.n}</b> <small class="mut">auto</small></td><td data-l="Customer">${i.c}</td><td data-l="Amount">${M(i.amt)}</td><td data-l="Due">${i.due}${ds(i) === 'Overdue' ? ` <b class="dn">${dO(i)}d overdue</b>` : ''}</td><td data-l="Status">${B(ds(i))}</td><td style="white-space:nowrap">${
      i.st === 'Draft' ? `<button class="btn o" onclick="event.stopPropagation();confirmInvoice(${i.id})">Confirm</button>` :
      (i.st === 'Confirmed' || ds(i) === 'Overdue') ? `<button class="btn o" onclick="event.stopPropagation();pay(${i.id})">Record payment</button>` :
      i.st === 'Paid' ? `<small class="mut">✓ Fully Paid</small>` :
      `<small class="mut">Cancelled</small>`
    }</td></tr>`).join('')}</tbody></table></div>` : '<div class="card empty"><b>No invoices</b>Nothing in this tab yet.</div>'}`
  ];
}

export function runBilling() {
  const nextId = Math.max(0, ...D.invoices.map(i => i.id)) + 1;
  const customers = D.customers.filter(c => c.status === 'Active');
  const cust = customers[nextId % customers.length] || { name: 'Acme Corp' };
  const newInv = {
    id: nextId,
    n: `INV-${2040 + nextId}`,
    c: cust.name,
    amt: 240,
    st: 'Draft',
    due: '2026-11-30',
    history: []
  };
  logInvoiceHistory(newInv, 'Created', null, 'Draft', 'Recurring billing run generated new Draft invoice.');
  D.invoices.push(newInv);
  toast(`Billing run complete: Draft invoice ${newInv.n} generated for ${newInv.c}`);
  if (typeof window.R === 'function') window.R();
}

export function confirmInvoice(id) {
  const i = D.invoices.find(x => x.id === id);
  if (!i) return;

  // Authorization check
  if (!currentUser.isAuthorized) {
    return toast('Access Denied: Only authorized billing staff can confirm invoices.');
  }

  // Validate state
  if (i.st !== 'Draft') {
    return toast(`Invalid status transition: Only Draft invoices can be confirmed (current: ${i.st})`);
  }

  confirmD(`Confirm invoice <b>${i.n}</b> for <b>${i.c}</b> (${M(i.amt)})?<br><small class="mut">Once confirmed, invoice is finalized and line items are locked awaiting payment.</small>`, () => {
    const prev = i.st;
    i.st = 'Confirmed';
    logInvoiceHistory(i, 'Confirmed', prev, 'Confirmed', 'Invoice finalized and awaiting payment.');
    toast(`Invoice ${i.n} confirmed successfully`);
    if (typeof window.R === 'function') window.R();
  }, 'Confirm Invoice');
}

export function cancelInvoice(id) {
  const i = D.invoices.find(x => x.id === id);
  if (!i) return;

  // Validate state
  if (i.st === 'Paid') {
    return toast('Cannot cancel a fully paid invoice. Payments must be reversed or refunded first.');
  }
  if (i.st === 'Cancelled') {
    return toast('Invoice is already cancelled.');
  }
  if (i.st !== 'Draft' && i.st !== 'Confirmed') {
    return toast(`Cancellation is not permitted for invoice in '${i.st}' status.`);
  }

  const o = modal(`
    <h3>Cancel Invoice · ${i.n}</h3>
    <p class="mut">Are you sure you want to cancel this invoice? Cancelled invoices cannot be confirmed or paid.</p>
    <label for="c_reason">Cancellation Reason</label>
    <input id="c_reason" placeholder="e.g. Customer billing dispute or order cancellation" style="margin-bottom:16px">
    <div class="ft">
      <button class="btn o" onclick="X()">Dismiss</button>
      <button class="btn d" id="cc_btn">Confirm Cancellation</button>
    </div>
  `);

  o.querySelector('#cc_btn').onclick = () => {
    const reason = o.querySelector('#c_reason').value.trim() || 'Invoice cancelled by user';
    const prev = i.st;
    i.st = 'Cancelled';
    X();
    logInvoiceHistory(i, 'Cancelled', prev, 'Cancelled', reason);
    toast(`Invoice ${i.n} has been cancelled`);
    if (typeof window.R === 'function') window.R();
  };
}

export function pay(id) {
  const i = D.invoices.find(x => x.id === id);
  if (!i) return;

  // Status validation
  if (i.st === 'Draft') {
    return toast('Cannot record payment: Invoice is in Draft. Confirm the invoice first.');
  }
  if (i.st === 'Cancelled') {
    return toast('Cannot record payment on a cancelled invoice.');
  }
  if (i.st === 'Paid') {
    return toast('Invoice is already fully paid.');
  }

  const o = modal(`
<h2>Record payment · ${i.n}</h2>
<p class="mut">Customer: <b>${i.c}</b> · Total due: <b>${M(i.amt)}</b></p>
<label>Payment Amount</label>
<input id="pa" type="number" step="0.01" value="${i.amt}">
<label>Payment Method</label>
<select id="pm"><option>Bank transfer</option><option>Credit Card</option><option>Cash</option><option>Direct Debit</option></select>
<label>Payment Date</label>
<input id="pd" type="date" value="2026-10-31">
<label>Transaction Reference</label>
<input id="pr" placeholder="e.g. TXN-9921">
<div class="ft">
  <button class="btn o" onclick="X()">Cancel</button>
  <button class="btn" id="ok">Record payment</button>
</div>`);

  o.querySelector('#ok').onclick = () => {
    const pa = o.querySelector('#pa');
    const amount = +pa.value;
    if (!(amount > 0)) return toast('Enter a valid payment amount above zero');
    const pm = o.querySelector('#pm').value;
    const pr = o.querySelector('#pr').value.trim() || 'DIRECT';
    const prev = i.st;

    // Transition to Paid
    i.st = 'Paid';
    X();
    logInvoiceHistory(i, 'Payment Recorded', prev, 'Paid', `Full payment of ${M(amount)} recorded via ${pm} (Ref: ${pr}).`);
    toast(`${i.n} marked as Paid`);
    if (typeof window.R === 'function') window.R();
  };
}

export function sendInvoice(id) {
  const i = D.invoices.find(x => x.id === id);
  if (!i) return;

  if (i.st === 'Draft') {
    return toast('Draft invoices cannot be sent to customers. Please confirm the invoice first.');
  }
  if (i.st === 'Cancelled') {
    return toast('Cannot send a cancelled invoice.');
  }

  const cust = D.customers.find(c => c.name === i.c) || {};
  const email = cust.email || `${i.c.toLowerCase().replace(/[^a-z]/g, '')}@example.com`;

  const o = modal(`
<h3>Send Invoice · ${i.n}</h3>
<p class="mut">Send official invoice and payment link to the customer.</p>
<label for="s_email">Recipient Email</label>
<input id="s_email" type="email" value="${email}">
<label for="s_subject">Subject</label>
<input id="s_subject" value="Invoice ${i.n} from Admin Panel (${M(i.amt)})">
<label for="s_msg">Message</label>
<textarea id="s_msg" style="width:100%;height:70px;margin-bottom:16px;border:1px solid var(--b);border-radius:6px;padding:8px;font-family:inherit">Dear ${i.c},\n\nPlease find attached invoice ${i.n} for ${M(i.amt)} due on ${i.due}.\n\nThank you for your business!</textarea>
<div class="ft">
  <button class="btn o" onclick="X()">Cancel</button>
  <button class="btn" id="s_send">Send Invoice</button>
</div>`);

  o.querySelector('#s_send').onclick = () => {
    const recipient = o.querySelector('#s_email').value.trim();
    if (!recipient) return toast('Please enter a recipient email');
    i.sent = true;
    X();
    logInvoiceHistory(i, 'Sent', i.st, i.st, `Invoice dispatched via email to ${recipient}.`);
    toast(`Invoice ${i.n} sent to ${recipient}`);
    if (typeof window.R === 'function') window.R();
  };
}

export function printInvoice(id) {
  const i = D.invoices.find(x => x.id === id);
  if (!i) return;
  if (i.st === 'Cancelled') {
    return toast('Cannot print a cancelled invoice.');
  }
  logInvoiceHistory(i, 'Printed', i.st, i.st, 'Invoice sent to printer.');
  toast(`Printing invoice ${i.n}...`);
  window.print();
  if (typeof window.R === 'function') window.R();
}

export function downloadInvoice(id) {
  const i = D.invoices.find(x => x.id === id);
  if (!i) return;
  if (i.st === 'Cancelled') {
    return toast('Cannot download a cancelled invoice.');
  }
  logInvoiceHistory(i, 'Downloaded', i.st, i.st, 'Invoice PDF copy downloaded.');

  // Create text/PDF simulated download blob
  const textContent = `=====================================================
INVOICE: ${i.n}
=====================================================
Customer: ${i.c}
Date: 2026-10-31
Due Date: ${i.due}
Status: ${i.st}
-----------------------------------------------------
Subscription Base Amount: $${(i.amt / 1.18).toFixed(2)}
Tax (18%):                $${(i.amt - i.amt / 1.18).toFixed(2)}
-----------------------------------------------------
TOTAL:                    $${Number(i.amt).toFixed(2)}
=====================================================
Generated by Odoo Subscription Management System
`;
  const blob = new Blob([textContent], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${i.n}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  toast(`Downloaded ${i.n}.pdf`);
  if (typeof window.R === 'function') window.R();
}

export function deleteInvoice(id) {
  const i = D.invoices.find(x => x.id === id);
  if (!i) return;

  if (i.st === 'Confirmed' || i.st === 'Paid') {
    return toast(`Cannot delete finalized invoice ${i.n}. Confirmed and Paid invoices are protected from deletion.`);
  }

  confirmD(`Delete draft invoice <b>${i.n}</b>? This action cannot be undone.`, () => {
    D.invoices = D.invoices.filter(x => x.id !== id);
    S.inv = null;
    toast(`Draft invoice ${i.n} deleted.`);
    if (typeof window.R === 'function') window.R();
  }, 'Delete Draft', 'd');
}

export function invD(i) {
  const isFinalized = i.st === 'Confirmed' || i.st === 'Paid';
  const isOverdue = ds(i) === 'Overdue';
  const historyList = (i.history || []).slice().reverse();

  return [
    `<button class="btn o np" onclick="S.inv=null;R()">← All invoices</button>`,
    `<div class="card" style="max-width:760px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <h2>Invoice ${i.n}</h2>
      <p class="mut" style="margin:4px 0 0">Customer: <b>${i.c}</b> · Due: <b>${i.due}</b>${isOverdue ? ` · <b class="dn">${dO(i)} days overdue</b>` : ''}</p>
    </div>
    <div>${B(ds(i))}</div>
  </div>

  ${i.st === 'Draft' ? `
    <div style="background:#f1f5f9;border-left:3px solid #64748b;padding:8px 12px;margin:14px 0;border-radius:4px">
      <small style="color:#334155"><b>Status: Draft.</b> Invoice has been generated but not yet confirmed. Financial details may be modified or confirmed by authorized staff.</small>
    </div>
  ` : i.st === 'Confirmed' ? `
    <div style="background:#eff6ff;border-left:3px solid #3b82f6;padding:8px 12px;margin:14px 0;border-radius:4px">
      <small style="color:#1d4ed8"><b>Status: Confirmed.</b> Invoice is finalized and awaiting payment. Financial figures and customer assignment are locked.</small>
    </div>
  ` : i.st === 'Paid' ? `
    <div style="background:#ecfdf5;border-left:3px solid #10b981;padding:8px 12px;margin:14px 0;border-radius:4px">
      <small style="color:#047857"><b>Status: Fully Paid.</b> Invoice is completely settled and finalized. No modifications or status changes allowed.</small>
    </div>
  ` : `
    <div style="background:#fef2f2;border-left:3px solid #ef4444;padding:8px 12px;margin:14px 0;border-radius:4px">
      <small style="color:#b91c1c"><b>Status: Cancelled.</b> This invoice was voided/cancelled and cannot be processed or paid.</small>
    </div>
  `}

  <table style="margin-top:12px">
    <thead>
      <tr><th>Item Description</th><th style="text-align:right">Amount</th></tr>
    </thead>
    <tbody>
      <tr><td>Subscription Recurring Service</td><td style="text-align:right">${M((i.amt / 1.18).toFixed(2))}</td></tr>
      <tr><td>Applicable Tax (18%)</td><td style="text-align:right">${M((i.amt - i.amt / 1.18).toFixed(2))}</td></tr>
      <tr style="font-weight:bold;border-top:2px solid var(--b)"><td>Total Payable</td><td style="text-align:right"><b>${M(i.amt)}</b></td></tr>
    </tbody>
  </table>

  <!-- Action Toolbar with Strict Lifecycle Permission Guards -->
  <div class="tb np" style="margin-top:20px;padding-top:16px;border-top:1px solid var(--b)">
    ${i.st === 'Draft' ? `
      <button class="btn" onclick="confirmInvoice(${i.id})">✓ Confirm invoice</button>
      <button class="btn o" onclick="cancelInvoice(${i.id})">Cancel invoice</button>
      <button class="btn o" onclick="downloadInvoice(${i.id})">Download PDF</button>
      <button class="btn o" onclick="printInvoice(${i.id})">Print</button>
      <button class="btn o d" onclick="deleteInvoice(${i.id})">Delete Draft</button>
    ` : (i.st === 'Confirmed' || isOverdue) ? `
      <button class="btn" onclick="pay(${i.id})">Record payment</button>
      <button class="btn o" onclick="sendInvoice(${i.id})">Send by email</button>
      <button class="btn o" onclick="downloadInvoice(${i.id})">Download PDF</button>
      <button class="btn o" onclick="printInvoice(${i.id})">Print</button>
      <button class="btn o d" onclick="cancelInvoice(${i.id})">Cancel invoice</button>
    ` : i.st === 'Paid' ? `
      <button class="btn o" onclick="sendInvoice(${i.id})">Send receipt</button>
      <button class="btn o" onclick="downloadInvoice(${i.id})">Download PDF</button>
      <button class="btn o" onclick="printInvoice(${i.id})">Print</button>
      <span class="mut" style="font-size:12px;margin-left:8px">Protected finalized record</span>
    ` : `
      <button class="btn o" disabled style="opacity:0.6;cursor:not-allowed">Actions Disabled (Cancelled)</button>
    `}
  </div>
</div>

<!-- Invoice Lifecycle History Section -->
<div class="card" style="max-width:760px;margin-top:16px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <h3 style="margin:0">Invoice Lifecycle History</h3>
    <small class="mut">${historyList.length} event(s) recorded</small>
  </div>

  ${historyList.length ? `
    <div style="overflow-x:auto">
      <table style="width:100%;font-size:13px">
        <thead>
          <tr>
            <th style="width:140px">Timestamp</th>
            <th style="width:120px">Actor</th>
            <th style="width:130px">Action</th>
            <th style="width:150px">Status Transition</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          ${historyList.map(h => `
            <tr>
              <td class="mut" style="white-space:nowrap">${h.t}</td>
              <td><b>${h.a}</b></td>
              <td><span class="bd ${h.act === 'Confirmed' ? 'g' : h.act === 'Payment Recorded' ? 'g' : h.act === 'Cancelled' ? 'r' : 's'}">${h.act}</span></td>
              <td><small>${h.from ? `<span class="mut">${h.from}</span> &rarr; ` : ''}<b>${h.to}</b></small></td>
              <td class="mut">${h.d || '—'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  ` : '<p class="mut">No lifecycle history recorded for this invoice.</p>'}
</div>`
  ];
}
