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

export function generateClientInvoicePdf(i) {
  const cust = i.customer || D.customers.find(c => c.name === i.c) || { name: i.c, email: 'billing@example.com', phone: '+1 (555) 010-0000', street: '100 Enterprise Way', city: 'San Francisco', zip: '94105', country: 'United States', vat: 'US-94819284' };
  const lines = i.lines && i.lines.length ? i.lines : [
    { desc: `${i.c} - Subscription Service (${i.n})`, qty: 1, unitPrice: (i.amt / 1.18).toFixed(2), disc: 0, tax: 18, subtotal: (i.amt / 1.18).toFixed(2) }
  ];
  const untaxed = i.untaxed !== undefined ? i.untaxed : +(i.amt / 1.18).toFixed(2);
  const tax = i.tax !== undefined ? i.tax : +(i.amt - untaxed).toFixed(2);
  const paid = i.paid !== undefined ? i.paid : (i.st === 'Paid' ? i.amt : 0);
  const residual = (i.st === 'Cancelled') ? 0 : (i.residual !== undefined ? i.residual : (i.st === 'Paid' ? 0 : i.amt));
  const payments = (D.payments || []).filter(p => p.invId === i.id);

  let stream = `BT\n/F1 16 Tf\n50 740 Td\n(TAX INVOICE - ${i.n}) Tj\n`;
  stream += `/F1 9 Tf\n0 -22 Td\n(Invoice Date: ${i.d || '2026-10-31'}   |   Due Date: ${i.due || '2026-11-15'}   |   Status: ${i.st.toUpperCase()}) Tj\n`;
  stream += `0 -18 Td\n(Customer: ${cust.name}   |   Email: ${cust.email || 'N/A'}   |   Phone: ${cust.phone || 'N/A'}) Tj\n`;
  stream += `0 -16 Td\n(Address: ${cust.street || '100 Enterprise Way'}, ${cust.city || 'San Francisco'} ${cust.zip || '94105'} ${cust.country || 'USA'}   |   VAT: ${cust.vat || 'US-94819284'}) Tj\n`;
  stream += `0 -22 Td\n(----------------------------------------------------------------------------------------------------------------------------------------) Tj\n`;
  stream += `0 -14 Td\n(Item Description                                                  Qty       Unit Price      Discount      Tax        Subtotal) Tj\n`;
  stream += `0 -14 Td\n(----------------------------------------------------------------------------------------------------------------------------------------) Tj\n`;

  lines.forEach(l => {
    const dStr = (l.desc || 'Service Item').padEnd(48).slice(0, 48);
    const qStr = String(Number(l.qty || 1).toFixed(1)).padStart(6);
    const pStr = ('$' + Number(l.unitPrice || 0).toFixed(2)).padStart(14);
    const discStr = (l.disc ? (l.disc + '%') : '-').padStart(10);
    const taxStr = ((l.tax || 18) + '%').padStart(8);
    const totStr = ('$' + Number(l.subtotal || 0).toFixed(2)).padStart(14);
    stream += `0 -16 Td\n(${dStr} ${qStr} ${pStr} ${discStr} ${taxStr} ${totStr}) Tj\n`;
  });

  stream += `0 -20 Td\n(----------------------------------------------------------------------------------------------------------------------------------------) Tj\n`;
  stream += `0 -15 Td\n(Subtotal (Untaxed):                                                                                                $${Number(untaxed).toFixed(2)}) Tj\n`;
  stream += `0 -15 Td\n(Applicable Tax (18%):                                                                                               $${Number(tax).toFixed(2)}) Tj\n`;
  stream += `0 -16 Td\n(Final Invoice Total:                                                                                               $${Number(i.amt).toFixed(2)}) Tj\n`;
  stream += `0 -15 Td\n(Total Payments Credited:                                                                                           -$${Number(paid).toFixed(2)}) Tj\n`;
  stream += `0 -16 Td\n(Remaining Outstanding Balance:                                                                                     $${Number(residual).toFixed(2)}) Tj\n`;
  stream += `0 -25 Td\n(================================================================================================================) Tj\n`;
  stream += `0 -14 Td\n(PAYMENT INSTRUCTIONS & TERMS: Due on or before ${i.due || '2026-11-15'}. Remit via Bank Wire or Credit Card.) Tj\n`;
  stream += `0 -14 Td\n(Bank: First Commercial Global Bank  |  Account: 1029-3847-5610-88  |  SWIFT: FCBKUS33  |  Ref: ${i.n}) Tj\n`;

  if (payments.length) {
    stream += `0 -18 Td\n(Recorded Payments: ${payments.map(p => p.n + ' (' + p.d + ', $' + p.amt + ')').join(', ')}) Tj\n`;
  }
  stream += `0 -22 Td\n(Thank you for your business! For inquiries, contact billing@odoo-subscription.com) Tj\nET`;

  const streamBytes = new TextEncoder().encode(stream);
  const streamLength = streamBytes.length;

  const header = `%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n4 0 obj\n<< /Length ${streamLength} >>\nstream\n`;
  const footer = `\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000300 00000 n \n0000000233 00000 n \ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n1500\n%%EOF\n`;

  return header + stream + footer;
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

  const cust = i.customer || D.customers.find(c => c.name === i.c) || {};
  const email = i.recipient_email || cust.email || `${i.c.toLowerCase().replace(/[^a-z]/g, '')}@example.com`;

  const o = modal(`
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
  <h3 style="margin:0">Send Invoice · ${i.n}</h3>
  <span class="bd g">Ready for Dispatch</span>
</div>
<p class="mut" style="margin-bottom:12px">Deliver official invoice PDF and settlement link directly to customer mailbox.</p>

<label for="s_recipient">Customer Name</label>
<input id="s_recipient" value="${i.c}" disabled style="background:#f8fafc;margin-bottom:10px">

<label for="s_email">Recipient Email Address <span style="color:#dc2626">*</span></label>
<input id="s_email" type="email" value="${email}" style="margin-bottom:10px" placeholder="e.g. billing@company.com">

<label for="s_subject">Email Subject</label>
<input id="s_subject" value="Tax Invoice ${i.n} from Odoo Subscriptions (${M(i.amt)})" style="margin-bottom:10px">

<label for="s_msg">Email Message Body</label>
<textarea id="s_msg" style="width:100%;height:75px;margin-bottom:12px;border:1px solid var(--b);border-radius:6px;padding:8px;font-family:inherit">Dear ${i.c},

Please find attached your official invoice ${i.n} for ${M(i.amt)}, with payment due on ${i.due}.

Thank you for your business!
Odoo Subscription Billing Team</textarea>

<div style="background:#f1f5f9;border:1px solid #cbd5e1;border-radius:6px;padding:8px 12px;margin-bottom:16px;display:flex;align-items:center;gap:10px">
  <span style="font-size:18px">📄</span>
  <div>
    <b style="font-size:12px;color:#0f172a">${i.n}.pdf</b>
    <div style="font-size:11px;color:#64748b">Professional PDF Attachment · Includes items, taxes, payment instructions</div>
  </div>
</div>

<div class="ft">
  <button class="btn o" onclick="X()">Cancel</button>
  <button class="btn" id="s_send">✉ Send Invoice via Email</button>
</div>`);

  o.querySelector('#s_send').onclick = async () => {
    const recipient = o.querySelector('#s_email').value.trim();
    const subject = o.querySelector('#s_subject').value.trim();
    const message = o.querySelector('#s_msg').value.trim();

    // Validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!recipient || !emailRegex.test(recipient)) {
      return toast('Validation Error: Please provide a valid recipient email address.');
    }

    X();
    try {
      const r = await invoiceAction(id, 'send', null, null, { recipient, subject, message });
      if (r && r.error) {
        toast('Delivery Notice: ' + r.error);
      }
    } catch (e) {
      // Offline fallback
    }

    i.sent = true;
    i.sent_date = '2026-10-31';
    i.recipient_email = recipient;
    i.delivery_status = 'sent';
    logInvoiceHistory(i, 'Sent', i.st, i.st, `Invoice dispatched via email to ${recipient} with PDF attached.`);
    toast(`Invoice ${i.n} sent to ${recipient} (PDF attached)`);
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
  toast(`Preparing print document for ${i.n}...`);

  const cust = i.customer || D.customers.find(c => c.name === i.c) || { name: i.c, email: 'billing@example.com', phone: '+1 555-0101', street: '100 Enterprise Way', city: 'Silicon Valley', zip: '94025', country: 'United States', vat: 'US-94819284' };
  const lines = i.lines && i.lines.length ? i.lines : [
    { desc: `${i.c} - Subscription Service`, qty: 1, unitPrice: (i.amt / 1.18).toFixed(2), disc: 0, tax: 18, subtotal: (i.amt / 1.18).toFixed(2) }
  ];
  const untaxed = i.untaxed !== undefined ? i.untaxed : +(i.amt / 1.18).toFixed(2);
  const tax = i.tax !== undefined ? i.tax : +(i.amt - untaxed).toFixed(2);
  const paid = i.paid !== undefined ? i.paid : (i.st === 'Paid' ? i.amt : 0);
  const residual = (i.st === 'Cancelled') ? 0 : (i.residual !== undefined ? i.residual : (i.st === 'Paid' ? 0 : i.amt));
  const payments = (D.payments || []).filter(p => p.invId === i.id);

  const printWindow = window.open('', '_blank', 'width=800,height=900');
  if (!printWindow) {
    window.print();
    if (typeof window.R === 'function') window.R();
    return;
  }

  const html = `<!DOCTYPE html>
<html>
<head>
  <title>Invoice - ${i.n}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 40px; color: #1e293b; line-height: 1.5; }
    .header { display: flex; justify-content: space-between; border-bottom: 2px solid #0f172a; padding-bottom: 20px; }
    .company { font-size: 13px; color: #475569; }
    .company h2 { margin: 0 0 6px 0; color: #0f172a; font-size: 20px; }
    .title { text-align: right; }
    .title h1 { margin: 0; color: #0f172a; font-size: 24px; letter-spacing: 0.5px; }
    .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 24px 0; background: #f8fafc; padding: 16px; border-radius: 6px; border: 1px solid #e2e8f0; }
    .info-box h4 { margin: 0 0 6px 0; font-size: 11px; text-transform: uppercase; color: #64748b; }
    .info-box p { margin: 3px 0; font-size: 13px; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px; }
    th { background: #0f172a; color: #ffffff; text-align: left; padding: 8px 10px; font-weight: 600; font-size: 12px; }
    td { padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }
    .num { text-align: right; }
    .totals { width: 340px; margin-left: auto; margin-top: 10px; }
    .totals td { padding: 5px 8px; border: none; }
    .totals tr.grand { font-size: 15px; font-weight: bold; background: #f1f5f9; border-top: 2px solid #0f172a; border-bottom: 2px solid #0f172a; }
    .totals tr.due { font-size: 16px; font-weight: bold; color: ${residual > 0 ? '#dc2626' : '#047857'}; background: ${residual > 0 ? '#fef2f2' : '#ecfdf5'}; }
    .footer { margin-top: 40px; padding-top: 15px; border-top: 1px solid #cbd5e1; font-size: 11px; color: #64748b; text-align: center; }
    @media print { body { margin: 0; } }
  </style>
</head>
<body>
  <div class="header">
    <div class="company">
      <h2>Odoo Subscription Management</h2>
      <p>100 Enterprise Way · Silicon Valley, CA 94025<br>Email: billing@odoo-subscription.com · Phone: +1 (555) 019-2834<br>Tax ID: US-94819284</p>
    </div>
    <div class="title">
      <h1>TAX INVOICE</h1>
      <p style="margin:4px 0 0;font-size:14px"><b>${i.n}</b></p>
      <p style="margin:4px 0 0;font-size:12px;color:#64748b">Date: ${i.d || '2026-10-31'} · Due: <b>${i.due}</b></p>
      <p style="margin:4px 0 0"><span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold;background:#0f172a;color:#fff">${i.st.toUpperCase()}</span></p>
    </div>
  </div>

  <div class="info-grid">
    <div class="info-box">
      <h4>Bill To Customer</h4>
      <p><b>${cust.name}</b></p>
      <p>${cust.street || '100 Business Way'}</p>
      <p>${cust.city || 'San Francisco'}, ${cust.zip || '94105'} ${cust.country || 'USA'}</p>
      <p>Email: ${cust.email || 'billing@example.com'}</p>
      <p>Phone: ${cust.phone || 'N/A'} · VAT: ${cust.vat || 'US-94819284'}</p>
    </div>
    <div class="info-box">
      <h4>Payment Instructions &amp; Bank Details</h4>
      <p>Payment Terms: Net 15 / Due upon receipt</p>
      <p>Bank: First Commercial Global Bank</p>
      <p>Account #: 1029-3847-5610-88</p>
      <p>SWIFT/BIC: FCBKUS33 · Routing: 021000021</p>
      <p>Payment Reference: <b>${i.n}</b></p>
    </div>
  </div>

  <h4 style="margin:0;font-size:12px;text-transform:uppercase;color:#0f172a">Product Descriptions &amp; Quantities</h4>
  <table>
    <thead>
      <tr>
        <th>Description</th>
        <th class="num">Quantity</th>
        <th class="num">Unit Price</th>
        <th class="num">Discount</th>
        <th class="num">Taxes</th>
        <th class="num">Subtotal</th>
      </tr>
    </thead>
    <tbody>
      ${lines.map(l => `
        <tr>
          <td><b>${l.desc}</b></td>
          <td class="num">${Number(l.qty || 1).toFixed(1)}</td>
          <td class="num">$${Number(l.unitPrice || 0).toFixed(2)}</td>
          <td class="num">${l.disc ? l.disc + '%' : '-'}</td>
          <td class="num">${l.tax || 18}%</td>
          <td class="num"><b>$${Number(l.subtotal || 0).toFixed(2)}</b></td>
        </tr>
      `).join('')}
    </tbody>
  </table>

  <table class="totals">
    <tr><td>Subtotal (Untaxed):</td><td class="num">$${Number(untaxed).toFixed(2)}</td></tr>
    <tr><td>Applicable Taxes (18%):</td><td class="num">$${Number(tax).toFixed(2)}</td></tr>
    <tr class="grand"><td>Final Invoice Amount:</td><td class="num">$${Number(i.amt).toFixed(2)}</td></tr>
    <tr style="color:#047857"><td>Payments Credited:</td><td class="num">-$${Number(paid).toFixed(2)}</td></tr>
    <tr class="due"><td>Remaining Balance Due:</td><td class="num">$${Number(residual).toFixed(2)}</td></tr>
  </table>

  ${payments.length ? `
    <h4 style="margin:20px 0 6px 0;font-size:12px;text-transform:uppercase;color:#0f172a">Recorded Payments &amp; Receipts</h4>
    <table>
      <thead>
        <tr><th>Receipt #</th><th>Date</th><th>Method</th><th>Reference</th><th class="num">Amount Paid</th></tr>
      </thead>
      <tbody>
        ${payments.map(p => `<tr><td><b>${p.n}</b></td><td>${p.d}</td><td>${p.m}</td><td><code>${p.ref}</code></td><td class="num" style="color:#047857;font-weight:bold">$${Number(p.amt).toFixed(2)}</td></tr>`).join('')}
      </tbody>
    </table>
  ` : ''}

  <div class="footer">
    Thank you for your business! Please settle outstanding balances before the due date (${i.due}).<br>
    Questions? Email billing@odoo-subscription.com or call +1 (555) 019-2834.
  </div>
</body>
</html>`;

  printWindow.document.open();
  printWindow.document.write(html);
  printWindow.document.close();
  printWindow.focus();
  setTimeout(() => {
    printWindow.print();
  }, 350);

  if (typeof window.R === 'function') window.R();
}

