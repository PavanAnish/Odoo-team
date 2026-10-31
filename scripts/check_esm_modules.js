const fs = require('fs');
const vm = require('vm');

const files = [
  'admin/app.js',
  'admin/shared/store.js',
  'admin/dashboard/dashboard.js',
  'admin/customers/customers.js',
  'admin/products/products.js',
  'admin/products/api.js',
  'admin/plans/plans.js',
  'admin/taxes/taxes.js',
  'admin/discounts/discounts.js',
  'admin/quotations/quotations.js',
  'admin/subscriptions/subscriptions.js',
  'admin/invoices/invoices.js'
];

let hasError = false;
for (const f of files) {
  try {
    const code = fs.readFileSync(f, 'utf8');
    const m = new vm.SourceTextModule(code, { identifier: f });
    console.log('OK:', f);
  } catch (e) {
    console.error('ERROR in', f, ':', e.message);
    hasError = true;
  }
}
if (hasError) process.exit(1);
