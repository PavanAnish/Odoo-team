import { D, S, M, ds, getFinancialSummary } from '../shared/store.js';

export const spark = (v, c = '#A47551') => {
  const m = Math.max(...v);
  return `<svg viewBox="0 0 80 24" width="80" height="24"><polyline fill="none" stroke="${c}" stroke-width="2" points="${v.map((y, i) => i * 80 / (v.length - 1) + ',' + (22 - y / m * 20)).join(' ')}"/></svg>`;
};

export const kpi = (l, v, pre, t, sp) => `
<div class="card">
  <span class="mut">${l}</span>
  <div class="kv"><span class="cu" data-v="${v}" data-p="${pre}">0</span></div>
  <div style="display:flex;justify-content:space-between;align-items:center">
    <small class="${t < 0 && l.startsWith('Over') ? 'dn' : 'up'}">${t > 0 ? '▲' : '▼'} ${Math.abs(t)}%</small>
    ${spark(sp, l.startsWith('Over') ? '#C4674A' : '#A47551')}
  </div>
</div>`;

export const area = (v, c, w = 600, h = 200) => {
  const m = Math.max(...v) * 1.1, p = v.map((y, i) => [i * w / (v.length - 1), h - y / m * h]);
  return `<path d="M0,${h} ${p.map(q => 'L' + q).join(' ')} L${w},${h}Z" fill="${c}" opacity=".18"/><polyline fill="none" stroke="${c}" stroke-width="2.5" points="${p.join(' ')}"/>`;
};

export function dash() {
  const summary = getFinancialSummary(D.invoices);
  const od = D.invoices.filter(i => ds(i) === 'Overdue');
  const odA = summary.totalOverdue;
  const paid = summary.totalPaid;
  const out = summary.totalOutstanding;

  const ST = ['Draft', 'Quotation', 'Confirmed', 'Active', 'Closed'];
  const cl = ['#EDE3D8', '#D9A441', '#C9A88A', '#7E9C88', '#A29789'];
  const cn = ST.map(s => D.subs.filter(x => x.st === s).length);
  let a = 0;
  const cg = cn.map((n, i) => {
    const s = a;
    a += n / D.subs.length * 100;
    return `${cl[i]} ${s}% ${a}%`;
  }).join(',');

  const mo = [42, 47, 51, 49, 58, 63, 66, 71, 75, 82, 88, 94];
  const qt = [140, 170, 212, 264];
  const mm = S.rev === 'Month' ? mo : qt;
  const mm2 = mm.map(x => x * 0.62);

  const actBtn = `<button class="btn" onclick="location.hash='quotations'">+ New quotation</button>`;
  const content = `
<p class="mut" style="margin-bottom:16px">Welcome back, Maya. Here is how billing looks today.</p>
<div class="g g4">
  ${kpi('Active subscriptions', D.subs.filter(s => s.st === 'Active').length, '', 8.2, [3, 4, 4, 5, 6, 7, 8])}
  ${kpi('Total revenue', 94200, '$', 12.4, mo.slice(4, 11))}
  ${kpi('MRR', 58400, '$', 6.1, [40, 44, 45, 50, 52, 55, 58])}
  ${kpi('Overdue invoices', od.length, '', -3.5, [1, 3, 2, 2, 4, 3, 2])}
</div>
<p class="mut" style="margin:-8px 0 16px">Overdue amount: <b>${M(odA)}</b> across ${od.length} invoices</p>

<div class="g g2" style="grid-template-columns:2fr 1fr">
  <div class="card">
    <div style="display:flex;justify-content:space-between">
      <h3>Revenue</h3>
      <div class="tabs">${['Month', 'Quarter'].map(x => `<button class="${S.rev === x ? 'on' : ''}" onclick="S.rev='${x}';R()">${x}</button>`).join('')}</div>
    </div>
    <svg viewBox="0 0 600 200" width="100%" role="img" aria-label="Revenue chart">
      ${area(mm, '#A47551')}
      ${area(mm2, '#7E9C88')}
    </svg>
    <small class="mut"><span style="color:#A47551">●</span> Revenue &nbsp; <span style="color:#7E9C88">●</span> MRR</small>
  </div>
  <div class="card">
    <h3>Subscription status</h3>
    <div style="display:flex;gap:16px;align-items:center;margin-top:12px;flex-wrap:wrap">
      <div style="width:120px;height:120px;border-radius:50%;background:conic-gradient(${cg});mask:radial-gradient(circle 36px,transparent 98%,#000);-webkit-mask:radial-gradient(circle 36px,transparent 98%,#000)"></div>
      <div>${ST.map((s, i) => `<p><span style="color:${cl[i]}">●</span> ${s} <b>${cn[i]}</b></p>`).join('')}</div>
    </div>
  </div>
</div>

<div class="g g2">
  <div class="card aic">
    <h3>AI Insights</h3>
    ${[
      ['4 invoices likely to become overdue this week', 'Send reminders', 'Reminders queued for 4 customers'],
      ['Churn risk: 3 customers show falling usage', 'Review accounts', 'Opened churn-risk report'],
      ['Annual upgrades could add $6.2k MRR', 'See candidates', 'Listed 5 upgrade candidates']
    ].map(x => `<div style="display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 0;border-bottom:1px solid var(--s2)"><span>${x[0]}</span><button class="btn o" onclick="toast('${x[2]}')">${x[1]}</button></div>`).join('')}
  </div>
  <div class="card">
    <h3>Financial summary</h3>
    <table style="margin-top:8px">
      <tr><td>Paid</td><td><span class="bd g">Paid</span></td><td><b>${M(paid)}</b></td></tr>
      <tr><td>Outstanding</td><td><span class="bd g">Confirmed</span></td><td><b>${M(out)}</b></td></tr>
      <tr><td>Overdue</td><td><span class="bd r">Overdue</span></td><td><b>${M(odA)}</b></td></tr>
    </table>
  </div>
</div>

<div class="g g2">
  <div class="card">
    <h3>Recent invoices</h3>
    ${D.invoices.slice(0, 4).map(i => `<p style="display:flex;justify-content:space-between;padding:8px 0">${i.n} · ${i.c} <span>${M(i.amt)} <span class="bd ${i.st === 'Paid' ? 'g' : (ds(i) === 'Overdue' ? 'r' : 'g')}">${ds(i)}</span></span></p>`).join('')}
  </div>
  <div class="card">
    <h3>Upcoming renewals</h3>
    ${D.subs.filter(s => s.st === 'Active' || s.st === 'Confirmed').map(s => `<p style="display:flex;justify-content:space-between;padding:8px 0">${s.c} <span class="mut">${s.next} · ${M(s.amt)}</span></p>`).join('')}
  </div>
</div>`;

  return [actBtn, content];
}
