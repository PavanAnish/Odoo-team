/**
 * Module 2: Product Management
 * Professional Enterprise SaaS Product Management Section
 * Handles listing, server-side filtering, search, pagination,
 * creation, editing, variants with additional pricing, and archival.
 */

import { M, B, toast, modal, X, confirmD, D } from '../shared/store.js';
import { ProductAPI } from './api.js';

// Local UI state for Product Management
const productState = {
  viewMode: 'table', // 'table' | 'grid'
  search: '',
  productType: 'all', // 'all' | 'service' | 'consu'
  activeFilter: 'active', // 'active' | 'archived' | 'all'
  sortBy: 'name',
  sortDir: 'asc',
  page: 1,
  limit: 25,
  isLoading: false,
  backendConnected: false,
  lastError: null,
  products: [],
  totalCount: 0,
  canViewCost: true,
  canEdit: true,
  selectedProduct: null
};

// Seed initial fallback cache from shared data so interface is responsive immediately
function getInitialProducts() {
  return (D.products || []).map((p, idx) => ({
    id: p.id || idx + 1,
    name: p.name,
    sku: `SKU-${1000 + (p.id || idx + 1)}`,
    type: p.type === 'Software' || p.type === 'Service' ? 'service' : 'consu',
    type_label: p.type || 'Service',
    price: Number(p.price || 0),
    cost: Number(p.cost || 0),
    margin: p.price ? Math.round(((p.price - p.cost) / p.price) * 100) : 0,
    notes: p.notes || '',
    active: true,
    variant_count: (p.variants || []).length || 1,
    variants: (p.variants || []).map((v, vIdx) => {
      const extra = Number(v.x || v.price_extra || 0);
      const base = Number(p.price || 0);
      return {
        id: vIdx + 1,
        attribute_summary: v.a || v.attribute_name || 'Standard',
        base_price: base,
        extra_price: extra,
        final_price: roundCurrency(base + extra)
      };
    })
  }));
}

function roundCurrency(val) {
  return Math.round((Number(val) + Number.EPSILON) * 100) / 100;
}

// -----------------------------------------------------------------------------
// Data Fetching & Synchronization
// -----------------------------------------------------------------------------
async function loadProducts(silent = false) {
  if (!silent) {
    productState.isLoading = true;
    renderProductsTbody();
  }

  const res = await ProductAPI.list({
    search: productState.search,
    product_type: productState.productType,
    active_filter: productState.activeFilter,
    sort_by: productState.sortBy,
    sort_dir: productState.sortDir,
    page: productState.page,
    limit: productState.limit
  });

  productState.isLoading = false;

  if (res.success && res.data) {
    productState.backendConnected = true;
    productState.lastError = null;
    productState.products = res.data.products || [];
    productState.totalCount = res.data.total || productState.products.length;
    productState.canViewCost = res.data.can_view_cost ?? true;
    productState.canEdit = res.data.can_edit ?? true;
    if (D && D.products) {
      D.products = productState.products.map(p => ({
        id: p.id,
        name: p.name,
        type: p.type_label || p.type || 'Service',
        price: p.price || 0,
        cost: p.cost || 0,
        notes: p.notes || '',
        variants: p.variants || []
      }));
    }
  } else {
    productState.backendConnected = false;
    productState.lastError = res.message || 'Cannot communicate with Odoo backend.';

    // Apply local client-side search/filter on existing cached dataset
    let local = getInitialProducts();
    if (productState.activeFilter === 'archived') {
      local = local.filter(p => !p.active);
    } else if (productState.activeFilter === 'active') {
      local = local.filter(p => p.active);
    }

    if (productState.productType !== 'all') {
      local = local.filter(p => p.type === productState.productType);
    }

    if (productState.search.trim()) {
      const q = productState.search.toLowerCase();
      local = local.filter(p => p.name.toLowerCase().includes(q) || (p.sku && p.sku.toLowerCase().includes(q)));
    }

    productState.products = local;
    productState.totalCount = local.length;
  }

  renderProductsTbody();
}

