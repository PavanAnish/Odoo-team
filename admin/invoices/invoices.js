import { D, S, M, B, ds, dO, toast, modal, X, confirmD, currentUser, logInvoiceHistory, loadData,
         isUnpaid, isPartial, isFullyPaid, isOverdue, getFinancialSummary } from '../shared/store.js';
import { invoiceAction, runBilling as apiBilling } from '../shared/api.js';

export function invs() {
  if (S.inv) {
    const selectedInv = D.invoices.find(i => i.id === S.inv);
    if (selectedInv) return invD(selectedInv);
  }
  const summary = getFinancialSummary(D.invoices);
  const T = ['All', 'Unpaid', 'Partially Paid', 'Overdue', 'Draft', 'Confirmed', 'Paid', 'Cancelled'];
  const rows = D.invoices.filter(i => {
    if (S.tab === 'All') return true;
    if (S.tab === 'Unpaid') return isUnpaid(i);
    if (S.tab === 'Partially Paid') return isPartial(i);
    if (S.tab === 'Overdue') return ds(i) === 'Overdue';
    if (S.tab === 'Paid') return isFullyPaid(i);
    if (S.tab === 'Confirmed') return i.st === 'Confirmed';
    if (S.tab === 'Draft') return i.st === 'Draft';
    if (S.tab === 'Cancelled') return i.st === 'Cancelled';
    return i.st === S.tab;
  });

  return [
    `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2 style="margin:0">Invoices &amp; Balances</h2>
      <button class="btn" onclick="runBilling()">+ Run billing (New Draft)</button>
    </div>
    <div class="g g4" style="margin-bottom:16px">
      <div class="card" style="padding:12px 16px">
        <span class="mut" style="font-size:12px">Total Invoiced</span>
        <div style="font-size:20px;font-weight:bold;margin-top:2px">${M(summary.totalInvoiced)}</div>
        <small class="mut">${summary.countTotal} active invoice(s)</small>
      </div>
      <div class="card" style="padding:12px 16px">
        <span class="mut" style="font-size:12px">Payments Collected</span>
        <div style="font-size:20px;font-weight:bold;color:#047857;margin-top:2px">${M(summary.totalPaid)}</div>
        <small class="mut">${summary.countPaid} settled · ${summary.countPartial} partial</small>
      </div>
      <div class="card" style="padding:12px 16px">
        <span class="mut" style="font-size:12px">Remaining Outstanding</span>
        <div style="font-size:20px;font-weight:bold;color:#b45309;margin-top:2px">${M(summary.totalOutstanding)}</div>
        <small class="mut">${summary.countUnpaid} unpaid · ${summary.countPartial} partial</small>
      </div>
      <div class="card" style="padding:12px 16px">
        <span class="mut" style="font-size:12px">Overdue Balance</span>
        <div style="font-size:20px;font-weight:bold;color:#dc2626;margin-top:2px">${M(summary.totalOverdue)}</div>
        <small class="${summary.countOverdue > 0 ? 'dn' : 'mut'}">${summary.countOverdue} invoice(s) overdue</small>
      </div>
    </div>`,
    `<div class="tabs">${T.map(t => `<button class="${S.tab === t ? 'on' : ''}" onclick="S.tab='${t}';R()">${t}</button>`).join('')}</div>${rows.length ? `<div class="card tp tw rt"><table><thead><tr><th>Invoice</th><th>Customer</th><th>Total</th><th>Paid</th><th>Due</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows.map(i => {
      const isOd = ds(i) === 'Overdue';
      const paid = i.paid || (i.st === 'Paid' ? i.amt : 0);
      const residual = (i.st === 'Cancelled') ? 0 : (i.residual !== undefined ? i.residual : (i.st === 'Paid' ? 0 : i.amt));
      return `<tr class="r ${isOd ? 'ov' : ''}" onclick="S.inv=${i.id};R()">
        <td data-l="Invoice"><b>${i.n}</b> <small class="mut">auto</small></td>
        <td data-l="Customer">${i.c}</td>
        <td data-l="Total">${M(i.amt)}</td>
        <td data-l="Paid" class="${paid > 0 ? 'mut' : 'mut'}">${M(paid)}</td>
        <td data-l="Due">${M(residual)}${isOd ? ` <b class="dn">${dO(i)}d overdue</b>` : ''}</td>
        <td data-l="Status">${B(ds(i))}</td>
        <td style="white-space:nowrap">${
          i.st === 'Draft' ? `<button class="btn o" onclick="event.stopPropagation();confirmInvoice(${i.id})">Confirm</button>` :
          (i.st === 'Confirmed' || isOd || isPartial(i)) ? `<button class="btn o" onclick="event.stopPropagation();pay(${i.id})">Record payment</button>` :
          i.st === 'Paid' ? `<small class="mut">✓ Fully Paid</small>` :
          `<small class="mut">Cancelled</small>`
        }</td>
      </tr>`;
    }).join('')}</tbody></table></div>` : '<div class="card empty"><b>No invoices</b>Nothing in this tab yet.</div>'}`
  ];
}

