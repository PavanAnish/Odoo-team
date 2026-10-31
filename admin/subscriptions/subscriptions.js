import { D, S, M, B, ds, confirmD, toast } from '../shared/store.js';
import { subscriptionAction } from '../shared/api.js';
import { loadData } from '../shared/store.js';

export const ST = ['Draft', 'Quotation', 'Confirmed', 'Active', 'Paused', 'Closed'];

// Window-level async action handler (called from inline onclick)
window._subAction = async (sid, action, extra) => {
  try {
    const r = await subscriptionAction(sid, action, extra);
    if (r && r.error) {
      toast('Error: ' + r.error);
    } else {
      await loadData();
      window.R();
      toast(action.charAt(0).toUpperCase() + action.slice(1) + ' successful');
    }
  } catch (e) {
    toast('Error: ' + e.message);
  }
};

export function subs() {
  if (S.sel) {
    const selectedSub = D.subs.find(s => s.id === S.sel);
    if (selectedSub) return subD(selectedSub);
  }
  const tb = `<div class="card tp tw rt"><table><thead><tr><th>Subscription</th><th>Customer</th><th>Plan</th><th>Amount</th><th>Next billing</th><th>Status</th></tr></thead><tbody>${D.subs.map(s => `<tr class="r" onclick="S.sel=${s.id};R()"><td data-l="ID">${s.n}</td><td data-l="Customer">${s.c}</td><td data-l="Plan">${s.plan}</td><td data-l="Amount">${M(s.amt)}</td><td data-l="Next">${s.next || '—'}</td><td data-l="Status">${B(s.paused ? 'Paused' : s.st)}</td></tr>`).join('')}</tbody></table></div>`;
  const kb = `<div class="kb">${ST.map(st => `<div><b>${st}</b> <small class="mut">${D.subs.filter(s => (s.paused ? 'Paused' : s.st) === st).length}</small>${D.subs.filter(s => (s.paused ? 'Paused' : s.st) === st).map(s => `<div class="card" onclick="S.sel=${s.id};R()"><b>${s.c}</b><br><small class="mut">${s.n} · ${s.plan}</small><br>${M(s.amt)}</div>`).join('')}</div>`).join('')}</div>`;

  return [
    `<button class="btn" onclick="location.hash='quotations'">+ New subscription</button>`,
    `<div class="tabs">${['table', 'kanban'].map(v => `<button class="${S.view2 === v || (!S.view2 && v === 'table') ? 'on' : ''}" onclick="S.view2='${v}';R()">${v === 'table' ? 'Table' : 'Kanban'}</button>`).join('')}</div>${S.view2 === 'kanban' ? kb : tb}`
  ];
}

export function subD(s) {
  const i = ST.indexOf(s.paused ? 'Paused' : s.st);
  const inv = D.invoices.filter(x => x.c === s.c);

  return [
    `<button class="btn o" onclick="S.sel=null;R()">← All subscriptions</button>`,
    `<div class="card">
  <h2>${s.n} ${B(s.paused ? 'Paused' : s.st)}</h2>
  <div class="stp">${ST.map((x, j) => `<div class="${j < i ? 'dn2' : j === i ? 'cur' : ''}">${x}</div>`).join('')}</div>
  <p><b>Customer</b> ${s.c} &nbsp; <b>Plan</b> ${s.plan} &nbsp; <b>Billing</b> ${M(s.amt)} · next ${s.next || '—'}</p>
  <div class="tb" style="margin-top:16px">
    ${(s.st === 'Draft' || s.st === 'Quotation') ? `<button class="btn" onclick="window._subAction(${s.id},'confirm')">Confirm</button>` : ''}
    ${s.st === 'Confirmed' ? `<button class="btn" onclick="window._subAction(${s.id},'activate')">Activate</button>` : ''}
    ${s.st === 'Active' && !s.paused ? `<button class="btn o" onclick="window._subAction(${s.id},'pause')">Pause</button>` : ''}
    ${s.paused ? `<button class="btn o" onclick="window._subAction(${s.id},'resume')">Resume</button>` : ''}
    ${(s.st === 'Active' || s.paused) ? `<button class="btn o" onclick="window._subAction(${s.id},'renew')">Renew</button>` : ''}
    ${s.st !== 'Closed' ? `<button class="btn d" onclick="confirmD('Close ${s.n}?',()=>window._subAction(${s.id},'close'),'Close','d')">Close</button>` : ''}
  </div>
</div>
<div class="card" style="margin-top:16px">
  <h3>Invoices generated</h3>
  ${inv.map(x => `<p style="padding:8px 0">${x.n} ${B(ds(x))} ${M(x.amt)} · due ${x.due}</p>`).join('') || '<p class="mut">None yet.</p>'}
</div>`
  ];
}