// -----------------------------------------------------------------------------
// Main View Renderer
// -----------------------------------------------------------------------------
export function productsView() {
  // Trigger initial asynchronous data load
  setTimeout(() => loadProducts(true), 10);

  const actionButton = `<button class="btn" onclick="window.productModule.openCreateModal()">+ Add product</button>`;

  const content = `
<div id="products-container">
  <!-- System / Backend Status Indicator Banner -->
  <div id="product-conn-banner" style="margin-bottom: 14px">
    ${renderConnectionBanner()}
  </div>

  <!-- Search, Filter & Controls Toolbar -->
  <div class="card" style="padding: 14px 18px; margin-bottom: 16px">
    <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center; justify-content:space-between">
      <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center; flex:1">
        <!-- Search Input -->
        <div style="position:relative; min-width: 260px; max-width: 360px; flex: 1">
          <input id="prod-search-input"
                 placeholder="Search by product name or SKU…"
                 value="${escapeHtml(productState.search)}"
                 oninput="window.productModule.handleSearch(this.value)"
                 style="padding-left: 12px; height: 38px;">
        </div>

        <!-- Product Type Filter -->
        <select id="prod-type-select"
                style="width:auto; height: 38px;"
                onchange="window.productModule.handleTypeFilter(this.value)"
                aria-label="Filter by Product Type">
          <option value="all" ${productState.productType === 'all' ? 'selected' : ''}>All Types</option>
          <option value="service" ${productState.productType === 'service' ? 'selected' : ''}>Services</option>
          <option value="consu" ${productState.productType === 'consu' ? 'selected' : ''}>Consumables</option>
        </select>

        <!-- Status Filter -->
        <select id="prod-status-select"
                style="width:auto; height: 38px;"
                onchange="window.productModule.handleStatusFilter(this.value)"
                aria-label="Filter by Status">
          <option value="active" ${productState.activeFilter === 'active' ? 'selected' : ''}>Active only</option>
          <option value="archived" ${productState.activeFilter === 'archived' ? 'selected' : ''}>Archived only</option>
          <option value="all" ${productState.activeFilter === 'all' ? 'selected' : ''}>All status</option>
        </select>

        ${productState.search || productState.productType !== 'all' || productState.activeFilter !== 'active'
          ? `<button class="btn o" style="height:38px; padding:0 12px;" onclick="window.productModule.clearFilters()">Clear filters</button>`
          : ''}
      </div>

      <!-- View Switcher (Table vs Grid) -->
      <div style="display:flex; gap:6px; align-items:center">
        <button class="btn o ${productState.viewMode === 'table' ? 'ai' : ''}"
                style="height:38px; padding:0 14px;"
                onclick="window.productModule.setViewMode('table')">
          ☰ Table
        </button>
        <button class="btn o ${productState.viewMode === 'grid' ? 'ai' : ''}"
                style="height:38px; padding:0 14px;"
                onclick="window.productModule.setViewMode('grid')">
          ⊞ Grid
        </button>
      </div>
    </div>
  </div>

  <!-- Product Listing Area -->
  <div id="product-list-view">
    ${renderProductListingHTML()}
  </div>
</div>`;

  return [actionButton, content];
}

function renderConnectionBanner() {
  if (productState.backendConnected) {
    return `
<div style="background:#7E9C8818; border:1px solid #7E9C8866; border-radius:12px; padding:10px 14px; font-size:13px; display:flex; justify-content:space-between; align-items:center">
  <span style="color:#3e634c">
    ● <b>Odoo 17.0 Backend Connected:</b> Operating with live database records & transactions.
  </span>
  <span class="bd g">Live Database</span>
</div>`;
  }

  return `
<div style="background:#D9A44115; border:1px solid #D9A44155; border-radius:12px; padding:10px 14px; font-size:13px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px">
  <span style="color:#7d5907">
    ℹ <b>Odoo Backend Status:</b> Odoo server is not running on port 8069. Product catalog is operating in local verified mode. To enable dynamic database transactions, start Odoo via <code>odoo-bin -c config/odoo.conf</code>.
  </span>
  <button class="btn o" style="font-size:12px; padding:4px 10px;" onclick="window.productModule.retryConnection()">Retry Connection</button>
</div>`;
}

