import { D, S, M, B, confirmD, toast, form } from '../shared/store.js';
import { convertQuotation } from '../shared/api.js';
import { loadData } from '../shared/store.js';

export const tot = q => {
  const product = D.products.find(p => p.name === q.product) || { price: 0 };
  return (product.price * q.qty * (1 - q.disc / 100) * (1 + q.tax / 100)).toFixed(2);
};

export const T = ['Standard annual', 'Onboarding bundle', 'Team starter'];

export function quo() {
  const isTemplates = (S.qt || 'Quotations') === 'Templates';
  const headerTabs = `<div class="tabs">${['Quotations', 'Templates'].map(x => `<button class="${(S.qt || 'Quotations') === x ? 'on' : ''}" onclick="S.qt='${x}';R()">${x}</button>`).join('')}</div>`;
  const viewContent = isTemplates ?
    `<div class="g g4">${T.map(t => `<div class="card"><b>${t}</b><p class="mut" style="margin:6px 0 12px">Prefilled plan, products and tax.</p><button class="btn o" onclick="form('quotes')">Use template</button></div>`).join('')}</div>` :
    `<div class="card tp tw rt"><table><thead><tr><th>Quote</th><th>Customer</th><th>Plan</th><th>Total</th><th>Status</th><th></th></tr></thead><tbody>${D.quotes.map(q => `<tr><td data-l="Quote">${q.n}</td><td data-l="Customer">${q.customer}</td><td data-l="Plan">${q.plan}</td><td data-l="Total">${M(tot(q))}</td><td data-l="Status">${B(q.st)}</td><td>${q.st !== 'Converted' ? `<button class="btn" onclick="conv(${q.id})">Convert to Subscription</button>` : ''}</td></tr>`).join('')}</tbody></table></div>`;

  return [
    `<button class="btn" onclick="form('quotes')">+ Create quotation</button>`,
    headerTabs + viewContent
  ];
}

export async function conv(id) {
  const q = D.quotes.find(x => x.id === id);
  if (!q) return toast('Quotation not found');
  confirmD(`Convert ${q.n} to a subscription for ${q.customer}?`, async () => {
    try {
      const r = await convertQuotation(q.id);
      if (r && r.error) {
        toast('Error: ' + r.error);
      } else {
        await loadData();
        toast('Subscription created from ' + q.n);
        if (typeof window.R === 'function') window.R();
      }
    } catch (e) {
      toast('Error: ' + e.message);
    }
  }, 'Convert');
}