export async function runBilling() {
  try {
    const r = await apiBilling();
    if (r && r.error) {
      toast('Billing error: ' + r.error);
    } else {
      await loadData();
      toast(`Billing run complete: ${(r && r.invoices_created) || 0} invoice(s) created`);
      if (typeof window.R === 'function') window.R();
    }
  } catch (e) {
    // Fallback: mock billing when backend unreachable
    const nextId = Math.max(0, ...D.invoices.map(i => i.id)) + 1;
    const customers = D.customers.filter(c => c.status === 'Active');
    const cust = customers[nextId % customers.length] || { name: 'Orbit Foods' };
    const newInv = { id: nextId, n: `INV-${2040 + nextId}`, c: cust.name, amt: 240, paid: 0, residual: 240, st: 'Draft', due: '2026-11-30', history: [] };
    logInvoiceHistory(newInv, 'Created', null, 'Draft', 'Recurring billing run generated new Draft invoice.');
    D.invoices.push(newInv);
    toast(`Billing run complete (mock): Draft invoice ${newInv.n} generated`);
    if (typeof window.R === 'function') window.R();
  }
}

export function confirmInvoice(id) {
  const i = D.invoices.find(x => x.id === id);
  if (!i) return;

  if (!currentUser.isAuthorized) {
    return toast('Access Denied: Only authorized billing staff can confirm invoices.');
  }

  if (i.st !== 'Draft') {
    return toast(`Invalid status transition: Only Draft invoices can be confirmed (current: ${i.st})`);
  }

  confirmD(`Confirm invoice <b>${i.n}</b> for <b>${i.c}</b> (${M(i.amt)})?<br><small class="mut">Once confirmed, invoice is finalized and terms are locked awaiting payment.</small>`, async () => {
    try {
      const r = await invoiceAction(id, 'confirm');
      if (r && r.error) { toast('Error: ' + r.error); return; }
      await loadData();
      toast(`Invoice ${i.n} confirmed successfully`);
      if (typeof window.R === 'function') window.R();
    } catch (e) {
      // Fallback mock
      const prev = i.st;
      i.st = 'Confirmed';
      logInvoiceHistory(i, 'Confirmed', prev, 'Confirmed', 'Invoice finalized and awaiting payment.');
      toast(`Invoice ${i.n} confirmed (mock)`);
      if (typeof window.R === 'function') window.R();
    }
  }, 'Confirm Invoice');
}

export function cancelInvoice(id) {
  const i = D.invoices.find(x => x.id === id);
  if (!i) return;

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

  o.querySelector('#cc_btn').onclick = async () => {
    const reason = o.querySelector('#c_reason').value.trim() || 'Invoice cancelled by user';
    const prev = i.st;
    i.st = 'Cancelled';
    i.residual = 0;
    X();
    try {
      const r = await invoiceAction(id, 'cancel', null, reason);
      if (r && r.error) { toast('Error: ' + r.error); return; }
      await loadData();
      toast(`Invoice ${i.n} has been cancelled`);
      if (typeof window.R === 'function') window.R();
    } catch (e) {
      const prev = i.st;
      i.st = 'Cancelled';
      logInvoiceHistory(i, 'Cancelled', prev, 'Cancelled', reason);
      toast(`Invoice ${i.n} has been cancelled (mock)`);
      if (typeof window.R === 'function') window.R();
    }
  };
}