function renderProductListingHTML() {
  if (productState.isLoading) {
    return `
<div class="card tp tw rt">
  <div style="padding:40px; text-align:center">
    <div class="sk" style="height:40px; margin-bottom:8px"></div>
    <div class="sk" style="height:40px; margin-bottom:8px"></div>
    <div class="sk" style="height:40px"></div>
    <p class="mut" style="margin-top:12px">Loading products from backend...</p>
  </div>
</div>`;
  }

  const items = productState.products || [];

  if (items.length === 0) {
    return `
<div class="card empty">
  <b>No products found</b>
  <p class="mut">No catalog items matched your query. Try resetting filters or create a new product.</p>
  <button class="btn" style="margin-top:14px" onclick="window.productModule.openCreateModal()">+ Add Product</button>
</div>`;
  }

  if (productState.viewMode === 'grid') {
    return `
<div class="g g4">
  ${items.map(p => `
  <div class="card" style="display:flex; flex-direction:column; justify-content:space-between; cursor:pointer;" onclick="window.productModule.openDetailModal(${p.id})">
    <div>
      <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:6px">
        <span class="bd ${p.type === 'service' ? 'g' : 'a'}">${escapeHtml(p.type_label || (p.type === 'service' ? 'Service' : 'Consumable'))}</span>
        <span class="bd ${p.active ? 'g' : 'r'}">${p.active ? 'Active' : 'Archived'}</span>
      </div>
      <h3 style="font-size:16px; margin:4px 0">${escapeHtml(p.name)}</h3>
      <p class="mut" style="font-size:12px; margin-bottom:8px">${p.sku ? `SKU: ${escapeHtml(p.sku)}` : 'No SKU'} · ${p.variant_count || 1} variant(s)</p>
      ${p.notes ? `<p class="mut" style="font-size:12px; margin-bottom:12px">${escapeHtml(p.notes)}</p>` : ''}
    </div>
    <div style="border-top:1px solid var(--bd); padding-top:10px; margin-top:10px">
      <div style="display:flex; justify-content:space-between; align-items:baseline">
        <span class="kv" style="font-size:20px">${M(p.price)}</span>
        ${productState.canViewCost && p.cost !== null ? `<small class="mut">Cost ${M(p.cost)} (${p.margin}% margin)</small>` : ''}
      </div>
      <div style="display:flex; gap:6px; margin-top:12px" onclick="event.stopPropagation()">
        <button class="btn o" style="flex:1; padding:6px 8px; font-size:12px" onclick="window.productModule.openEditModal(${p.id})">Edit</button>
        ${p.active
          ? `<button class="btn o" style="padding:6px 8px; font-size:12px" onclick="window.productModule.confirmArchive(${p.id}, '${escapeJs(p.name)}')">Archive</button>`
          : `<button class="btn o" style="padding:6px 8px; font-size:12px" onclick="window.productModule.unarchive(${p.id})">Restore</button>`}
      </div>
    </div>
  </div>`).join('')}
</div>`;
  }

  // Table View
  return `
<div class="card tp tw rt">
  <table>
    <thead>
      <tr>
        <th onclick="window.productModule.handleSort('name')">Product Name ${renderSortIndicator('name')}</th>
        <th onclick="window.productModule.handleSort('default_code')">SKU / Code ${renderSortIndicator('default_code')}</th>
        <th>Type</th>
        <th onclick="window.productModule.handleSort('list_price')">Sales Price ${renderSortIndicator('list_price')}</th>
        ${productState.canViewCost ? `<th>Cost Price</th><th>Margin</th>` : ''}
        <th>Variants</th>
        <th>Status</th>
        <th style="text-align:right">Actions</th>
      </tr>
    </thead>
    <tbody>
      ${items.map(p => `
      <tr class="r" onclick="window.productModule.openDetailModal(${p.id})">
        <td data-l="Product Name"><b>${escapeHtml(p.name)}</b></td>
        <td data-l="SKU">${p.sku ? escapeHtml(p.sku) : '<span class="mut">—</span>'}</td>
        <td data-l="Type"><span class="bd ${p.type === 'service' ? 'g' : 'a'}">${escapeHtml(p.type_label || (p.type === 'service' ? 'Service' : 'Consumable'))}</span></td>
        <td data-l="Sales Price"><b>${M(p.price)}</b></td>
        ${productState.canViewCost ? `
        <td data-l="Cost Price">${p.cost !== null ? M(p.cost) : '<span class="mut">—</span>'}</td>
        <td data-l="Margin">${p.margin !== null ? `${p.margin}%` : '<span class="mut">—</span>'}</td>` : ''}
        <td data-l="Variants"><span class="bd s">${p.variant_count || 1}</span></td>
        <td data-l="Status"><span class="bd ${p.active ? 'g' : 'r'}">${p.active ? 'Active' : 'Archived'}</span></td>
        <td style="text-align:right" onclick="event.stopPropagation()">
          <button class="ib" title="View details" onclick="window.productModule.openDetailModal(${p.id})">👁</button>
          <button class="ib" title="Edit product" onclick="window.productModule.openEditModal(${p.id})">✎</button>
          ${p.active
            ? `<button class="ib" title="Archive product" onclick="window.productModule.confirmArchive(${p.id}, '${escapeJs(p.name)}')">📁</button>`
            : `<button class="ib" title="Restore product" onclick="window.productModule.unarchive(${p.id})">↺</button>`}
        </td>
      </tr>`).join('')}
    </tbody>
  </table>
</div>
<div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px; font-size:13px" class="mut">
  <span>Showing ${items.length} of ${productState.totalCount} product(s)</span>
</div>`;
}

