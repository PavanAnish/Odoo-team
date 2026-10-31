/**
 * Product Management API Client
 * Interfaces with native Odoo 17 JSON-RPC / REST endpoints:
 * /subscription/catalog/products/list
 * /subscription/catalog/products/get
 * /subscription/catalog/products/create
 * /subscription/catalog/products/update
 * /subscription/catalog/products/archive
 * /subscription/catalog/products/unarchive
 */

const BASE_URL = (typeof window !== 'undefined' && window.location && (window.location.origin || window.location.host || '').includes(':8000'))
  ? 'http://127.0.0.1:8069'
  : (typeof window !== 'undefined' && window.location && window.location.origin ? window.location.origin : '');

async function postJson(endpoint, params = {}) {
  const url = `${BASE_URL}${endpoint}`;
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 6000);

    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'call',
        params: params,
        id: Math.floor(Math.random() * 100000)
      }),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      if (res.status === 401 || res.status === 403) {
        return {
          success: false,
          errorType: 'access_denied',
          message: 'Access denied: You do not have permission to perform this product operation.'
        };
      }
      return {
        success: false,
        errorType: 'http_error',
        message: `HTTP ${res.status}: Server returned an error.`
      };
    }

    const json = await res.json();
    if (json.error) {
      return {
        success: false,
        errorType: 'odoo_error',
        message: json.error.data?.message || json.error.message || 'Odoo RPC error.'
      };
    }

    const result = json.result || json;
    if (result.status === 'error') {
      return {
        success: false,
        errorType: result.error_type || 'server_error',
        message: result.message || 'Operation failed.'
      };
    }

    return {
      success: true,
      data: result
    };
  } catch (err) {
    const isTimeout = err.name === 'AbortError';
    return {
      success: false,
      errorType: 'connection_failed',
      message: isTimeout
        ? 'Request timed out after 6 seconds connecting to Odoo backend.'
        : 'Cannot reach Odoo backend server (port 8069). Backend service is not currently running.',
      isOffline: true
    };
  }
}

export const ProductAPI = {
  async list({ search = '', product_type = 'all', active_filter = 'active', sort_by = 'name', sort_dir = 'asc', page = 1, limit = 50 } = {}) {
    return postJson('/subscription/catalog/products/list', {
      search,
      product_type,
      active_filter,
      sort_by,
      sort_dir,
      page,
      limit
    });
  },

  async get(productId) {
    return postJson('/subscription/catalog/products/get', { product_id: productId });
  },

  async create(productData) {
    return postJson('/subscription/catalog/products/create', productData);
  },

  async update(productId, productData) {
    return postJson('/subscription/catalog/products/update', {
      product_id: productId,
      ...productData
    });
  },

  async archive(productId) {
    return postJson('/subscription/catalog/products/archive', { product_id: productId });
  },

  async unarchive(productId) {
    return postJson('/subscription/catalog/products/unarchive', { product_id: productId });
  }
};