export function pay(id) {
  const i = D.invoices.find(x => x.id === id);
  if (!i) return;

  // Authorization check
  if (!currentUser.isAuthorized) {
    return toast('Access Denied: Only authorized billing staff can record payments.');
  }

  // Status check
  if (i.st === 'Draft') {
    return toast('Cannot record payment: Invoice is in Draft. Confirm the invoice first.');
  }
  if (i.st === 'Cancelled') {
    return toast('Cannot record payment on a cancelled invoice.');
  }
  if (i.st === 'Paid') {
    return toast('Invoice is already fully paid.');
  }

  const currentResidual = i.residual !== undefined ? i.residual : (i.amt - (i.paid || 0));

  const o = modal(`
<h2>Record Payment · ${i.n}</h2>
<p class="mut">Customer: <b>${i.c}</b> · Total: <b>${M(i.amt)}</b> · Remaining Balance: <b style="color:var(--c,#0f766e)">${M(currentResidual)}</b></p>

<label for="pa">Payment Amount ($)</label>
<input id="pa" type="number" step="0.01" min="0.01" max="${currentResidual}" value="${currentResidual}" required>

<label for="pm">Payment Method</label>
<select id="pm">
  <option value="Bank transfer">Bank transfer</option>
  <option value="Credit / Debit Card">Credit / Debit Card</option>
  <option value="Cash">Cash</option>
  <option value="Direct Debit">Direct Debit</option>
  <option value="Check / Cheque">Check / Cheque</option>
</select>

<label for="pd">Payment Date</label>
<input id="pd" type="date" value="2026-10-31">

<label for="pr">Transaction Reference</label>
<input id="pr" placeholder="e.g. TXN-9921 (Unique bank/gateway ref)">

<label for="pn">Payment Notes / Memo</label>
<textarea id="pn" style="width:100%;height:60px;margin-bottom:16px;border:1px solid var(--b);border-radius:6px;padding:8px;font-family:inherit" placeholder="Optional notes, receipt number, or memo..."></textarea>

<div class="ft">
  <button class="btn o" onclick="X()">Cancel</button>
  <button class="btn" id="ok">Record Payment</button>
</div>`);

  o.querySelector('#ok').onclick = async () => {
    const amountVal = +o.querySelector('#pa').value;
    const method = o.querySelector('#pm').value;
    const dateVal = o.querySelector('#pd').value || '2026-10-31';
    const refVal = o.querySelector('#pr').value.trim();
    const notesVal = o.querySelector('#pn').value.trim();

    // 1. Strict amount validation
    if (!(amountVal > 0)) {
      return toast('Validation Error: Payment amount must be strictly greater than zero.');
    }
    if (roundToTwo(amountVal - currentResidual) > 0) {
      return toast(`Validation Error: Payment amount (${M(amountVal)}) exceeds remaining balance of ${M(currentResidual)}.`);
    }

    // 2. Prevent duplicate payment submissions
    if (refVal) {
      const isDuplicateRef = (D.payments || []).some(
        p => p.invId === i.id && p.ref && p.ref.toLowerCase() === refVal.toLowerCase()
      );
      if (isDuplicateRef) {
        return toast(`Duplicate Error: Transaction reference '${refVal}' has already been recorded for this invoice.`);
      }
    } else {
      const isIdentical = (D.payments || []).some(
        p => p.invId === i.id && p.amt === amountVal && p.d === dateVal && p.m === method
      );
      if (isIdentical) {
        return toast('Duplicate Error: An identical payment has already been recorded for this invoice today.');
      }
    }

    // 3. Create payment record
    if (!D.payments) D.payments = [];
    const nextPayId = Math.max(0, ...D.payments.map(p => p.id)) + 1;
    const payNum = `PAY-${1000 + nextPayId}`;
    const paymentRecord = {
      id: nextPayId,
      invId: i.id,
      n: payNum,
      inv: i.n,
      c: i.c,
      amt: amountVal,
      m: method,
      d: dateVal,
      ref: refVal || 'N/A',
      notes: notesVal || 'Payment recorded',
      user: currentUser.name
    };
    D.payments.push(paymentRecord);

    // 4. Update invoice balances and state
    i.paid = roundToTwo((i.paid || 0) + amountVal);
    i.residual = Math.max(0, roundToTwo(i.amt - i.paid));

    const isFullSettlement = (i.residual === 0);
    const prevStatus = i.st;

    if (isFullSettlement) {
      i.st = 'Paid';
      logInvoiceHistory(
        i,
        'Payment Recorded',
        prevStatus,
        'Paid',
        `Full settlement of ${M(amountVal)} recorded via ${method} (${payNum}, Ref: ${refVal || 'N/A'}). Balance: $0.00. Notes: ${notesVal || 'None'}`
      );
      toast(`Payment of ${M(amountVal)} recorded. Invoice ${i.n} is now fully Paid.`);
    } else {
      logInvoiceHistory(
        i,
        'Payment Recorded',
        prevStatus,
        prevStatus,
        `Partial payment of ${M(amountVal)} recorded via ${method} (${payNum}, Ref: ${refVal || 'N/A'}). Remaining balance: ${M(i.residual)}. Notes: ${notesVal || 'None'}`
      );
      toast(`Partial payment of ${M(amountVal)} recorded. Remaining balance: ${M(i.residual)}.`);
    }

    X();
    // Attempt real backend payment record
    invoiceAction(id, 'pay', amountVal).then(r => {
      if (r && !r.error) loadData().then(() => { if (typeof window.R === 'function') window.R(); });
    }).catch(() => {});
    if (typeof window.R === 'function') window.R();
  };
}