function renderSortIndicator(field) {
  if (productState.sortBy !== field) return '';
  return productState.sortDir === 'asc' ? ' ↑' : ' ↓';
}

function renderProductsTbody() {
  if (typeof document === 'undefined') return;
  const container = document.getElementById('product-list-view');
  if (container) {
    container.innerHTML = renderProductListingHTML();
  }
  const banner = document.getElementById('product-conn-banner');
  if (banner) {
    banner.innerHTML = renderConnectionBanner();
  }
}

// -----------------------------------------------------------------------------
// Product Creation & Edit Dialogs
// -----------------------------------------------------------------------------
function openProductFormModal(product = null) {
  const isEdit = Boolean(product && product.id);
  const title = isEdit ? `Edit Product: ${escapeHtml(product.name)}` : 'Create New Product';

  const initialVariants = (product && product.variants) ? product.variants : [];

  const variantRowHtml = (v = { a: '', x: 0 }) => `
<div class="vr variant-config-row" style="display:flex; gap:8px; margin-bottom:8px">
  <input placeholder="Attribute e.g. Tier: Pro or Brand: Odoo" value="${escapeHtml(v.attribute_summary || v.a || '')}" class="v-attr-name" style="flex:1">
  <div style="position:relative; width:130px; flex:none">
    <input type="number" step="0.01" placeholder="+ Extra (₹)" value="${v.extra_price !== undefined ? v.extra_price : (v.x || 0)}" class="v-attr-extra" oninput="window.productModule.recalcVariantPreview()">
  </div>
  <button type="button" class="btn o" onclick="this.parentNode.remove(); window.productModule.recalcVariantPreview()" aria-label="Remove variant">✕</button>
</div>`;

  const modalHtml = `
<h2>${title}</h2>
<form id="product-manage-form" onsubmit="event.preventDefault(); window.productModule.submitProductForm(${isEdit ? product.id : 'null'});">
  <label for="pf-name">Product Name <span style="color:var(--te)">*</span></label>
  <input id="pf-name" required placeholder="e.g. Recurra Pro Seat" value="${isEdit ? escapeHtml(product.name) : ''}">
  <span class="er" id="pf-name-error"></span>

  <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:8px">
    <div>
      <label for="pf-sku">SKU / Internal Reference</label>
      <input id="pf-sku" placeholder="e.g. SKU-PRO-01" value="${isEdit && product.sku ? escapeHtml(product.sku) : ''}">
    </div>
    <div>
      <label for="pf-type">Product Type</label>
      <select id="pf-type">
        <option value="service" ${isEdit && product.type === 'service' ? 'selected' : ''}>Service (Subscription License / Support)</option>
        <option value="consu" ${isEdit && product.type === 'consu' ? 'selected' : ''}>Consumable (Physical Goods)</option>
      </select>
    </div>
  </div>

  <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:8px">
    <div>
      <label for="pf-price">Sales Price <span style="color:var(--te)">*</span></label>
      <input id="pf-price" type="number" step="0.01" min="0" required placeholder="0.00" value="${isEdit ? product.price : '0.00'}" oninput="window.productModule.recalcMargin()">
      <span class="er" id="pf-price-error"></span>
    </div>
    <div>
      <label for="pf-cost">Cost Price</label>
      <input id="pf-cost" type="number" step="0.01" min="0" placeholder="0.00" value="${isEdit && product.cost !== null ? product.cost : '0.00'}" oninput="window.productModule.recalcMargin()">
    </div>
  </div>

  <div class="card aic" style="margin-top:10px; padding:10px 14px; font-size:13px">
    Estimated Margin: <b id="pf-margin-display">—</b>
  </div>

  <label for="pf-notes">Sales Description & Notes</label>
  <textarea id="pf-notes" rows="2" placeholder="Optional notes visible on quotations and invoices">${isEdit ? escapeHtml(product.notes || '') : ''}</textarea>

  <!-- Variants Configuration Section -->
  <div style="margin-top:16px; border-top:1px solid var(--bd); padding-top:14px">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px">
      <label style="margin:0; font-weight:600">Product Variants & Price Adjustments</label>
      <button type="button" class="btn o" style="font-size:12px; padding:4px 10px;" onclick="window.productModule.addVariantRow()">+ Add Variant</button>
    </div>
    <small class="mut" style="display:block; margin-bottom:10px">
      Define attribute values and extra price. The final price equals Base Price + Extra Price (e.g., Base ₹2,000 + Extra ₹560 = Final ₹2,560).
    </small>
    <div id="pf-variants-container">
      ${initialVariants.map(v => variantRowHtml(v)).join('')}
    </div>
    <div id="pf-variant-calc-preview" style="background:var(--s1); padding:8px 12px; border-radius:10px; font-size:12px; margin-top:8px; display:none">
    </div>
  </div>

  <div class="ft">
    <button type="button" class="btn o" onclick="X()">Discard</button>
    <button type="submit" class="btn" id="pf-submit-btn">${isEdit ? 'Save Changes' : 'Create Product'}</button>
  </div>
</form>`;

  modal(modalHtml, false);
  recalcMargin();
  recalcVariantPreview();
}