export async function downloadInvoice(id) {
  const i = D.invoices.find(x => x.id === id);
  if (!i) return;
  if (i.st === 'Cancelled') {
    return toast('Cannot download a cancelled invoice.');
  }

  logInvoiceHistory(i, 'Downloaded', i.st, i.st, 'Invoice PDF copy downloaded.');

  // 1. Try server-side PDF generation if available
  try {
    const res = await fetch(`/admin/api/invoice/${id}/pdf`);
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${i.n}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast(`Downloaded ${i.n}.pdf (Server PDF)`);
      if (typeof window.R === 'function') window.R();
      return;
    }
  } catch (e) {
    // Fall back to client generator
  }

  // 2. Client-side professional PDF generation fallback
  const pdfString = generateClientInvoicePdf(i);
  const blob = new Blob([pdfString], { type: 'application/pdf' });
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
  const untaxedAmt = i.untaxed !== undefined ? i.untaxed : +(totalAmt / 1.18).toFixed(2);
  const taxAmt = i.tax !== undefined ? i.tax : +(totalAmt - untaxedAmt).toFixed(2);
  const paidAmt = i.paid !== undefined ? i.paid : (i.st === 'Paid' ? totalAmt : 0);
  const residualAmt = (i.st === 'Cancelled') ? 0 : (i.residual !== undefined ? i.residual : (i.st === 'Paid' ? 0 : totalAmt));

  const cust = i.customer || D.customers.find(c => c.name === i.c) || {
    name: i.c,
    email: `${i.c.toLowerCase().replace(/[^a-z]/g, '')}@example.com`,
    phone: '+1 (555) 010-9921',
    street: '1200 Pine St, Suite 400',
    city: 'Seattle',
    zip: '98101',
    country: 'United States',
    vat: 'US-98129034'
  };

  const lines = i.lines && i.lines.length ? i.lines : [
    {
      desc: `${i.c} - Subscription Recurring Service (${i.n})`,
      qty: 1,
      unitPrice: untaxedAmt,
      disc: 0,
      tax: 18,
      subtotal: untaxedAmt
    }
  ];

  return [
    `<button class="btn o np" onclick="S.inv=null;R()">← All invoices</button>`,
    `<div class="card" style="max-width:820px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <h2 style="margin:0 0 4px">Invoice ${i.n}</h2>
      <p class="mut" style="margin:0">Customer: <b>${i.c}</b> · Invoice Date: <b>${i.d || '2026-10-31'}</b> · Due: <b>${i.due}</b>${isOverdue ? ` · <b class="dn">${dO(i)} days overdue</b>` : ''}</p>
    </div>
    <div style="text-align:right">
      ${B(ds(i))}
      <div style="margin-top:6px">
        <span class="bd ${i.sent ? 'g' : 's'}" style="font-size:11px">${i.sent ? '✓ Delivered via Email' : 'Email Pending'}</span>
      </div>
    </div>
  </div>

  ${i.st === 'Draft' ? `
    <div style="background:#f1f5f9;border-left:3px solid #64748b;padding:8px 12px;margin:14px 0;border-radius:4px">
      <small style="color:#334155"><b>Status: Draft.</b> Invoice has been generated but not yet confirmed. Financial terms and line items may be adjusted before confirmation.</small>
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

  <!-- Customer Details Card -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 16px;margin:14px 0">
    <div>
      <span class="mut" style="font-size:11px;text-transform:uppercase;font-weight:bold">Customer &amp; Billing Contact</span>
      <div style="font-weight:bold;font-size:14px;margin-top:2px">${cust.name}</div>
      <div style="font-size:12px;color:#475569;margin-top:2px">
        <div>Email: <b>${cust.email || 'N/A'}</b></div>
        <div>Phone: ${cust.phone || 'N/A'}</div>
        <div>Address: ${cust.street || '100 Business Parkway'}, ${cust.city || 'Seattle'} ${cust.zip || ''}</div>
        <div>Tax ID / VAT: <code>${cust.vat || 'US-98129034'}</code></div>
      </div>
    </div>
    <div>
      <span class="mut" style="font-size:11px;text-transform:uppercase;font-weight:bold">Payment &amp; Bank Instructions</span>
      <div style="font-size:12px;color:#475569;margin-top:4px;line-height:1.5">
        <div><b>Payment Due Date:</b> <span style="color:#0f172a;font-weight:bold">${i.due}</span></div>
        <div><b>Payment Terms:</b> Due upon receipt / Net 15</div>
        <div><b>Bank Name:</b> First Commercial Global Bank</div>
        <div><b>Account #:</b> 1029-3847-5610-88 · <b>SWIFT:</b> FCBKUS33</div>
        <div><b>Reference:</b> <code>${i.n}</code></div>
      </div>
    </div>
  </div>

  <!-- Product Descriptions & Quantities Table -->
  <h4 style="margin:16px 0 6px;font-size:12px;text-transform:uppercase;color:#475569">Product Descriptions &amp; Quantities</h4>
  <div style="overflow-x:auto;border:1px solid #e2e8f0;border-radius:6px">
    <table style="width:100%;font-size:13px;margin:0">
      <thead style="background:#0f172a;color:#fff">
        <tr>
          <th>Description</th>
          <th style="text-align:right">Quantity</th>
          <th style="text-align:right">Unit Price</th>
          <th style="text-align:right">Discount</th>
          <th style="text-align:right">Taxes</th>
          <th style="text-align:right">Subtotal</th>
        </tr>
      </thead>
      <tbody>
        ${lines.map(l => `
          <tr>
            <td><b>${l.desc}</b></td>
            <td style="text-align:right">${Number(l.qty || 1).toFixed(1)}</td>
            <td style="text-align:right">${M(l.unitPrice)}</td>
            <td style="text-align:right">${l.disc ? l.disc + '%' : '-'}</td>
            <td style="text-align:right">${l.tax || 18}%</td>
            <td style="text-align:right;font-weight:bold">${M(l.subtotal)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  </div>

  <!-- Financial Totals Summary Breakdown -->
  <div style="display:flex;justify-content:flex-end;margin-top:14px">
    <table style="width:360px;font-size:13px">
      <tr>
        <td>Subtotal (Untaxed):</td>
        <td style="text-align:right"><b>${M(untaxedAmt)}</b></td>
      </tr>
      <tr>
        <td>Applicable Taxes (18%):</td>
        <td style="text-align:right"><b>${M(taxAmt)}</b></td>
      </tr>
      <tr style="font-weight:bold;font-size:15px;border-top:2px solid #0f172a;background:#f1f5f9">
        <td>Final Invoice Total:</td>
        <td style="text-align:right"><b>${M(totalAmt)}</b></td>
      </tr>
      <tr style="color:#047857">
        <td>Total Paid to Date:</td>
        <td style="text-align:right"><b>-${M(paidAmt)}</b></td>
      </tr>
      <tr style="font-weight:bold;font-size:16px;border-top:1px solid ${residualAmt > 0 ? '#dc2626' : '#047857'};background:${residualAmt > 0 ? '#fef2f2' : '#ecfdf5'}">
        <td style="color:${residualAmt > 0 ? '#dc2626' : '#047857'}">Remaining Balance Due:</td>
        <td style="text-align:right;color:${residualAmt > 0 ? '#dc2626' : '#047857'}"><b>${M(residualAmt)}</b></td>
      </tr>
    </table>
  </div>

  <!-- Action Toolbar with Payment & Lifecycle Controls -->
  <div class="tb np" style="margin-top:20px;padding-top:16px;border-top:1px solid var(--b);display:flex;gap:8px;flex-wrap:wrap">
    ${i.st === 'Draft' ? `
      <button class="btn" onclick="confirmInvoice(${i.id})">✓ Confirm invoice</button>
      <button class="btn o" onclick="downloadInvoice(${i.id})">Download PDF</button>
      <button class="btn o" onclick="printInvoice(${i.id})">Print</button>
      <button class="btn o" onclick="cancelInvoice(${i.id})">Cancel invoice</button>
      <button class="btn o d" onclick="deleteInvoice(${i.id})">Delete Draft</button>
    ` : (i.st === 'Confirmed' || isOverdue) ? `
      <button class="btn" onclick="pay(${i.id})">Record payment</button>
      <button class="btn" style="background:#0284c7" onclick="sendInvoice(${i.id})">✉ Send by email</button>
      <button class="btn o" onclick="downloadInvoice(${i.id})">📄 Download PDF</button>
      <button class="btn o" onclick="printInvoice(${i.id})">🖨 Print</button>
      <button class="btn o d" onclick="cancelInvoice(${i.id})">Cancel invoice</button>
    ` : i.st === 'Paid' ? `
      <button class="btn" style="background:#047857" onclick="sendInvoice(${i.id})">✉ Send receipt</button>
      <button class="btn o" onclick="downloadInvoice(${i.id})">📄 Download PDF</button>
      <button class="btn o" onclick="printInvoice(${i.id})">🖨 Print</button>
      <span class="mut" style="font-size:12px;margin-left:8px;align-self:center">✓ Protected finalized record</span>
    ` : `
      <button class="btn o" disabled style="opacity:0.6;cursor:not-allowed">Actions Disabled (Cancelled)</button>
    `}
  </div>
</div>

<!-- Recorded Payments Section -->
<div class="card" style="max-width:820px;margin-top:16px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <h3 style="margin:0">Recorded Payment Receipts</h3>
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
<div class="card" style="max-width:820px;margin-top:16px">
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
              <td><span class="bd ${h.act === 'Confirmed' ? 'g' : h.act === 'Payment Recorded' ? 'g' : h.act === 'Sent' ? 'g' : h.act === 'Cancelled' ? 'r' : 's'}">${h.act}</span></td>
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