export function viewPaymentDetails(payId) {
  if (!currentUser.isAuthorized) {
    return toast('Access Denied: Only authorized billing staff can view payment details.');
  }

  const p = (D.payments || []).find(x => x.id === payId);
  if (!p) return toast('Payment record not found.');

  modal(`
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h2 style="margin:0">Payment Receipt · ${p.n}</h2>
      <span class="bd g">Recorded &amp; Settled</span>
    </div>
    <div style="background:#f8fafc;padding:12px;border-radius:6px;margin-bottom:16px">
      <p style="margin:4px 0">Invoice: <b>${p.inv}</b></p>
      <p style="margin:4px 0">Customer: <b>${p.c}</b></p>
      <p style="margin:4px 0">Amount Paid: <b style="color:var(--c,#0f766e);font-size:16px">${M(p.amt)}</b></p>
      <p style="margin:4px 0">Payment Method: <b>${p.m}</b></p>
      <p style="margin:4px 0">Payment Date: <b>${p.d}</b></p>
      <p style="margin:4px 0">Transaction Reference: <b>${p.ref || 'N/A'}</b></p>
      <p style="margin:4px 0">Recorded By: <b>${p.user || 'Billing Staff'}</b></p>
    </div>
    <label>Internal Notes / Memo</label>
    <p style="background:#fff;border:1px solid var(--b);padding:8px;border-radius:4px;color:var(--m,#475569)">${p.notes || 'No operational notes attached.'}</p>
    <div class="ft" style="margin-top:16px">
      <button class="btn o" onclick="window.print()">Print Receipt</button>
      <button class="btn" onclick="X()">Close</button>
    </div>
  `);
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

  const textContent = `=====================================================
INVOICE: ${i.n}
=====================================================
Customer: ${i.c}
Date: 2026-10-31
Due Date: ${i.due}
Status: ${i.st}
-----------------------------------------------------
Total Invoiced Amount:    $${Number(i.amt).toFixed(2)}
Total Paid to Date:       $${Number(i.paid || (i.st === 'Paid' ? i.amt : 0)).toFixed(2)}
Remaining Balance Due:    $${Number(i.residual !== undefined ? i.residual : (i.st === 'Paid' ? 0 : i.amt)).toFixed(2)}
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
  const isOverdue = ds(i) === 'Overdue';
  const historyList = (i.history || []).slice().reverse();
  const invoicePayments = (D.payments || []).filter(p => p.invId === i.id);

  const totalAmt = i.amt;
  const paidAmt = i.paid !== undefined ? i.paid : (i.st === 'Paid' ? totalAmt : 0);
  const residualAmt = i.residual !== undefined ? i.residual : (i.st === 'Paid' ? 0 : totalAmt);

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
      <small style="color:#334155"><b>Status: Draft.</b> Invoice has been generated but not yet confirmed. Financial terms may be adjusted before confirmation.</small>
    </div>
  ` : i.st === 'Confirmed' ? `
    <div style="background:#eff6ff;border-left:3px solid #3b82f6;padding:8px 12px;margin:14px 0;border-radius:4px">
      <small style="color:#1d4ed8"><b>Status: Confirmed.</b> Invoice is finalized awaiting payment. Financial lines are locked. Remaining due: <b>${M(residualAmt)}</b>.</small>
    </div>
  ` : i.st === 'Paid' ? `
    <div style="background:#ecfdf5;border-left:3px solid #10b981;padding:8px 12px;margin:14px 0;border-radius:4px">
      <small style="color:#047857"><b>Status: Fully Paid.</b> Invoice is completely settled. No further payments or modifications permitted.</small>
    </div>
  ` : `
    <div style="background:#fef2f2;border-left:3px solid #ef4444;padding:8px 12px;margin:14px 0;border-radius:4px">
      <small style="color:#b91c1c"><b>Status: Cancelled.</b> This invoice was voided/cancelled and cannot accept payments or processing.</small>
    </div>
  `}

  <!-- Financial Summary -->
  <table style="margin-top:12px">
    <thead>
      <tr><th>Billing Breakdown</th><th style="text-align:right">Amount</th></tr>
    </thead>
    <tbody>
      <tr><td>Subscription Recurring Service</td><td style="text-align:right">${M((totalAmt / 1.18).toFixed(2))}</td></tr>
      <tr><td>Applicable Tax (18%)</td><td style="text-align:right">${M((totalAmt - totalAmt / 1.18).toFixed(2))}</td></tr>
      <tr style="font-weight:bold;border-top:1px solid var(--b)"><td>Total Invoiced</td><td style="text-align:right"><b>${M(totalAmt)}</b></td></tr>
      <tr style="color:#047857"><td>Total Paid</td><td style="text-align:right"><b>${M(paidAmt)}</b></td></tr>
      <tr style="font-weight:bold;font-size:15px;background:#f8fafc">
        <td>Remaining Balance Due</td>
        <td style="text-align:right;color:${residualAmt > 0 ? '#b91c1c' : '#047857'}"><b>${M(residualAmt)}</b></td>
      </tr>
    </tbody>
  </table>

  <!-- Action Toolbar with Payment & Lifecycle Controls -->
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