function recalcMargin() {
  const pInput = document.getElementById('pf-price');
  const cInput = document.getElementById('pf-cost');
  const display = document.getElementById('pf-margin-display');
  if (!pInput || !cInput || !display) return;

  const price = parseFloat(pInput.value) || 0;
  const cost = parseFloat(cInput.value) || 0;

  if (price > 0) {
    const diff = price - cost;
    const pct = Math.round((diff / price) * 100);
    display.textContent = `${M(diff)} (${pct}%)`;
    display.style.color = diff >= 0 ? '#4f7360' : '#C4674A';
  } else {
    display.textContent = '—';
    display.style.color = 'inherit';
  }
}

function recalcVariantPreview() {
  const pInput = document.getElementById('pf-price');
  const container = document.getElementById('pf-variants-container');
  const preview = document.getElementById('pf-variant-calc-preview');
  if (!pInput || !container || !preview) return;

  const basePrice = parseFloat(pInput.value) || 0;
  const rows = container.querySelectorAll('.variant-config-row');

  if (rows.length === 0) {
    preview.style.display = 'none';
    return;
  }

  const previews = [];
  rows.forEach(r => {
    const name = r.querySelector('.v-attr-name')?.value.trim();
    const extra = parseFloat(r.querySelector('.v-attr-extra')?.value) || 0;
    if (name) {
      const finalPrice = roundCurrency(basePrice + extra);
      previews.push(`<b>${escapeHtml(name)}</b>: Base ${M(basePrice)} + Extra ${M(extra)} = <b>${M(finalPrice)}</b>`);
    }
  });

  if (previews.length > 0) {
    preview.style.display = 'block';
    preview.innerHTML = `<span><b>Calculated Variant Prices:</b><br>${previews.join('<br>')}</span>`;
  } else {
    preview.style.display = 'none';
  }
}

