// Invoice Platform — Alpine.js application logic

function invoiceApp() {
  return {
    // ── Static dropdown data ──
    categories: [],
    brands: [],
    dates: [],
    currencies: [],
    products: [],

    // ── Form fields ──
    form: {
      dt: '',
      order_ts: '',
      customer_id: '',
      order_id: '',
      item_seq: 1,
      product_id: '',
      quantity: 1,
      unit_price_currency: 'USD',
      unit_price: '',
      discount_pct: 0,
      tax_amount: 0,
      channel: 'web',
      coupon_code: '',
    },

    // ── Cascade selection ──
    selectedCategory: '',
    selectedBrand: '',
    customerInfo: null,
    productInfo: null,

    // ── Customer autocomplete ──
    customerQuery: '',
    customerResults: [],
    showCustomerDropdown: false,
    customerSearchTimeout: null,

    // ── Product search ──
    productQuery: '',

    // ── UI state ──
    driveConnected: false,
    driveMethod: null,
    oauthConfigured: false,
    showDriveModal: false,
    loadingPreview: false,
    loadingDownload: false,
    loadingUpload: false,
    uploadResult: null,
    errors: {},
    toast: null,
    toastTimeout: null,

    // ── Computed totals ──
    get subtotal() {
      return (parseFloat(this.form.quantity) || 0) * (parseFloat(this.form.unit_price) || 0);
    },
    get discountAmount() {
      return this.subtotal * ((parseFloat(this.form.discount_pct) || 0) / 100);
    },
    get total() {
      return this.subtotal - this.discountAmount + (parseFloat(this.form.tax_amount) || 0);
    },
    get currencySymbol() {
      const s = { USD: '$', GBP: '£', INR: '₹', AED: 'AED ', AUD: 'A$', CAD: 'CA$', SGD: 'S$' };
      return s[this.form.unit_price_currency] || (this.form.unit_price_currency + ' ');
    },
    get formattedTotal() {
      return `${this.currencySymbol}${this.total.toFixed(2)}`;
    },

    // ── Init ──
    async init() {
      await Promise.all([
        this.loadCategories(),
        this.loadBrands(),
        this.loadDates(),
        this.loadCurrencies(),
        this.checkDriveStatus(),
      ]);
      // Default timestamp to now
      const now = new Date();
      const p = n => String(n).padStart(2, '0');
      this.form.order_ts = `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}T${p(now.getHours())}:${p(now.getMinutes())}`;
    },

    // ── Loaders ──
    async loadCategories() {
      this.categories = await (await fetch('/api/categories')).json();
    },
    async loadBrands(categoryCode = '') {
      const url = categoryCode ? `/api/brands?category=${encodeURIComponent(categoryCode)}` : '/api/brands';
      this.brands = await (await fetch(url)).json();
    },
    async loadDates() {
      this.dates = await (await fetch('/api/dates')).json();
    },
    async loadCurrencies() {
      this.currencies = await (await fetch('/api/currencies')).json();
    },
    async loadProducts() {
      if (!this.selectedCategory && !this.selectedBrand) { this.products = []; return; }
      const p = new URLSearchParams({ limit: 200 });
      if (this.selectedCategory) p.set('category', this.selectedCategory);
      if (this.selectedBrand)    p.set('brand', this.selectedBrand);
      if (this.productQuery && this.productQuery.length >= 2) p.set('q', this.productQuery);
      this.products = await (await fetch(`/api/products?${p}`)).json();
    },

    // ── Drive status ──
    async checkDriveStatus() {
      const data = await (await fetch('/api/config/drive-status')).json();
      this.driveConnected   = data.connected;
      this.driveMethod      = data.method;
      this.oauthConfigured  = data.oauth_configured;
    },

    // ── Google Drive connect / disconnect ──
    connectDrive() {
      if (!this.oauthConfigured) {
        this.showDriveModal = true;
        return;
      }
      // Redirect to OAuth flow
      window.location.href = '/api/drive/connect';
    },
    async disconnectDrive() {
      await fetch('/api/drive/disconnect', { method: 'POST' });
      this.driveConnected = false;
      this.driveMethod = null;
      this.showToast('Google Drive disconnected', '');
    },

    // ── Cascade handlers ──
    async onCategoryChange() {
      this.selectedBrand = '';
      this.form.product_id = '';
      this.productInfo = null;
      this.products = [];
      await this.loadBrands(this.selectedCategory);
    },
    async onBrandChange() {
      this.form.product_id = '';
      this.productInfo = null;
      await this.loadProducts();
    },

    // FIX: auto-fill price when a product is selected
    async onProductChange() {
      if (!this.form.product_id) { this.productInfo = null; return; }
      const res = await fetch(`/api/products/${encodeURIComponent(this.form.product_id)}`);
      if (res.ok) {
        const p = await res.json();
        this.productInfo = p;
        // Auto-fill price fields if the product has a known price from order history
        if (p.unit_price !== undefined && p.unit_price !== null) {
          this.form.unit_price = p.unit_price;
          if (p.unit_price_currency) {
            this.form.unit_price_currency = p.unit_price_currency;
          }
        }
      }
    },
    async onProductSearch() {
      await this.loadProducts();
    },

    // ── Customer autocomplete (FIX: ensure dropdown shows) ──
    onCustomerInput() {
      clearTimeout(this.customerSearchTimeout);
      this.form.customer_id = '';
      this.customerInfo = null;
      const q = this.customerQuery.trim();
      if (q.length < 2) {
        this.customerResults = [];
        this.showCustomerDropdown = false;
        return;
      }
      this.customerSearchTimeout = setTimeout(() => this.searchCustomers(), 300);
    },
    async searchCustomers() {
      const q = this.customerQuery.trim();
      if (q.length < 2) return;
      try {
        const res = await fetch(`/api/customers/search?q=${encodeURIComponent(q)}&limit=20`);
        const results = await res.json();
        this.customerResults = results;
        this.showCustomerDropdown = results.length > 0;
      } catch (e) {
        this.showCustomerDropdown = false;
      }
    },
    selectCustomer(cust) {
      this.form.customer_id = cust.customer_id;
      this.customerQuery = cust.customer_id;
      this.customerInfo = { ...cust };
      this.showCustomerDropdown = false;
      this.customerResults = [];
    },
    hideCustomerDropdown() {
      // Short delay so mousedown on a result fires first
      setTimeout(() => { this.showCustomerDropdown = false; }, 250);
    },

    // ── Validation ──
    validate() {
      const e = {};
      if (!this.form.dt)          e.dt = 'Select a date';
      if (!this.form.order_ts)    e.order_ts = 'Enter order timestamp';
      if (!this.form.customer_id) e.customer_id = 'Select a customer';
      if (!this.form.order_id)    e.order_id = 'Enter an order ID';
      if (!this.form.product_id)  e.product_id = 'Select a product';
      if (!this.form.quantity || parseFloat(this.form.quantity) <= 0) e.quantity = 'Must be > 0';
      if (this.form.unit_price === '' || parseFloat(this.form.unit_price) < 0) e.unit_price = 'Enter unit price';
      const d = parseFloat(this.form.discount_pct);
      if (isNaN(d) || d < 0 || d > 100) e.discount_pct = '0–100%';
      this.errors = e;
      return Object.keys(e).length === 0;
    },

    buildPayload() {
      return {
        ...this.form,
        order_ts: this.form.order_ts.replace('T', ' ') + ':00',
        discount_pct: parseFloat(this.form.discount_pct) || 0,
        quantity: parseFloat(this.form.quantity) || 1,
        unit_price: parseFloat(this.form.unit_price) || 0,
        tax_amount: parseFloat(this.form.tax_amount) || 0,
        customer_info: this.customerInfo || {},
        product_info: this.productInfo || {},
      };
    },

    // ── Invoice actions ──
    async previewInvoice() {
      if (!this.validate()) { this.showToast('Fix the errors first', 'error'); return; }
      this.loadingPreview = true;
      try {
        const res = await fetch('/api/invoice/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.buildPayload()),
        });
        const html = await res.text();
        const win = window.open('', '_blank');
        win.document.write(html);
        win.document.close();
      } catch (err) {
        this.showToast('Preview failed: ' + err.message, 'error');
      } finally {
        this.loadingPreview = false;
      }
    },

    async downloadPdf() {
      if (!this.validate()) { this.showToast('Fix the errors first', 'error'); return; }
      this.loadingDownload = true;
      try {
        const res = await fetch('/api/invoice/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.buildPayload()),
        });
        if (!res.ok) throw new Error(await res.text());
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Invoice-${this.form.order_id}-${this.form.item_seq}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('PDF downloaded!', 'success');
      } catch (err) {
        this.showToast('Download failed: ' + err.message, 'error');
      } finally {
        this.loadingDownload = false;
      }
    },

    async uploadToDrive() {
      if (!this.validate()) { this.showToast('Fix the errors first', 'error'); return; }
      this.loadingUpload = true;
      this.uploadResult = null;
      try {
        const res = await fetch('/api/invoice/upload', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.buildPayload()),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Upload failed');
        this.uploadResult = data;
        this.showToast('Uploaded to Google Drive!', 'success');
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.loadingUpload = false;
      }
    },

    resetForm() {
      this.form = {
        dt: '', order_ts: '', customer_id: '', order_id: '',
        item_seq: 1, product_id: '', quantity: 1,
        unit_price_currency: 'USD', unit_price: '',
        discount_pct: 0, tax_amount: 0, channel: 'web', coupon_code: '',
      };
      this.customerQuery = '';
      this.customerInfo = null;
      this.productInfo = null;
      this.selectedCategory = '';
      this.selectedBrand = '';
      this.products = [];
      this.uploadResult = null;
      this.errors = {};
    },

    showToast(message, type = '') {
      clearTimeout(this.toastTimeout);
      this.toast = { message, type };
      this.toastTimeout = setTimeout(() => { this.toast = null; }, 3500);
    },
  };
}