<!-- Recorded Payments Section -->
<div class="card" style="max-width:760px;margin-top:16px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <h3 style="margin:0">Recorded Payments</h3>
    <small class="mut">${invoicePayments.length} payment(s) credited</small>
  </div>

  ${invoicePayments.length ? `
    <div style="overflow-x:auto">
      <table style="width:100%;font-size:13px">
        <thead>
          <tr>
            <th>Payment #</th>
            <th>Date</th>
            <th>Method</th>
            <th style="text-align:right">Amount</th>
            <th>Reference</th>
            <th>Notes</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${invoicePayments.map(p => `
            <tr>
              <td><b>${p.n}</b></td>
              <td>${p.d}</td>
              <td>${p.m}</td>
              <td style="text-align:right;font-weight:bold;color:#047857">${M(p.amt)}</td>
              <td><code>${p.ref || 'N/A'}</code></td>
              <td class="mut">${p.notes || '—'}</td>
              <td style="text-align:right"><button class="btn o" style="padding:3px 8px;font-size:11px" onclick="viewPaymentDetails(${p.id})">Details</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  ` : '<p class="mut" style="margin:8px 0">No payments recorded yet for this invoice.</p>'}
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

function roundToTwo(num) {
  return +(Math.round(num + "e+2") + "e-2");
}