// -----------------------------------------------------------------------------
// Product Details Drawer
// -----------------------------------------------------------------------------
function openDetailModal(productId) {
  const p = productState.products.find(x => x.id === productId);
  if (!p) return;

  const variantsList = p.variants && p.variants.length > 0
    ? p.variants.map(v => `
      <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--s2)">
        <span>${escapeHtml(v.attribute_summary || 'Variant')}</span>
        <span>${v.extra_price ? `+${M(v.extra_price)} → ` : ''}<b>${M(v.final_price || p.price)}</b></span>
      </div>`).join('')
    : '<p class="mut">No attributes or variants configured.</p>';

  const content = `
<h2>${escapeHtml(p.name)}</h2>
<p class="mut">${p.sku ? `SKU: ${escapeHtml(p.sku)}` : 'No SKU assigned'} · <span class="bd ${p.type === 'service' ? 'g' : 'a'}">${escapeHtml(p.type_label || p.type)}</span> · <span class="bd ${p.active ? 'g' : 'r'}">${p.active ? 'Active' : 'Archived'}</span></p>

<div class="card aic" style="margin:16px 0; display:flex; justify-content:space-around; text-align:center">
  <div>
    <small class="mut">Sales Price</small>
    <div class="kv" style="font-size:22px">${M(p.price)}</div>
  </div>
  ${productState.canViewCost && p.cost !== null ? `
  <div>
    <small class="mut">Cost Price</small>
    <div class="kv" style="font-size:22px">${M(p.cost)}</div>
  </div>
  <div>
    <small class="mut">Margin</small>
    <div class="kv" style="font-size:22px; color:#4f7360">${p.margin}%</div>
  </div>` : ''}
</div>

${p.notes ? `
<div style="margin-bottom:16px">
  <h3>Description</h3>
  <p class="mut" style="margin-top:4px">${escapeHtml(p.notes)}</p>
</div>` : ''}

<h3>Configured Variants & Pricing</h3>
<small class="mut" style="display:block; margin-bottom:8px">Each variant price calculates dynamically as Base Price + Extra Price:</small>
<div style="background:var(--s1); border-radius:12px; padding:12px; margin-bottom:16px">
  ${variantsList}
</div>

<div class="ft">
  <button class="btn o" onclick="X()">Close</button>
  <button class="btn o" onclick="X(); window.productModule.openEditModal(${p.id})">Edit</button>
  ${p.active
    ? `<button class="btn d" onclick="X(); window.productModule.confirmArchive(${p.id}, '${escapeJs(p.name)}')">Archive Product</button>`
    : `<button class="btn" onclick="X(); window.productModule.unarchive(${p.id})">Restore Product</button>`}
</div>`;

  modal(content, true); // Drawer style
}

// -----------------------------------------------------------------------------
// Form Submissions and Backend Mutations
// -----------------------------------------------------------------------------
async function submitProductForm(productId) {
  const submitBtn = document.getElementById('pf-submit-btn');
  const nameInput = document.getElementById('pf-name');
  const priceInput = document.getElementById('pf-price');
  const costInput = document.getElementById('pf-cost');
  const typeSelect = document.getElementById('pf-type');
  const skuInput = document.getElementById('pf-sku');
  const notesInput = document.getElementById('pf-notes');

  // Clear previous errors
  document.getElementById('pf-name-error').textContent = '';
  document.getElementById('pf-price-error').textContent = '';

  const name = nameInput.value.trim();
  const price = parseFloat(priceInput.value);
  const cost = parseFloat(costInput.value) || 0.0;
  const detailedType = typeSelect.value;
  const sku = skuInput.value.trim();
  const notes = notesInput.value.trim();

  let hasError = false;
  if (!name) {
    document.getElementById('pf-name-error').textContent = 'Product name is required.';
    hasError = true;
  }

  if (isNaN(price) || price < 0) {
    document.getElementById('pf-price-error').textContent = 'Please enter a valid non-negative sales price.';
    hasError = true;
  }

  if (hasError) return;

  // Extract variants from form rows
  const variantRows = document.querySelectorAll('#pf-variants-container .variant-config-row');
  const variants = [];
  variantRows.forEach(r => {
    const attr = r.querySelector('.v-attr-name')?.value.trim();
    const extra = parseFloat(r.querySelector('.v-attr-extra')?.value) || 0.0;
    if (attr) {
      variants.push({
        attribute_name: attr,
        a: attr,
        price_extra: extra,
        x: extra
      });
    }
  });

  const payload = {
    name,
    list_price: price,
    standard_price: cost,
    detailed_type: detailedType,
    default_code: sku || false,
    description_sale: notes || false,
    variants
  };

  // Prevent duplicate submissions
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving to Database...';
  }

  let res;
  if (productId) {
    res = await ProductAPI.update(productId, payload);
  } else {
    res = await ProductAPI.create(payload);
  }

  if (submitBtn) {
    submitBtn.disabled = false;
    submitBtn.textContent = productId ? 'Save Changes' : 'Create Product';
  }

  if (res.success) {
    X();
    toast(res.data?.message || (productId ? 'Product updated successfully.' : 'Product created successfully.'));
    await loadProducts();
  } else {
    // If backend is offline, update local verified cache so user can verify functionality
    if (res.isOffline) {
      updateLocalCache(productId, payload);
      X();
      toast(`[Local Verification] Product ${productId ? 'updated' : 'created'} in memory cache. Start Odoo for database persistence.`);
      renderProductsTbody();
      return;
    }

    toast(`Error: ${res.message}`);
  }
}

function updateLocalCache(productId, payload) {
  const margin = payload.list_price > 0
    ? Math.round(((payload.list_price - payload.standard_price) / payload.list_price) * 100)
    : 0;

  const variants = (payload.variants || []).map((v, i) => ({
    id: i + 1,
    attribute_summary: v.attribute_name,
    base_price: payload.list_price,
    extra_price: v.price_extra,
    final_price: roundCurrency(payload.list_price + v.price_extra)
  }));

  if (productId) {
    const idx = productState.products.findIndex(p => p.id === productId);
    if (idx !== -1) {
      productState.products[idx] = {
        ...productState.products[idx],
        name: payload.name,
        sku: payload.default_code,
        price: payload.list_price,
        cost: payload.standard_price,
        margin,
        type: payload.detailed_type,
        type_label: payload.detailed_type === 'service' ? 'Service' : 'Consumable',
        notes: payload.description_sale,
        variant_count: variants.length || 1,
        variants: variants.length ? variants : productState.products[idx].variants
      };
    }
  } else {
    const newId = Math.max(0, ...productState.products.map(p => p.id)) + 1;
    productState.products.unshift({
      id: newId,
      name: payload.name,
      sku: payload.default_code || `SKU-${1000 + newId}`,
      price: payload.list_price,
      cost: payload.standard_price,
      margin,
      type: payload.detailed_type,
      type_label: payload.detailed_type === 'service' ? 'Service' : 'Consumable',
      notes: payload.description_sale,
      active: true,
      variant_count: variants.length || 1,
      variants
    });
    productState.totalCount += 1;
  }
}

function confirmArchive(productId, productName) {
  confirmD(
    `Are you sure you want to archive '${escapeHtml(productName)}'? It will no longer be available for new subscriptions or quotations.`,
    async () => {
      const res = await ProductAPI.archive(productId);
      if (res.success) {
        toast(res.data?.message || 'Product archived successfully.');
        await loadProducts();
      } else {
        if (res.isOffline) {
          const p = productState.products.find(x => x.id === productId);
          if (p) p.active = false;
          toast(`[Local Verification] Product archived.`);
          renderProductsTbody();
          return;
        }
        toast(`Error: ${res.message}`);
      }
    },
    'Archive Product',
    'd'
  );
}

async function unarchive(productId) {
  const res = await ProductAPI.unarchive(productId);
  if (res.success) {
    toast(res.data?.message || 'Product restored successfully.');
    await loadProducts();
  } else {
    if (res.isOffline) {
      const p = productState.products.find(x => x.id === productId);
      if (p) p.active = true;
      toast(`[Local Verification] Product restored.`);
      renderProductsTbody();
      return;
    }
    toast(`Error: ${res.message}`);
  }
}

// -----------------------------------------------------------------------------
// Helper Utilities
// -----------------------------------------------------------------------------
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeJs(str) {
  if (!str) return '';
  return String(str).replace(/'/g, "\\'").replace(/"/g, '\\"');
}

// -----------------------------------------------------------------------------
// Expose on Window for Interactive UI Handlers
// -----------------------------------------------------------------------------
if (typeof window !== 'undefined') {
  window.productModule = {
    handleSearch(val) {
      productState.search = val;
      productState.page = 1;
      loadProducts();
    },

    handleTypeFilter(val) {
      productState.productType = val;
      productState.page = 1;
      loadProducts();
    },

    handleStatusFilter(val) {
      productState.activeFilter = val;
      productState.page = 1;
      loadProducts();
    },

    handleSort(field) {
      if (productState.sortBy === field) {
        productState.sortDir = productState.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        productState.sortBy = field;
        productState.sortDir = 'asc';
      }
      loadProducts();
    },

    clearFilters() {
      productState.search = '';
      productState.productType = 'all';
      productState.activeFilter = 'active';
      const sInput = document.getElementById('prod-search-input');
      const tSelect = document.getElementById('prod-type-select');
      const stSelect = document.getElementById('prod-status-select');
      if (sInput) sInput.value = '';
      if (tSelect) tSelect.value = 'all';
      if (stSelect) stSelect.value = 'active';
      loadProducts();
    },

    setViewMode(mode) {
      productState.viewMode = mode;
      renderProductsTbody();
    },

    retryConnection() {
      toast('Re-checking Odoo backend service...');
      loadProducts();
    },

    openCreateModal() {
      openProductFormModal(null);
    },

    openEditModal(id) {
      const p = productState.products.find(x => x.id === id);
      if (p) openProductFormModal(p);
    },

    openDetailModal(id) {
      openDetailModal(id);
    },

    addVariantRow() {
      const container = document.getElementById('pf-variants-container');
      if (container) {
        const div = document.createElement('div');
        div.className = 'vr variant-config-row';
        div.style.cssText = 'display:flex; gap:8px; margin-bottom:8px';
        div.innerHTML = `
          <input placeholder="Attribute e.g. Tier: Pro or Brand: Odoo" class="v-attr-name" style="flex:1">
          <div style="position:relative; width:130px; flex:none">
            <input type="number" step="0.01" placeholder="+ Extra (₹)" value="0.00" class="v-attr-extra" oninput="window.productModule.recalcVariantPreview()">
          </div>
          <button type="button" class="btn o" onclick="this.parentNode.remove(); window.productModule.recalcVariantPreview()" aria-label="Remove variant">✕</button>
        `;
        container.appendChild(div);
        recalcVariantPreview();
      }
    },

    recalcMargin,
    recalcVariantPreview,
    submitProductForm,
    confirmArchive,
    unarchive
  };
}
