import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Bot,
  Boxes,
  BriefcaseBusiness,
  Building2,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  Database,
  FileText,
  FileUp,
  Filter,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  MessageSquareText,
  Package,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  TrendingDown,
  TrendingUp,
  Truck,
  MapPin,
  AlertTriangle,
  Route,
  UploadCloud,
  Wallet,
  X,
  Zap,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const DEMO_ORGANIZATION_ID = '11111111-1111-4111-8111-111111111111';
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
const DEFAULT_START = '2026-08-01';
const DEFAULT_END = '2026-10-31';
const INVENTORY_SNAPSHOT_DATE = '2026-11-01';

type PageKey = 'overview' | 'analyst' | 'knowledge' | 'products' | 'inventory' | 'supply_chain' | 'ipo_readiness' | 'retail';
type JsonObject = Record<string, unknown>;
type FinancialMetrics = {
  gross_sales?: number;
  sales_returns?: number;
  net_revenue?: number;
  cogs?: number;
  gross_profit?: number;
  gross_margin_pct?: number;
  operating_expenses?: number;
  ebitda?: number;
  ebitda_margin_pct?: number;
  ebit?: number;
  pbt?: number;
  pat?: number;
  pat_margin_pct?: number;
};
type MonthMetric = FinancialMetrics & { month: string; operating_expense_ratio_pct?: number };
type ProductRow = { sku: string; product_name: string; category?: string; units_sold: number; net_sales: number; gross_profit: number; order_count: number };
type RegionRow = { region: string; order_count: number; net_sales: number; gross_profit: number };
type InventoryRow = { sku: string; product_name: string; category?: string; quantity_on_hand: number; inventory_value: number; reorder_alert: boolean; snapshot_date?: string };
type KnowledgeDocument = { document_id: string; filename: string; uploaded_at?: string; chunk_count: number };
type KnowledgeHit = { text: string; source: { document_id: string; filename: string; page_number: number; citation: string }; distance?: number };
type AgentSource = { document_id: string; filename: string; page_number: number; citation: string };
type AgentResult = { answer: string; provider?: string; model?: string; tools_used?: string[]; tool_trace?: Array<{ tool: string; arguments: JsonObject }>; sources?: AgentSource[]; disclaimer?: string };
type ChatMessage = { id: string; role: 'assistant' | 'user'; content: string; result?: AgentResult; error?: boolean };

const navItems: Array<{ key: PageKey; label: string; icon: typeof LayoutDashboard }> = [
  { key: 'overview', label: 'Overview', icon: LayoutDashboard },
  { key: 'analyst', label: 'AI Analyst', icon: MessageSquareText },
  { key: 'knowledge', label: 'Knowledge base', icon: FileText },
  { key: 'products', label: 'Products & regions', icon: Package },
  { key: 'inventory', label: 'Inventory', icon: Boxes },
  { key: 'supply_chain', label: 'Supply chain', icon: Truck },
  { key: 'ipo_readiness', label: 'IPO readiness', icon: BriefcaseBusiness },
  { key: 'retail', label: 'Multi-store intelligence', icon: Boxes },
];

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  headers.set('X-Organization-ID', DEMO_ORGANIZATION_ID);
  if (!(init.body instanceof FormData) && init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === 'string' ? payload.detail : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return payload as T;
}

function numberValue(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function formatCurrency(value: unknown, currency = 'INR', compact = false): string {
  const amount = numberValue(value);
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency,
      maximumFractionDigits: compact ? 1 : 0,
      notation: compact ? 'compact' : 'standard',
    }).format(amount);
  } catch {
    return `${currency} ${amount.toLocaleString('en-IN')}`;
  }
}

function formatNumber(value: unknown, digits = 0): string {
  return numberValue(value).toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function monthLabel(value: string): string {
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return date.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
}


function App() {
  const [activePage, setActivePage] = useState<PageKey>('overview');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [startDate, setStartDate] = useState(DEFAULT_START);
  const [endDate, setEndDate] = useState(DEFAULT_END);
  const [currency, setCurrency] = useState('INR');
  const [organizationName, setOrganizationName] = useState('Deccan Wholesale & Retail Demo Co.');
  const [metrics, setMetrics] = useState<FinancialMetrics>({});
  const [months, setMonths] = useState<MonthMetric[]>([]);
  const [products, setProducts] = useState<ProductRow[]>([]);
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [inventory, setInventory] = useState<InventoryRow[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [businessCounts, setBusinessCounts] = useState<JsonObject>({});
  const [balance, setBalance] = useState<JsonObject>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pageError, setPageError] = useState('');
  const [notice, setNotice] = useState('');

  const loadDashboard = useCallback(async (quiet = false) => {
    if (quiet) setRefreshing(true); else setLoading(true);
    setPageError('');
    const query = `start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
    const requests = await Promise.allSettled([
      apiRequest<JsonObject>('/api/v1/organizations/current'),
      apiRequest<JsonObject>(`/api/v1/financial/summary?${query}`),
      apiRequest<{ months: MonthMetric[]; currency?: string }>(`/api/v1/financial/monthly-trend?${query}`),
      apiRequest<{ products: ProductRow[]; currency?: string }>(`/api/v1/analytics/product-performance?${query}&limit=10`),
      apiRequest<{ regions: RegionRow[]; currency?: string }>(`/api/v1/analytics/regional-performance?${query}`),
      apiRequest<{ inventory: InventoryRow[]; currency?: string }>(`/api/v1/analytics/inventory-health?as_of_date=${INVENTORY_SNAPSHOT_DATE}`),
      apiRequest<{ statement: JsonObject; currency?: string }>(`/api/v1/financial/balance-sheet?as_of_date=${encodeURIComponent(endDate)}`),
      apiRequest<{ documents: KnowledgeDocument[] }>('/api/v1/knowledge/documents'),
      apiRequest<JsonObject>('/api/v1/dashboard/summary'),
    ]);

    const [org, summary, trend, productData, regionData, inventoryData, balanceData, docs, dashboard] = requests;
    let failures = 0;
    const unwrap = <T,>(result: PromiseSettledResult<T>, fallback: T): T => {
      if (result.status === 'fulfilled') return result.value;
      failures += 1;
      return fallback;
    };
    const orgData = unwrap(org, {} as JsonObject);
    const summaryData = unwrap(summary, {} as JsonObject);
    const trendData = unwrap(trend, { months: [] });
    const productPayload = unwrap(productData, { products: [] });
    const regionPayload = unwrap(regionData, { regions: [] });
    const inventoryPayload = unwrap(inventoryData, { inventory: [] });
    const balancePayload = unwrap(balanceData, { statement: {} });
    const docPayload = unwrap(docs, { documents: [] });
    const dashboardPayload = unwrap(dashboard, {} as JsonObject);

    if (typeof orgData.display_name === 'string') setOrganizationName(orgData.display_name);
    if (typeof summaryData.currency === 'string') setCurrency(summaryData.currency);
    else if (typeof trendData.currency === 'string') setCurrency(trendData.currency);
    setMetrics((summaryData.metrics as FinancialMetrics) || {});
    setMonths(Array.isArray(trendData.months) ? trendData.months : []);
    setProducts(Array.isArray(productPayload.products) ? productPayload.products : []);
    setRegions(Array.isArray(regionPayload.regions) ? regionPayload.regions : []);
    setInventory(Array.isArray(inventoryPayload.inventory) ? inventoryPayload.inventory : []);
    setBalance((balancePayload.statement as JsonObject) || {});
    setDocuments(Array.isArray(docPayload.documents) ? docPayload.documents : []);
    setBusinessCounts((dashboardPayload.business_counts as JsonObject) || {});
    if (failures > 0 && !quiet) {
      setPageError(`${failures} data request${failures === 1 ? '' : 's'} could not be completed. Check that the API is running; sections with available data remain usable.`);
    }
    setLoading(false);
    setRefreshing(false);
  }, [startDate, endDate]);

  useEffect(() => { void loadDashboard(); }, [loadDashboard]);

  const refreshDocuments = useCallback(async () => {
    const result = await apiRequest<{ documents: KnowledgeDocument[] }>('/api/v1/knowledge/documents');
    setDocuments(result.documents || []);
  }, []);

  const pageTitle = navItems.find((item) => item.key === activePage)?.label || 'Overview';
  const currentMonth = months[months.length - 1];
  const previousMonth = months.length > 1 ? months[months.length - 2] : undefined;
  const expenseRatio = currentMonth?.operating_expense_ratio_pct;
  const alertCount = inventory.filter((item) => item.reorder_alert).length;

  const change = (current: number, previous?: number) => previous && previous !== 0 ? ((current - previous) / Math.abs(previous)) * 100 : null;
  const revenueChange = change(numberValue(currentMonth?.net_revenue), previousMonth ? numberValue(previousMonth.net_revenue) : undefined);
  const expenseChange = change(numberValue(currentMonth?.operating_expenses), previousMonth ? numberValue(previousMonth.operating_expenses) : undefined);

  const setPage = (page: PageKey) => {
    setActivePage(page);
    setMobileNavOpen(false);
    setNotice('');
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNavOpen ? 'sidebar-open' : ''}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><Activity size={21} strokeWidth={2.5} /></div>
          <div><div className="brand-name">profitpulse<span>ai</span></div><div className="brand-caption">BUSINESS INTELLIGENCE</div></div>
          <button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)}><X size={18} /></button>
        </div>

        <div className="workspace-switcher">
          <div className="workspace-icon"><Building2 size={17} /></div>
          <div className="workspace-copy"><strong>{organizationName}</strong><span>Demo workspace</span></div>
          <ChevronDown size={15} className="muted-icon" />
        </div>

        <div className="nav-section-label">WORKSPACE</div>
        <nav className="main-nav" aria-label="Main navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            return <button key={item.key} className={`nav-link ${activePage === item.key ? 'active' : ''}`} onClick={() => setPage(item.key)}>
              <Icon size={18} strokeWidth={1.9} /><span>{item.label}</span>{item.key === 'knowledge' && documents.length > 0 && <span className="nav-count">{documents.length}</span>}
            </button>;
          })}
        </nav>

        <div className="sidebar-divider" />
        <div className="nav-section-label">SYSTEM</div>
        <button className="nav-link" onClick={() => setNotice('Settings are in development. This demo uses a fixed development organization ID.')}><Settings2 size={18} /><span>Settings</span></button>
        <button className="nav-link" onClick={() => setNotice('The API is proxied through this application. Open /docs for the interactive API reference.')}><CircleHelp size={18} /><span>Help & API docs</span></button>

        <div className="sidebar-spacer" />
        <div className="sidebar-health">
          <div className="health-top"><span className="pulse-dot" />Demo stack configured</div>
          <div className="health-sub">API · PostgreSQL · ChromaDB</div>
        </div>
        <div className="profile-row">
          <div className="avatar">PP</div>
          <div className="profile-copy"><strong>ProfitPulse Demo</strong><span>Local environment</span></div>
          <ChevronDown size={15} className="muted-icon" />
        </div>
      </aside>

      {mobileNavOpen && <button aria-label="Close navigation overlay" className="nav-scrim" onClick={() => setMobileNavOpen(false)} />}

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileNavOpen(true)}><Menu size={20} /></button>
            <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{pageTitle}</strong></div>
          </div>
          <div className="topbar-actions">
            <div className="live-status"><span className="pulse-dot" />Live data</div>
            <button className="icon-button refresh-button" title="Refresh dashboard" onClick={() => void loadDashboard(true)} disabled={refreshing}>{refreshing ? <LoaderCircle className="spin" size={17} /> : <RefreshCw size={17} />}</button>
            <div className="top-avatar">HS</div>
          </div>
        </header>

        <div className="content-area">
          {pageError && <div className="alert alert-warning"><CircleHelp size={17} /><span>{pageError}</span><button onClick={() => setPageError('')} aria-label="Dismiss"><X size={15} /></button></div>}
          {notice && <div className="alert alert-info"><Sparkles size={17} /><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Dismiss"><X size={15} /></button></div>}
          {activePage === 'overview' && <OverviewPage
            loading={loading} currency={currency} metrics={metrics} months={months}
            balance={balance} businessCounts={businessCounts} expenseRatio={expenseRatio} revenueChange={revenueChange}
            expenseChange={expenseChange} alertCount={alertCount} startDate={startDate} endDate={endDate}
            setStartDate={setStartDate} setEndDate={setEndDate} onAsk={() => setPage('analyst')} onKnowledge={() => setPage('knowledge')}
          />}
          {activePage === 'analyst' && <AnalystPage />}
          {activePage === 'knowledge' && <KnowledgePage documents={documents} onRefresh={refreshDocuments} onNotice={setNotice} />}
          {activePage === 'products' && <ProductsPage products={products} regions={regions} currency={currency} loading={loading} />}
          {activePage === 'inventory' && <InventoryPage inventory={inventory} currency={currency} loading={loading} alertCount={alertCount} />}
          {activePage === 'supply_chain' && <SupplyChainPage />}
          {activePage === 'ipo_readiness' && <IpoReadinessPage months={months} metrics={metrics} currency={currency} />}
          {activePage === 'retail' && <RetailIntelligencePage />}
          <footer className="footer"><span>ProfitPulse AI <span className="footer-dot">·</span> Decision intelligence for growing businesses</span><span>DEMO ENVIRONMENT <span className="footer-dot">·</span> Not audited financial advice</span></footer>
        </div>
      </main>
    </div>
  );
}


type RetailStore = { id: string; store_code: string; store_name: string; city: string; monthly_revenue_threshold: number; sales_rows?: number; latest_inventory_date?: string | null };
type RetailReport = {
  company: { total_revenue: number; total_gross_profit: number; gross_margin_pct: number; stores_with_low_stock: number; low_stock_sku_count: number };
  store_count: number;
  store_ranking: Array<{ code: string; name: string; city: string; revenue: number; gross_profit: number; gross_margin_pct: number; low_stock_skus: number }>;
  expansion_candidates: Array<{ store_name: string; city: string; monthly_revenue_threshold: number; consecutive_months_above_threshold: number; reason: string }>;
  important_note: string;
};

function RetailIntelligencePage() {
  const [stores, setStores] = useState<RetailStore[]>([]);
  const [report, setReport] = useState<RetailReport | null>(null);
  const [selectedStore, setSelectedStore] = useState('');
  const [storeCode, setStoreCode] = useState('');
  const [storeName, setStoreName] = useState('');
  const [city, setCity] = useState('');
  const [threshold, setThreshold] = useState('750000');
  const [salesFile, setSalesFile] = useState<File | null>(null);
  const [inventoryFile, setInventoryFile] = useState<File | null>(null);
  const [recipient, setRecipient] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const loadRetail = useCallback(async () => {
    setBusy(true); setError('');
    try {
      const [storeData, reportData] = await Promise.all([
        apiRequest<{ stores: RetailStore[] }>('/api/v1/retail/stores'),
        apiRequest<RetailReport>('/api/v1/retail/headquarters/report'),
      ]);
      setStores(storeData.stores || []);
      setReport(reportData);
      if (!selectedStore && storeData.stores?.length) setSelectedStore(storeData.stores[0].id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load multi-store data. Apply the database migration first.');
    } finally { setBusy(false); }
  }, [selectedStore]);

  useEffect(() => { void loadRetail(); }, [loadRetail]);

  const createStore = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      await apiRequest('/api/v1/retail/stores', { method: 'POST', body: JSON.stringify({
        store_code: storeCode, store_name: storeName, city, monthly_revenue_threshold: Number(threshold || 0),
      })});
      setStoreCode(''); setStoreName(''); setCity('');
      setMessage('Store created. Select it below to upload its sales and inventory files.');
      await loadRetail();
    } catch (e) { setError(e instanceof Error ? e.message : 'Store creation failed.'); }
    finally { setBusy(false); }
  };

  const uploadFile = async (kind: 'sales' | 'inventory') => {
    const file = kind === 'sales' ? salesFile : inventoryFile;
    if (!selectedStore || !file) { setError('Select a store and a CSV file first.'); return; }
    setBusy(true); setError(''); setMessage('');
    try {
      const form = new FormData(); form.append('file', file);
      const path = kind === 'sales' ? 'upload-sales' : 'upload-inventory';
      const result = await apiRequest<{ accepted_rows: number }>(`/api/v1/retail/stores/${selectedStore}/${path}`, { method: 'POST', body: form });
      setMessage(`${kind === 'sales' ? 'Sales' : 'Inventory'} upload complete: ${result.accepted_rows} rows accepted.`);
      if (kind === 'sales') setSalesFile(null); else setInventoryFile(null);
      await loadRetail();
    } catch (e) { setError(e instanceof Error ? e.message : 'Upload failed.'); }
    finally { setBusy(false); }
  };

  const sendEmail = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const result = await apiRequest<{ status: string; recipient: string }>('/api/v1/retail/headquarters/email', {
        method: 'POST', body: JSON.stringify({ recipient }),
      });
      setMessage(`Headquarters report emailed to ${result.recipient}.`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Email delivery failed.'); }
    finally { setBusy(false); }
  };

  const money = (value: number) => formatCurrency(value, 'INR');
  return <div className="retail-intelligence">
    <div className="page-heading">
      <div><div className="eyebrow"><span className="eyebrow-line" /> RETAIL NETWORK INTELLIGENCE</div>
        <h1>Multi-store intelligence</h1>
        <p>Upload each store's sales and stock records. Store analysts prepare local reports; headquarters consolidates the network view.</p>
      </div>
      <button className="secondary-button" onClick={() => void loadRetail()} disabled={busy}><RefreshCw size={14} /> Refresh reports</button>
    </div>
    {error && <div className="alert alert-warning"><CircleHelp size={16} /><span>{error}</span></div>}
    {message && <div className="alert alert-info"><Check size={16} /><span>{message}</span></div>}
    <div className="metric-grid" style={{marginBottom:18}}>
      <div className="metric-card"><div className="metric-label">Stores connected</div><div className="metric-value">{report?.store_count ?? stores.length}</div></div>
      <div className="metric-card"><div className="metric-label">Network revenue</div><div className="metric-value">{money(report?.company.total_revenue ?? 0)}</div></div>
      <div className="metric-card"><div className="metric-label">Gross profit</div><div className="metric-value">{money(report?.company.total_gross_profit ?? 0)}</div></div>
      <div className="metric-card"><div className="metric-label">Stores with low stock</div><div className="metric-value">{report?.company.stores_with_low_stock ?? 0}</div></div>
    </div>
    <div className="content-grid" style={{display:'grid', gridTemplateColumns:'repeat(2,minmax(0,1fr))', gap:16, marginBottom:16}}>
      <section className="panel panel-padding">
        <div className="panel-header"><div><h3>Add a store</h3><p>Configure the monthly revenue threshold used for expansion screening.</p></div></div>
        <form onSubmit={createStore} style={{display:'grid', gap:9}}>
          <input aria-label="Store code" placeholder="Store code (e.g. ST01)" value={storeCode} onChange={e=>setStoreCode(e.target.value)} required />
          <input aria-label="Store name" placeholder="Store name" value={storeName} onChange={e=>setStoreName(e.target.value)} required />
          <input aria-label="City" placeholder="City / location" value={city} onChange={e=>setCity(e.target.value)} required />
          <input aria-label="Monthly revenue threshold" type="number" min="0" placeholder="Monthly revenue threshold (INR)" value={threshold} onChange={e=>setThreshold(e.target.value)} />
          <button className="primary-button" type="submit" disabled={busy}><Plus size={14}/> Add store</button>
        </form>
      </section>
      <section className="panel panel-padding">
        <div className="panel-header"><div><h3>Manual data upload</h3><p>Upload a separate sales CSV and inventory snapshot for the selected store.</p></div></div>
        <select aria-label="Select store" value={selectedStore} onChange={e=>setSelectedStore(e.target.value)} style={{width:'100%', marginBottom:12}}>
          <option value="">Select a store</option>{stores.map(s=><option key={s.id} value={s.id}>{s.store_code} · {s.store_name}</option>)}
        </select>
        <label style={{display:'block', fontSize:11, marginBottom:5}}>Sales records CSV</label>
        <input type="file" accept=".csv,text/csv" onChange={e=>setSalesFile(e.target.files?.[0] || null)} />
        <button className="secondary-button" style={{margin:'8px 0 14px'}} onClick={()=>void uploadFile('sales')} disabled={busy || !salesFile || !selectedStore}><UploadCloud size={14}/> Upload sales</button>
        <label style={{display:'block', fontSize:11, marginBottom:5}}>Inventory snapshot CSV</label>
        <input type="file" accept=".csv,text/csv" onChange={e=>setInventoryFile(e.target.files?.[0] || null)} />
        <button className="secondary-button" style={{marginTop:8}} onClick={()=>void uploadFile('inventory')} disabled={busy || !inventoryFile || !selectedStore}><UploadCloud size={14}/> Upload inventory</button>
        <p style={{fontSize:10, color:'#8592a4', marginTop:12}}>Templates: examples/retail_sales_template.csv and examples/retail_inventory_template.csv</p>
      </section>
    </div>
    <section className="panel panel-padding" style={{marginBottom:16}}>
      <div className="panel-header"><div><h3>Headquarters report</h3><p>Central agent ranks stores by gross profit and flags stock risks.</p></div><span className="panel-chip">{stores.length} stores</span></div>
      <div style={{overflowX:'auto'}}>
        <table style={{width:'100%', borderCollapse:'collapse', fontSize:11}}>
          <thead><tr>{['Store','City','Revenue','Gross profit','Margin','Low-stock SKUs'].map(x=><th key={x} style={{textAlign:'left',padding:'10px 8px',color:'#8190a3',borderBottom:'1px solid #edf0f4'}}>{x}</th>)}</tr></thead>
          <tbody>{(report?.store_ranking || []).map((s,i)=><tr key={s.code}><td style={{padding:'10px 8px',borderBottom:'1px solid #f0f2f5'}}><strong>{i+1}. {s.name}</strong><div style={{color:'#98a2af'}}>{s.code}</div></td><td>{s.city}</td><td>{money(s.revenue)}</td><td>{money(s.gross_profit)}</td><td>{s.gross_margin_pct.toFixed(1)}%</td><td>{s.low_stock_skus}</td></tr>)}</tbody>
        </table>
        {!report?.store_ranking?.length && <p style={{color:'#8a96a6',fontSize:11}}>No store data yet. Add stores and upload their CSV records to generate reports.</p>}
      </div>
    </section>
    <div className="content-grid" style={{display:'grid', gridTemplateColumns:'repeat(2,minmax(0,1fr))', gap:16}}>
      <section className="panel panel-padding">
        <div className="panel-header"><div><h3>Expansion screening</h3><p>Threshold-based candidates for owner review, not automatic site recommendations.</p></div></div>
        {(report?.expansion_candidates || []).map(s=><div key={s.store_name} style={{padding:'9px 0',borderBottom:'1px solid #edf0f4'}}><strong style={{fontSize:11}}>{s.store_name} · {s.city}</strong><p style={{fontSize:10,color:'#8290a1',margin:'4px 0'}}>{s.reason}</p></div>)}
        {!report?.expansion_candidates?.length && <p style={{fontSize:11,color:'#8a96a6'}}>No store has crossed its configured threshold for three consecutive reported months.</p>}
      </section>
      <section className="panel panel-padding">
        <div className="panel-header"><div><h3>Email owner report</h3><p>Send the latest consolidated headquarters report.</p></div></div>
        <form onSubmit={sendEmail} style={{display:'grid',gap:9}}>
          <input type="email" aria-label="Owner email address" placeholder="owner@company.com" value={recipient} onChange={e=>setRecipient(e.target.value)} required />
          <button className="primary-button" type="submit" disabled={busy}><Send size={14}/> Send consolidated email</button>
        </form>
        <p style={{fontSize:10,color:'#8592a4',marginTop:10}}>SMTP settings must be configured on the backend. Scheduled daily delivery will be added after the first manual demo run.</p>
      </section>
    </div>
    <p style={{fontSize:10,color:'#8592a4',marginTop:14}}>{report?.important_note}</p>
  </div>;
}

type OverviewProps = {
  loading: boolean; currency: string; metrics: FinancialMetrics; months: MonthMetric[];
  balance: JsonObject; businessCounts: JsonObject; expenseRatio?: number; revenueChange: number | null; expenseChange: number | null;
  alertCount: number; startDate: string; endDate: string; setStartDate: (value: string) => void; setEndDate: (value: string) => void;
  onAsk: () => void; onKnowledge: () => void;
};

function OverviewPage(props: OverviewProps) {
  const { loading, currency, metrics, months, balance, businessCounts, expenseRatio, revenueChange, expenseChange, alertCount, startDate, endDate, setStartDate, setEndDate, onAsk, onKnowledge } = props;
  const chartData = months.map((month) => ({
    label: monthLabel(month.month),
    revenue: numberValue(month.net_revenue),
    expenses: numberValue(month.operating_expenses),
    grossProfit: numberValue(month.gross_profit),
    ebitda: numberValue(month.ebitda),
  }));
  const mixData = [
    { name: 'COGS', value: numberValue(metrics.cogs) },
    { name: 'Gross profit', value: numberValue(metrics.gross_profit) },
  ].filter((item) => item.value > 0);
  const palette = ['#8ba3d8', '#f0a45c', '#36b39a'];

  return <>
    <div className="page-heading heading-with-actions">
      <div><div className="eyebrow">BUSINESS OVERVIEW <span className="eyebrow-line" /></div><h1>Your business, in focus.</h1><p>A clear view of financial performance, operating health and the signals behind the numbers.</p></div>
      <div className="date-filter"><div className="date-field"><label htmlFor="start-date">FROM</label><input id="start-date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} max={endDate} /></div><span className="date-separator">to</span><div className="date-field"><label htmlFor="end-date">TO</label><input id="end-date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} min={startDate} /></div><span className="filter-icon"><Filter size={15} /></span></div>
    </div>

    <div className="insight-banner"><div className="insight-icon"><Sparkles size={18} /></div><div className="insight-copy"><strong>Your AI business analyst is ready.</strong><span>Ask questions across your financial ledger, operations and uploaded company documents.</span></div><button className="banner-action" onClick={onAsk}>Ask ProfitPulse <ArrowRight size={15} /></button></div>

    <div className="section-heading"><div><h2>Performance snapshot</h2><span>Selected reporting period · {new Date(`${startDate}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} – {new Date(`${endDate}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span></div><span className="section-caption"><span className="pulse-dot" />Updated from live API</span></div>

    <div className="metric-grid">
      <MetricCard label="Net revenue" value={formatCurrency(metrics.net_revenue, currency, true)} icon={<Wallet size={18} />} tone="blue" detail={revenueChange === null ? 'Period total' : `${revenueChange >= 0 ? '+' : ''}${revenueChange.toFixed(1)}% vs prior month`} trend={revenueChange === null ? 'neutral' : revenueChange >= 0 ? 'positive' : 'negative'} loading={loading} />
      <MetricCard label="Gross profit" value={formatCurrency(metrics.gross_profit, currency, true)} icon={<TrendingUp size={18} />} tone="green" detail={`${formatNumber(metrics.gross_margin_pct, 1)}% gross margin`} loading={loading} />
      <MetricCard label="EBITDA" value={formatCurrency(metrics.ebitda, currency, true)} icon={<Activity size={18} />} tone="orange" detail={`${formatNumber(metrics.ebitda_margin_pct, 1)}% EBITDA margin`} trend={numberValue(metrics.ebitda) >= 0 ? 'positive' : 'negative'} loading={loading} />
      <MetricCard label="Operating expenses" value={formatCurrency(metrics.operating_expenses, currency, true)} icon={<BriefcaseBusiness size={18} />} tone="purple" detail={expenseChange === null ? 'Period total' : `${expenseChange >= 0 ? '+' : ''}${expenseChange.toFixed(1)}% vs prior month`} trend={expenseChange === null ? 'neutral' : expenseChange <= 0 ? 'positive' : 'negative'} loading={loading} />
    </div>

    <div className="dashboard-grid main-charts-grid">
      <section className="panel chart-panel large-panel">
        <div className="panel-header"><div><h3>Revenue & operating expenses</h3><p>Monthly financial performance</p></div><span className="panel-chip">{months.length} periods</span></div>
        {loading ? <ChartSkeleton /> : chartData.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chartData} margin={{ top: 12, right: 8, left: 4, bottom: 0 }}>
          <defs><linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7896d4" stopOpacity={0.22} /><stop offset="100%" stopColor="#7896d4" stopOpacity={0.01} /></linearGradient></defs>
          <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e9edf3" />
          <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#8b95a5', fontSize: 11 }} dy={10} />
          <YAxis axisLine={false} tickLine={false} tick={{ fill: '#8b95a5', fontSize: 11 }} tickFormatter={(v) => `${currency === 'INR' ? '₹' : ''}${(v / 1000).toFixed(0)}k`} width={58} />
          <Tooltip content={<ChartTooltip currency={currency} />} />
          <Legend verticalAlign="top" align="right" height={30} iconType="circle" wrapperStyle={{ fontSize: 11, color: '#6e7888' }} />
          <Area type="monotone" dataKey="revenue" name="Net revenue" stroke="#6f8fce" strokeWidth={2.6} fill="url(#revenueFill)" activeDot={{ r: 5 }} />
          <Bar dataKey="expenses" name="Operating expenses" fill="#f0a45c" radius={[5, 5, 0, 0]} barSize={28} />
        </ComposedChart></ResponsiveContainer></div> : <EmptyState title="No monthly data" detail="Try a wider reporting period." />}
      </section>
      <section className="panel chart-panel ebitda-panel">
        <div className="panel-header"><div><h3>EBITDA trend</h3><p>Operating earnings before D&A</p></div><span className="panel-icon"><TrendingDown size={17} /></span></div>
        {loading ? <ChartSkeleton /> : chartData.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData} margin={{ top: 14, right: 4, left: 0, bottom: 0 }}>
          <defs><linearGradient id="ebitdaFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#e58a79" stopOpacity={0.2} /><stop offset="100%" stopColor="#e58a79" stopOpacity={0.01} /></linearGradient></defs>
          <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e9edf3" />
          <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#8b95a5', fontSize: 11 }} dy={9} />
          <YAxis axisLine={false} tickLine={false} tick={{ fill: '#8b95a5', fontSize: 10 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} width={42} />
          <Tooltip content={<ChartTooltip currency={currency} />} />
          <Area type="monotone" dataKey="ebitda" name="EBITDA" stroke="#d37f70" strokeWidth={2.5} fill="url(#ebitdaFill)" activeDot={{ r: 5 }} />
        </AreaChart></ResponsiveContainer></div> : <EmptyState title="No EBITDA trend" detail="Monthly figures will appear here." />}
      </section>
    </div>

    <div className="dashboard-grid lower-grid">
      <section className="panel panel-padding">
        <div className="panel-header"><div><h3>Revenue composition</h3><p>COGS + gross profit = net revenue</p></div><span className="panel-icon"><Wallet size={17} /></span></div>
        {loading ? <ChartSkeleton /> : mixData.length ? <div className="mix-layout"><div className="donut-wrap"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={mixData} dataKey="value" nameKey="name" innerRadius={63} outerRadius={88} paddingAngle={3} stroke="none">{mixData.map((entry, index) => <Cell key={entry.name} fill={palette[index % palette.length]} />)}</Pie><Tooltip formatter={(value) => formatCurrency(value, currency)} /></PieChart></ResponsiveContainer><div className="donut-center"><strong>{formatCurrency(metrics.net_revenue, currency, true)}</strong><span>Net revenue</span></div></div><div className="mix-legend">{mixData.map((item, index) => <div className="mix-item" key={item.name}><span className="mix-dot" style={{ background: palette[index % palette.length] }} /><span>{item.name}</span><strong>{formatCurrency(item.value, currency, true)}</strong></div>)}</div></div> : <EmptyState title="No composition data" detail="Financial categories will appear here." />}
      </section>
      <section className="panel panel-padding">
        <div className="panel-header"><div><h3>Business pulse</h3><p>Operational signals at a glance</p></div><span className="panel-icon"><Activity size={17} /></span></div>
        <div className="pulse-stats">
          <PulseStat icon={<Building2 size={17} />} label="Customers" value={formatNumber(businessCounts.customers)} />
          <PulseStat icon={<Package size={17} />} label="Active products" value={formatNumber(businessCounts.active_products)} />
          <PulseStat icon={<BriefcaseBusiness size={17} />} label="Orders" value={formatNumber(businessCounts.orders)} />
          <PulseStat icon={<Boxes size={17} />} label="Reorder alerts · 1 Nov" value={formatNumber(alertCount)} alert={alertCount > 0} />
        </div>
        <div className="balance-note"><div className="balance-note-icon"><ShieldCheck size={16} /></div><div><strong>Ledger balance check</strong><span>{balance.is_balanced === true ? 'Assets equal liabilities and equity.' : 'Balance status not confirmed for this date.'}</span></div><span className={`status-pill ${balance.is_balanced === true ? 'status-good' : 'status-neutral'}`}>{balance.is_balanced === true ? 'Balanced' : 'Review'}</span></div>
      </section>
    </div>

    <div className="bottom-insight-row">
      <div className="mini-insight"><div className="mini-icon mini-icon-amber"><Zap size={17} /></div><div><strong>Operating expense ratio</strong><span>{expenseRatio === undefined ? 'No monthly ratio available' : `${formatNumber(expenseRatio, 1)}% in the latest month · ${expenseRatio > 100 ? 'expenses exceed revenue' : 'within monthly revenue'}`}</span></div></div>
      <button className="text-action" onClick={onKnowledge}>Explore company knowledge <ArrowRight size={15} /></button>
    </div>
  </>;
}

function MetricCard({ label, value, icon, tone, detail, trend, loading }: { label: string; value: string; icon: ReactNode; tone: string; detail: string; trend?: 'positive' | 'negative' | 'neutral'; loading: boolean }) {
  const TrendIcon = trend === 'positive' ? ArrowUpRight : trend === 'negative' ? ArrowDownRight : Activity;
  return <div className="metric-card"><div className="metric-top"><span className="metric-label">{label}</span><span className={`metric-icon metric-${tone}`}>{icon}</span></div><div className="metric-value">{loading ? <span className="skeleton skeleton-value" /> : value}</div><div className={`metric-detail ${trend === 'positive' ? 'detail-positive' : trend === 'negative' ? 'detail-negative' : ''}`}><TrendIcon size={13} /><span>{loading ? 'Loading live figures' : detail}</span></div></div>;
}

function ChartTooltip({ active, payload, label, currency }: { active?: boolean; payload?: Array<{ name?: string | number; value?: unknown; color?: string }>; label?: string | number; currency: string }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>{label}</strong>{payload.map((item) => <div key={item.name}><span style={{ background: item.color }} />{item.name}<b>{formatCurrency(item.value, currency)}</b></div>)}</div>;
}

function ChartSkeleton() { return <div className="chart-skeleton"><div className="skeleton skeleton-chart" /><div className="skeleton skeleton-chart short" /></div>; }
function EmptyState({ title, detail }: { title: string; detail: string }) { return <div className="empty-state"><Database size={22} /><strong>{title}</strong><span>{detail}</span></div>; }
function PulseStat({ icon, label, value, alert = false }: { icon: ReactNode; label: string; value: string; alert?: boolean }) { return <div className="pulse-stat"><span className={`pulse-stat-icon ${alert ? 'pulse-alert' : ''}`}>{icon}</span><div><strong>{value}</strong><span>{label}</span></div></div>; }

function AnalystPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([{ id: 'welcome', role: 'assistant', content: 'I’m your ProfitPulse business analyst. Ask me about revenue, margins, expenses, inventory, or your uploaded company documents. I’ll use connected tools and show the evidence behind the answer.' }]);
  const [question, setQuestion] = useState('');
  const [sending, setSending] = useState(false);
  const [maxToolRounds] = useState(6);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prompts = [
    'Why did EBITDA deteriorate in October 2026?',
    'Compare monthly revenue and operating expenses from August to October.',
    'Who approves an unbudgeted purchase of INR 75,000 under the uploaded policy?',
    'Which products contributed the most gross profit?',
  ];

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, sending]);

  const submit = async (text = question) => {
    const clean = text.trim();
    if (!clean || sending) return;
    setQuestion('');
    setSending(true);
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: clean };
    setMessages((current) => [...current, userMessage]);
    try {
      const result = await apiRequest<AgentResult>('/api/v1/agent/ask', {
        method: 'POST',
        body: JSON.stringify({ question: clean, max_tool_rounds: maxToolRounds }),
      });
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', content: result.answer || 'The agent returned no answer.', result }]);
    } catch (error) {
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', content: error instanceof Error ? error.message : 'The request failed.', error: true }]);
    } finally {
      setSending(false);
    }
  };

  return <div className="analyst-layout">
    <div className="page-heading"><div><div className="eyebrow">PROFITPULSE INTELLIGENCE <span className="eyebrow-line" /></div><h1>Ask better business questions.</h1><p>Your AI analyst can investigate structured data and retrieve evidence from your company documents.</p></div></div>
    <div className="analyst-workspace">
      <div className="chat-column">
        <div className="chat-header"><div className="chat-agent-icon"><Bot size={21} /></div><div><strong>ProfitPulse Business Analyst</strong><span><i className="online-dot" /> Groq · LangGraph tool-calling</span></div><span className="chat-secure"><ShieldCheck size={14} /> Read-only tools</span></div>
        <div className="chat-messages">
          {messages.map((message) => <div key={message.id} className={`message-row ${message.role === 'user' ? 'message-user' : ''}`}>
            {message.role === 'assistant' && <div className="message-avatar"><Sparkles size={15} /></div>}
            <div className={`message-bubble ${message.role === 'user' ? 'user-bubble' : 'assistant-bubble'} ${message.error ? 'error-bubble' : ''}`}>
              {message.role === 'assistant' ? <div className="markdown-content"><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown></div> : message.content}
              {message.result?.sources && message.result.sources.length > 0 && <div className="answer-sources"><div className="source-label"><ShieldCheck size={13} /> SOURCES USED</div>{message.result.sources.map((source) => <span className="source-chip" key={`${source.document_id}-${source.page_number}`}><FileText size={12} />{source.filename} · p. {source.page_number}</span>)}</div>}
              {message.result?.tools_used && message.result.tools_used.length > 0 && <details className="tool-details"><summary><Zap size={12} /> {message.result.tools_used.length} tool{message.result.tools_used.length === 1 ? '' : 's'} used <ChevronDown size={12} /></summary><div className="tool-list">{message.result.tools_used.map((tool) => <span key={tool}>{tool}</span>)}</div></details>}
              {message.result?.provider && <div className="message-meta">{message.result.provider} · {message.result.model}</div>}
            </div>
          </div>)}
          {sending && <div className="message-row"><div className="message-avatar"><Sparkles size={15} /></div><div className="message-bubble assistant-bubble typing-bubble"><span /><span /><span /> <em>Investigating your question…</em></div></div>}
          <div ref={bottomRef} />
        </div>
        {messages.length === 1 && <div className="prompt-suggestions"><span>TRY ASKING</span><div>{prompts.map((prompt) => <button key={prompt} onClick={() => void submit(prompt)}>{prompt}<ArrowUpRight size={13} /></button>)}</div></div>}
        <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          <textarea aria-label="Ask ProfitPulse" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit(); } }} placeholder="Ask about revenue, profitability, inventory or company policies…" rows={2} />
          <div className="composer-bottom"><span><ShieldCheck size={13} /> Connected data · Read-only analysis</span><button className="send-button" disabled={!question.trim() || sending} type="submit">{sending ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />}<span>Send</span></button></div>
        </form>
      </div>
      <aside className="analyst-side-panel"><div className="side-panel-heading"><Sparkles size={16} /><strong>What I can investigate</strong></div><div className="capability-card"><span className="capability-icon cap-blue"><Activity size={16} /></span><div><strong>Financial intelligence</strong><p>Revenue, gross profit, EBITDA, margins and financial trends.</p></div></div><div className="capability-card"><span className="capability-icon cap-purple"><FileText size={16} /></span><div><strong>Company knowledge</strong><p>Policies, procedures and uploaded documents with citations.</p></div></div><div className="capability-card"><span className="capability-icon cap-green"><Package size={16} /></span><div><strong>Operations</strong><p>Product performance, regions and inventory health.</p></div></div><div className="analyst-note"><ShieldCheck size={15} /><span>The agent uses predefined read-only tools. Answers are decision support, not audited or professional advice.</span></div></aside>
    </div>
  </div>;
}

function KnowledgePage({ documents, onRefresh, onNotice }: { documents: KnowledgeDocument[]; onRefresh: () => Promise<void>; onNotice: (message: string) => void }) {
  const [uploading, setUploading] = useState(false);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [hits, setHits] = useState<KnowledgeHit[]>([]);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const upload = async (file?: File) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { setError('The selected file exceeds the 10 MB upload limit.'); return; }
    setUploading(true); setError(''); setHits([]);
    const form = new FormData(); form.append('file', file);
    try {
      const result = await apiRequest<{ filename: string; chunk_count: number; page_count: number; status: string }>('/api/v1/knowledge/documents', { method: 'POST', body: form });
      await onRefresh();
      onNotice(`${result.filename} indexed successfully · ${result.chunk_count} chunk${result.chunk_count === 1 ? '' : 's'} · ${result.page_count} page${result.page_count === 1 ? '' : 's'}.`);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Document upload failed.');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const search = async (event: FormEvent) => {
    event.preventDefault();
    if (query.trim().length < 3) return;
    setSearching(true); setError('');
    try {
      const result = await apiRequest<{ results: KnowledgeHit[] }>('/api/v1/knowledge/search', { method: 'POST', body: JSON.stringify({ query: query.trim(), top_k: 5 }) });
      setHits(result.results || []);
      if (!result.results?.length) onNotice('No matching passages were found in this organization’s indexed documents.');
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : 'Knowledge search failed.');
    } finally { setSearching(false); }
  };

  const remove = async (document: KnowledgeDocument) => {
    if (!window.confirm(`Delete ${document.filename} from this organization's knowledge base?`)) return;
    try {
      await apiRequest(`/api/v1/knowledge/documents/${document.document_id}`, { method: 'DELETE' });
      await onRefresh(); setHits([]); onNotice(`${document.filename} was deleted from the knowledge base.`);
    } catch (deleteError) { setError(deleteError instanceof Error ? deleteError.message : 'Document deletion failed.'); }
  };

  return <div className="knowledge-page">
    <div className="page-heading"><div><div className="eyebrow">COMPANY KNOWLEDGE <span className="eyebrow-line" /></div><h1>Give your AI the full picture.</h1><p>Upload policies and business documents. ProfitPulse indexes them for tenant-scoped semantic search and cited answers.</p></div><button className="primary-button" onClick={() => fileRef.current?.click()} disabled={uploading}><UploadCloud size={16} />{uploading ? 'Indexing…' : 'Upload document'}</button></div>
    <input ref={fileRef} className="visually-hidden" type="file" accept=".pdf,.txt,.md,.markdown,.csv" onChange={(event) => void upload(event.target.files?.[0])} />
    {error && <div className="alert alert-warning"><CircleHelp size={16} /><span>{error}</span><button onClick={() => setError('')}><X size={14} /></button></div>}
    <div className="knowledge-stats"><div className="knowledge-stat"><span className="knowledge-stat-icon"><FileText size={18} /></span><div><strong>{documents.length}</strong><span>Indexed documents</span></div></div><div className="knowledge-stat"><span className="knowledge-stat-icon"><Database size={18} /></span><div><strong>{documents.reduce((sum, item) => sum + numberValue(item.chunk_count), 0)}</strong><span>Searchable chunks</span></div></div><div className="knowledge-stat"><span className="knowledge-stat-icon"><ShieldCheck size={18} /></span><div><strong>Isolated</strong><span>Organization scoped</span></div></div></div>
    <section className="panel upload-panel"><div className="upload-drop-icon"><FileUp size={24} /></div><div className="upload-copy"><h3>Build your company knowledge base</h3><p>Upload PDF, TXT, Markdown or CSV documents. Selectable text is indexed with filename and page metadata. Maximum file size: 10 MB.</p><div className="file-types"><span>PDF</span><span>TXT</span><span>MD</span><span>CSV</span></div></div><button className="secondary-button" onClick={() => fileRef.current?.click()} disabled={uploading}>{uploading ? <LoaderCircle className="spin" size={15} /> : <Plus size={15} />} Add a document</button></section>
    <section className="panel knowledge-search-panel"><div className="panel-header"><div><h3>Search company knowledge</h3><p>Find relevant passages across your uploaded documents.</p></div><span className="panel-icon"><Search size={17} /></span></div><form className="knowledge-search-form" onSubmit={search}><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="e.g. Who approves an unbudgeted purchase above INR 25,000?" /><button type="submit" disabled={searching || query.trim().length < 3}>{searching ? <LoaderCircle className="spin" size={15} /> : 'Search'}</button></form>
      {hits.length > 0 && <div className="search-results"><div className="result-heading">{hits.length} matching passage{hits.length === 1 ? '' : 's'}</div>{hits.map((hit) => <div className="knowledge-hit" key={hit.source.document_id + hit.source.page_number + hit.text.slice(0, 12)}><div className="hit-source"><FileText size={13} />{hit.source.citation}<span>Distance {hit.distance?.toFixed(3) ?? 'n/a'}</span></div><p>{hit.text}</p></div>)}</div>}
    </section>
    <section className="panel documents-panel"><div className="panel-header"><div><h3>Indexed documents</h3><p>Documents available to the current demo organization.</p></div><button className="icon-button" title="Refresh documents" onClick={() => void onRefresh()}><RefreshCw size={16} /></button></div>
      {documents.length === 0 ? <EmptyState title="Your knowledge base is empty" detail="Upload a policy, procedure or business document to get started." /> : <div className="document-list">{documents.map((document) => <div className="document-row" key={document.document_id}><div className="document-icon"><FileText size={19} /></div><div className="document-copy"><strong>{document.filename}</strong><span>{document.chunk_count} searchable chunk{document.chunk_count === 1 ? '' : 's'}{document.uploaded_at ? ` · ${new Date(document.uploaded_at).toLocaleDateString('en-IN')}` : ''}</span></div><span className="document-status"><Check size={13} /> Indexed</span><button className="icon-button delete-button" aria-label={`Delete ${document.filename}`} title="Delete document" onClick={() => void remove(document)}><Trash2 size={15} /></button></div>)}</div>}
    </section>
    <div className="knowledge-footnote"><ShieldCheck size={15} /><span>Retrieval is filtered by organization ID. Scanned PDFs require OCR and are not indexed by this demo.</span></div>
  </div>;
}

function ProductsPage({ products, regions, currency, loading }: { products: ProductRow[]; regions: RegionRow[]; currency: string; loading: boolean }) {
  const bestProduct = products[0];
  return <div className="products-page"><div className="page-heading"><div><div className="eyebrow">COMMERCIAL PERFORMANCE <span className="eyebrow-line" /></div><h1>Know what moves the needle.</h1><p>Explore delivered-order product contribution and regional sales performance.</p></div></div>
    {bestProduct && <div className="insight-banner product-banner"><div className="insight-icon"><TrendingUp size={18} /></div><div className="insight-copy"><strong>{bestProduct.product_name} leads gross profit contribution.</strong><span>{formatCurrency(bestProduct.gross_profit, currency)} gross profit across {formatNumber(bestProduct.units_sold)} units in the selected period.</span></div></div>}
    <div className="dashboard-grid product-grid"><section className="panel chart-panel large-panel"><div className="panel-header"><div><h3>Gross profit by product</h3><p>Top products · delivered orders only</p></div><span className="panel-chip">{products.length} products</span></div>{loading ? <ChartSkeleton /> : products.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={products.slice(0, 8)} layout="vertical" margin={{ left: 14, right: 16, top: 5, bottom: 5 }}><CartesianGrid strokeDasharray="3 5" horizontal={false} stroke="#e9edf3" /><XAxis type="number" tick={{ fill: '#8b95a5', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} /><YAxis type="category" dataKey="product_name" width={115} tick={{ fill: '#667085', fontSize: 11 }} axisLine={false} tickLine={false} /><Tooltip formatter={(value) => formatCurrency(value, currency)} /><Bar dataKey="gross_profit" name="Gross profit" fill="#6f8fce" radius={[0, 5, 5, 0]} barSize={19} /></BarChart></ResponsiveContainer></div> : <EmptyState title="No product data" detail="Delivered order lines will appear here." />}</section>
      <section className="panel chart-panel"><div className="panel-header"><div><h3>Revenue by region</h3><p>Delivered orders</p></div><span className="panel-icon"><Building2 size={17} /></span></div>{loading ? <ChartSkeleton /> : regions.length ? <div className="region-list">{regions.map((region, index) => { const share = regions.reduce((sum, item) => sum + numberValue(item.net_sales), 0) ? (numberValue(region.net_sales) / regions.reduce((sum, item) => sum + numberValue(item.net_sales), 0)) * 100 : 0; return <div className="region-item" key={region.region}><div className="region-top"><span className="region-rank">0{index + 1}</span><strong>{region.region}</strong><b>{formatCurrency(region.net_sales, currency, true)}</b></div><div className="region-bar"><span style={{ width: `${Math.max(share, 2)}%` }} /></div><div className="region-meta"><span>{share.toFixed(1)}% of regional sales</span><span>{formatNumber(region.order_count)} orders</span></div></div>; })}</div> : <EmptyState title="No region data" detail="Regional performance is not available for this period." />}</section></div>
    <section className="panel table-panel"><div className="panel-header"><div><h3>Product performance</h3><p>Ranking by gross profit · delivered-order basis</p></div></div><div className="table-scroll"><table><thead><tr><th>PRODUCT</th><th>SKU</th><th>UNITS SOLD</th><th>ORDERS</th><th>NET SALES</th><th>GROSS PROFIT</th></tr></thead><tbody>{products.map((product) => <tr key={product.sku}><td><strong>{product.product_name}</strong><span className="table-sub">{product.category || 'Uncategorised'}</span></td><td>{product.sku}</td><td>{formatNumber(product.units_sold)}</td><td>{formatNumber(product.order_count)}</td><td>{formatCurrency(product.net_sales, currency)}</td><td className="positive-value">{formatCurrency(product.gross_profit, currency)}</td></tr>)}</tbody></table>{!loading && !products.length && <EmptyState title="No products for this period" detail="Try another date range." />}</div></section>
    <p className="data-basis-note"><Clock3 size={13} /> Product and regional figures use delivered orders and item-line totals; order-level tax and shipping are excluded by the backend calculation.</p>
  </div>;
}

function InventoryPage({ inventory, currency, loading, alertCount }: { inventory: InventoryRow[]; currency: string; loading: boolean; alertCount: number }) {
  const totalValue = inventory.reduce((sum, item) => sum + numberValue(item.inventory_value), 0);
  const totalUnits = inventory.reduce((sum, item) => sum + numberValue(item.quantity_on_hand), 0);
  return <div className="inventory-page"><div className="page-heading"><div><div className="eyebrow">SUPPLY & OPERATIONS <span className="eyebrow-line" /></div><h1>Stay ahead of stock pressure.</h1><p>Monitor inventory value, available units and products at or below reorder levels.</p></div></div>
    <div className="metric-grid inventory-metrics"><MetricCard label="Inventory value" value={formatCurrency(totalValue, currency, true)} icon={<Wallet size={18} />} tone="blue" detail="Latest available snapshot" loading={loading} /><MetricCard label="Units on hand" value={formatNumber(totalUnits)} icon={<Boxes size={18} />} tone="green" detail={`${inventory.length} product / warehouse rows`} loading={loading} /><MetricCard label="Reorder alerts · 1 Nov" value={formatNumber(alertCount)} icon={<Activity size={18} />} tone="orange" detail={alertCount ? 'At or below reorder level' : 'No items currently flagged'} trend={alertCount ? 'negative' : 'positive'} loading={loading} /></div>
    <section className="panel table-panel inventory-table"><div className="panel-header"><div><h3>Inventory health</h3><p>Latest seeded inventory snapshot · 1 Nov 2026</p></div><span className={`status-pill ${alertCount ? 'status-warn' : 'status-good'}`}>{alertCount ? `${alertCount} alerts` : 'Stock looks clear'}</span></div><div className="table-scroll"><table><thead><tr><th>PRODUCT</th><th>SKU</th><th>CATEGORY</th><th>ON HAND</th><th>INVENTORY VALUE</th><th>STATUS</th></tr></thead><tbody>{inventory.map((item) => <tr key={`${item.sku}-${item.snapshot_date || ''}`}><td><strong>{item.product_name}</strong><span className="table-sub">Snapshot {item.snapshot_date || INVENTORY_SNAPSHOT_DATE}</span></td><td>{item.sku}</td><td>{item.category || '—'}</td><td>{formatNumber(item.quantity_on_hand)}</td><td>{formatCurrency(item.inventory_value, currency)}</td><td><span className={`status-pill ${item.reorder_alert ? 'status-warn' : 'status-good'}`}>{item.reorder_alert ? 'Reorder needed' : 'Healthy'}</span></td></tr>)}</tbody></table>{!loading && !inventory.length && <EmptyState title="No inventory snapshot found" detail="The API did not return an inventory snapshot for this date." />}</div></section>
    <div className="knowledge-footnote"><CircleHelp size={15} /><span>Reorder alerts compare aggregate on-hand quantity with the product reorder level. Confirm warehouse-level and supplier lead-time details before placing orders.</span></div>
  </div>;
}


type SupplyChainOverview = {
  open_purchase_orders: number;
  active_shipments: number;
  delayed_shipments: number;
  stale_tracking_shipments: number;
  avg_transit_days?: number | null;
  open_po_goods_value: number;
  total_shipments: number;
};
type SupplyShipment = {
  id: string; shipment_number: string; status: string; transport_mode: string;
  incoterm?: string | null;
  supplier_name: string; supplier_code: string; origin_city: string; origin_state?: string;
  origin_country: string; destination_warehouse: string; destination_city?: string;
  carrier_name?: string; tracking_number?: string; current_eta_at?: string | null;
  promised_arrival_at?: string | null; latest_event_code?: string | null;
  latest_location?: string | null; latest_event_at?: string | null;
  transit_days?: number | null; delay_days?: number; goods_value?: number;
  charges_total?: number; currency?: string;
};
type SupplierScorecard = {
  supplier_id: string;
  supplier_code: string;
  supplier_name: string;
  purchase_order_count: number;
  open_po_count?: number;
  completed_po_count: number;
  completed_po_with_due_date_count?: number;
  on_time_po_count?: number;
  on_time_po_pct?: number | null;
  otif_pct?: number | null;
  otif_po_count?: number;
  quantity_ordered?: number;
  quantity_received?: number;
  fill_rate_pct?: number | null;
  completed_quantity_ordered?: number;
  completed_quantity_received?: number;
  completed_po_fill_rate_pct?: number | null;
  outstanding_quantity?: number;
  shipment_count: number;
  completed_shipments: number;
  completed_shipments_with_due_date?: number;
  on_time_shipments?: number;
  on_time_shipment_pct?: number | null;
  avg_procurement_lead_days?: number | null;
  avg_transit_days?: number | null;
  rejected_quantity?: number;
  receipt_quantity?: number;
  rejected_quantity_pct?: number | null;
  open_po_value: number;
};
type SupplyException = {
  id: string; shipment_number: string; exception_type: string; status: string;
  supplier_name: string; origin_city: string; origin_country: string;
  destination_city?: string; current_eta_at?: string | null; overdue_days?: number | null;
  latest_location?: string | null; latest_event_at?: string | null; carrier_name?: string;
};

function displayDate(value?: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value.slice(0, 10) : parsed.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function statusClass(status: string): string {
  if (['delivered', 'received'].includes(status)) return 'status-good';
  if (['delayed', 'exception', 'cancelled'].includes(status)) return 'status-warn';
  return 'status-neutral';
}

type SupplySupplierSite = {
  supplier_id: string; supplier_code: string; supplier_name: string;
  supplier_site_id?: string | null; site_code?: string | null; site_name?: string | null;
  site_type?: string | null; origin_city?: string | null; origin_state?: string | null;
  origin_country?: string | null; origin_port?: string | null; origin_country_code?: string | null;
  default_lead_time_days?: number | null; preferred_transport_mode?: string | null;
  is_primary?: boolean | null;
};
type SupplyCatalog = {
  suppliers: Array<{ id: string; supplier_code: string; name: string; city?: string; state?: string }>;
  products: Array<{ id: string; sku: string; name: string; category: string; unit_of_measure: string; unit_cost: number }>;
  warehouses: Array<{ id: string; warehouse_code: string; name: string; city?: string; state?: string }>;
};
type SupplyPurchaseOrder = {
  id: string; po_number: string; supplier_id: string; supplier_name: string; supplier_code: string;
  order_date: string; expected_date?: string | null; received_date?: string | null; status: string;
  total_amount: number; line_count: number; quantity_ordered: number; quantity_received: number;
  outstanding_goods_value: number;
};
type SupplyTimelineItem = {
  shipment_item_id: string; purchase_order_id: string; po_number: string; product_id: string;
  sku: string; product_name: string; quantity_shipped: number; quantity_received: number;
  quantity_outstanding: number; unit_cost: number;
};
type SupplyTimeline = {
  shipment: SupplyShipment & { supplier_id: string; destination_warehouse_id: string };
  items: SupplyTimelineItem[];
  events: Array<{ event_code: string; status_after?: string | null; location_name?: string | null; occurred_at: string; notes?: string | null; source: string }>;
  costs: Array<{ cost_type: string; amount: number; currency: string; charge_date: string; description?: string }>;
};
type ReceiptDraftLine = SupplyTimelineItem & { receiveNow: string; acceptNow: string; rejectNow: string; inspectionNotes: string };

function localDateInput(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}
function localDateTimeInput(): string {
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
  return now.toISOString().slice(0, 16);
}
function toUtcIso(value: string): string | undefined {
  return value ? new Date(value).toISOString() : undefined;
}
function displayStatus(value: string): string { return value.replace(/_/g, ' '); }

function SupplyChainPage() {
  const [overview, setOverview] = useState<SupplyChainOverview | null>(null);
  const [shipments, setShipments] = useState<SupplyShipment[]>([]);
  const [scorecards, setScorecards] = useState<SupplierScorecard[]>([]);
  const [exceptions, setExceptions] = useState<SupplyException[]>([]);
  const [supplierSites, setSupplierSites] = useState<SupplySupplierSite[]>([]);
  const [catalog, setCatalog] = useState<SupplyCatalog>({ suppliers: [], products: [], warehouses: [] });
  const [purchaseOrders, setPurchaseOrders] = useState<SupplyPurchaseOrder[]>([]);
  const [currency, setCurrency] = useState('INR');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const defaultsApplied = useRef(false);

  // Supplier origin form
  const [siteSupplierId, setSiteSupplierId] = useState('');
  const [siteCode, setSiteCode] = useState('ORIGIN-02');
  const [siteName, setSiteName] = useState('Secondary origin');
  const [siteType, setSiteType] = useState('factory');
  const [siteCity, setSiteCity] = useState('');
  const [siteState, setSiteState] = useState('');
  const [siteCountry, setSiteCountry] = useState('India');
  const [siteCountryCode, setSiteCountryCode] = useState('IN');
  const [siteOriginPort, setSiteOriginPort] = useState('');
  const [siteLeadDays, setSiteLeadDays] = useState('5');
  const [siteMode, setSiteMode] = useState('road');
  const [sitePrimary, setSitePrimary] = useState(false);

  // Purchase order form
  const [poSupplierId, setPoSupplierId] = useState('');
  const [poNumber, setPoNumber] = useState('');
  const [poOrderDate, setPoOrderDate] = useState(localDateInput());
  const [poExpectedDate, setPoExpectedDate] = useState('');
  const [poProductId, setPoProductId] = useState('');
  const [poQuantity, setPoQuantity] = useState('25');
  const [poUnitCost, setPoUnitCost] = useState('');

  // Shipment creation form
  const [shipmentPoId, setShipmentPoId] = useState('');
  const [shipmentNumber, setShipmentNumber] = useState('');
  const [shipmentSiteId, setShipmentSiteId] = useState('');
  const [shipmentWarehouseId, setShipmentWarehouseId] = useState('');
  const [shipmentMode, setShipmentMode] = useState('road');
  const [shipmentCarrier, setShipmentCarrier] = useState('');
  const [shipmentTracking, setShipmentTracking] = useState('');
  const [shipmentDeparture, setShipmentDeparture] = useState('');
  const [shipmentEta, setShipmentEta] = useState('');

  // Tracking update form
  const [selectedShipment, setSelectedShipment] = useState('');
  const [eventCode, setEventCode] = useState('in_transit');
  const [locationName, setLocationName] = useState('');
  const [eventNotes, setEventNotes] = useState('');
  const [eventEta, setEventEta] = useState('');

  // Goods receipt form
  const [receiptShipmentId, setReceiptShipmentId] = useState('');
  const [receiptTimeline, setReceiptTimeline] = useState<SupplyTimeline | null>(null);
  const [receiptNumber, setReceiptNumber] = useState('');
  const [receiptAt, setReceiptAt] = useState(localDateTimeInput());
  const [receiptStatus, setReceiptStatus] = useState('passed');
  const [receiptNotes, setReceiptNotes] = useState('');
  const [receiptLines, setReceiptLines] = useState<ReceiptDraftLine[]>([]);
  const [loadingTimeline, setLoadingTimeline] = useState(false);
  const [viewTimeline, setViewTimeline] = useState<SupplyTimeline | null>(null);
  const [viewTimelineLoading, setViewTimelineLoading] = useState(false);

  // Recorded shipment charges (not yet capitalized into inventory/GL).
  const [chargeShipmentId, setChargeShipmentId] = useState('');
  const [chargeType, setChargeType] = useState('freight');
  const [chargeAmount, setChargeAmount] = useState('');
  const [chargeDate, setChargeDate] = useState(localDateInput());
  const [chargeDescription, setChargeDescription] = useState('');
  const [chargeReference, setChargeReference] = useState('');

  const loadSupplyChain = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError('');
    try {
      const [overviewData, shipmentData, supplierData, exceptionData, catalogData, poData, scorecardData] = await Promise.all([
        apiRequest<{ currency?: string } & SupplyChainOverview>('/api/v1/supply-chain/overview'),
        apiRequest<{ shipments: SupplyShipment[] }>('/api/v1/supply-chain/shipments?limit=100'),
        apiRequest<{ suppliers: SupplySupplierSite[] }>('/api/v1/supply-chain/suppliers'),
        apiRequest<{ exceptions: SupplyException[] }>('/api/v1/supply-chain/exceptions'),
        apiRequest<SupplyCatalog>('/api/v1/supply-chain/catalog'),
        apiRequest<{ purchase_orders: SupplyPurchaseOrder[] }>('/api/v1/supply-chain/purchase-orders?limit=100'),
        apiRequest<{ scorecards: SupplierScorecard[] }>('/api/v1/supply-chain/supplier-scorecards'),
      ]);
      setOverview(overviewData);
      setCurrency(overviewData.currency || 'INR');
      setShipments(shipmentData.shipments || []);
      setSupplierSites(supplierData.suppliers || []);
      setExceptions(exceptionData.exceptions || []);
      setCatalog(catalogData);
      setPurchaseOrders(poData.purchase_orders || []);
      setScorecards(scorecardData.scorecards || []);
      const active = (shipmentData.shipments || []).find((item) => !['delivered', 'cancelled'].includes(item.status));
      const arrived = (shipmentData.shipments || []).find((item) => item.status === 'arrived_at_warehouse');
      setSelectedShipment((current) => current || active?.id || '');
      setReceiptShipmentId((current) => current || arrived?.id || '');
      setChargeShipmentId((current) => current || active?.id || '');
      if (!defaultsApplied.current) {
        if (catalogData.suppliers.length) {
          setPoSupplierId(catalogData.suppliers[0].id);
          setSiteSupplierId(catalogData.suppliers[0].id);
        }
        if (catalogData.products.length) {
          setPoProductId(catalogData.products[0].id);
          setPoUnitCost(String(catalogData.products[0].unit_cost));
        }
        if (catalogData.warehouses.length) setShipmentWarehouseId(catalogData.warehouses[0].id);
        const firstOpenPo = (poData.purchase_orders || []).find((item) => ['sent', 'partially_received'].includes(item.status));
        if (firstOpenPo) {
          setShipmentPoId(firstOpenPo.id);
          const firstOrigin = (supplierData.suppliers || []).find((item) => item.supplier_id === firstOpenPo.supplier_id && item.supplier_site_id);
          if (firstOrigin?.supplier_site_id) setShipmentSiteId(firstOrigin.supplier_site_id);
        }
        defaultsApplied.current = true;
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Supply-chain data could not be loaded.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void loadSupplyChain(); }, [loadSupplyChain]);

  const runMutation = async (label: string, request: () => Promise<unknown>) => {
    setSaving(true); setError(''); setNotice('');
    try {
      await request();
      setNotice(label);
      await loadSupplyChain(true);
    } catch (mutationError) {
      setError(mutationError instanceof Error ? mutationError.message : 'The operation could not be completed.');
    } finally { setSaving(false); }
  };

  const createSupplierSite = async (event: FormEvent) => {
    event.preventDefault();
    if (!siteSupplierId) return;
    await runMutation('Supplier origin site saved.', () => apiRequest(`/api/v1/supply-chain/suppliers/${siteSupplierId}/sites`, {
      method: 'POST', body: JSON.stringify({ site_code: siteCode, site_name: siteName, site_type: siteType, origin_city: siteCity,
        origin_state: siteState || undefined, origin_country: siteCountry, origin_country_code: siteCountryCode || undefined,
        origin_port: siteOriginPort || undefined, default_lead_time_days: siteLeadDays ? Number(siteLeadDays) : undefined,
        preferred_transport_mode: siteMode, is_primary: sitePrimary }),
    }));
  };

  const createPurchaseOrder = async (event: FormEvent) => {
    event.preventDefault();
    if (!poSupplierId || !poProductId) return;
    const selectedProduct = catalog.products.find((item) => item.id === poProductId);
    await runMutation('Purchase order created as a draft. Review it below and send it to the supplier when approved.', async () => {
      const result = await apiRequest<{ purchase_order_id: string }>('/api/v1/supply-chain/purchase-orders', {
        method: 'POST', body: JSON.stringify({ supplier_id: poSupplierId, po_number: poNumber,
          order_date: poOrderDate, expected_date: poExpectedDate || undefined,
          items: [{ product_id: poProductId, quantity_ordered: Number(poQuantity), unit_cost: Number(poUnitCost || selectedProduct?.unit_cost || 0) }] }),
      });
      setPoNumber('');
      return result;
    });
  };

  const sendPurchaseOrder = async (id: string) => runMutation('Purchase order sent and made available for shipment planning.', () =>
    apiRequest(`/api/v1/supply-chain/purchase-orders/${id}/send`, { method: 'POST' }));

  const createShipment = async (event: FormEvent) => {
    event.preventDefault();
    const po = purchaseOrders.find((item) => item.id === shipmentPoId);
    if (!po || !shipmentWarehouseId) return;
    const originSite = supplierSites.find((item) => item.supplier_id === po.supplier_id && item.supplier_site_id === shipmentSiteId);
    if (!originSite) { setError('Select or create a supplier origin site before dispatching this shipment.'); return; }
    await runMutation('Inbound shipment created. Add manual tracking milestones as the goods move.', () =>
      apiRequest('/api/v1/supply-chain/shipments', { method: 'POST', body: JSON.stringify({
        shipment_number: shipmentNumber, supplier_id: po.supplier_id, supplier_site_id: shipmentSiteId || undefined,
        purchase_order_ids: [shipmentPoId], destination_warehouse_id: shipmentWarehouseId,
        origin_city: originSite?.origin_city, origin_state: originSite?.origin_state,
        origin_country: originSite?.origin_country, transport_mode: shipmentMode,
        carrier_name: shipmentCarrier || undefined, tracking_number: shipmentTracking || undefined,
        planned_departure_at: toUtcIso(shipmentDeparture), promised_arrival_at: toUtcIso(shipmentEta),
        current_eta_at: toUtcIso(shipmentEta),
      }) }),
    );
    setShipmentNumber(''); setShipmentCarrier(''); setShipmentTracking('');
  };

  const submitTrackingEvent = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedShipment) return;
    await runMutation('Tracking milestone recorded. Status, ETA and exception indicators refreshed.', () =>
      apiRequest(`/api/v1/supply-chain/shipments/${selectedShipment}/events`, {
        method: 'POST', body: JSON.stringify({ event_code: eventCode, location_name: locationName || undefined,
          notes: eventNotes || undefined, current_eta_at: toUtcIso(eventEta) }),
      }));
    setLocationName(''); setEventNotes(''); setEventEta('');
  };

  const loadReceiptTimeline = async (shipmentId: string) => {
    setReceiptShipmentId(shipmentId); setReceiptTimeline(null); setReceiptLines([]);
    if (!shipmentId) return;
    setLoadingTimeline(true); setError('');
    try {
      const payload = await apiRequest<SupplyTimeline>(`/api/v1/supply-chain/shipments/${shipmentId}/timeline`);
      setReceiptTimeline(payload);
      setReceiptLines(payload.items.filter((item) => item.quantity_outstanding > 0).map((item) => ({
        ...item, receiveNow: String(item.quantity_outstanding), acceptNow: String(item.quantity_outstanding),
        rejectNow: '0', inspectionNotes: '',
      })));
    } catch (timelineError) {
      setError(timelineError instanceof Error ? timelineError.message : 'Shipment items could not be loaded.');
    } finally { setLoadingTimeline(false); }
  };

  const updateReceiptLine = (shipmentItemId: string, key: 'receiveNow' | 'acceptNow' | 'rejectNow' | 'inspectionNotes', value: string) => {
    setReceiptLines((rows) => rows.map((row) => row.shipment_item_id === shipmentItemId ? { ...row, [key]: value } : row));
  };

  const submitGoodsReceipt = async (event: FormEvent) => {
    event.preventDefault();
    if (!receiptShipmentId || !receiptLines.length) return;
    const invalid = receiptLines.some((row) => {
      const received = Number(row.receiveNow); const accepted = Number(row.acceptNow); const rejected = Number(row.rejectNow);
      return received <= 0 || accepted < 0 || rejected < 0 || Math.abs(accepted + rejected - received) > 0.0001 || received > row.quantity_outstanding;
    });
    if (invalid) { setError('For each line, accepted + rejected must equal received, and received cannot exceed outstanding shipped quantity.'); return; }
    await runMutation('Goods receipt recorded. Accepted quantities are now reflected in inventory movements; rejected goods remain excluded from available stock.', () =>
      apiRequest(`/api/v1/supply-chain/shipments/${receiptShipmentId}/receipts`, { method: 'POST', body: JSON.stringify({
        receipt_number: receiptNumber, received_at: toUtcIso(receiptAt), inspection_status: receiptStatus, notes: receiptNotes || undefined,
        items: receiptLines.map((row) => ({ shipment_item_id: row.shipment_item_id,
          quantity_received: Number(row.receiveNow), quantity_accepted: Number(row.acceptNow),
          quantity_rejected: Number(row.rejectNow), inspection_notes: row.inspectionNotes || undefined })),
      }) }),
    );
    setReceiptNumber(''); setReceiptNotes(''); setReceiptTimeline(null); setReceiptLines([]);
  };


  const loadShipmentTimeline = async (shipmentId: string) => {
    setViewTimelineLoading(true); setError('');
    try {
      const payload = await apiRequest<SupplyTimeline>(`/api/v1/supply-chain/shipments/${shipmentId}/timeline`);
      setViewTimeline(payload);
    } catch (timelineError) {
      setError(timelineError instanceof Error ? timelineError.message : 'Shipment timeline could not be loaded.');
    } finally { setViewTimelineLoading(false); }
  };

  const submitShipmentCharge = async (event: FormEvent) => {
    event.preventDefault();
    if (!chargeShipmentId || Number(chargeAmount) < 0 || !chargeDate) return;
    await runMutation('Shipment charge recorded. It remains a separate logistics cost until landed-cost allocation is implemented.', () =>
      apiRequest(`/api/v1/supply-chain/shipments/${chargeShipmentId}/charges`, {
        method: 'POST', body: JSON.stringify({ cost_type: chargeType, amount: Number(chargeAmount),
          charge_date: chargeDate, description: chargeDescription || undefined, reference: chargeReference || undefined }),
      }));
    setChargeAmount(''); setChargeDescription(''); setChargeReference('');
  };

  const activeShipments = shipments.filter((item) => !['delivered', 'cancelled'].includes(item.status));
  const openPurchaseOrders = purchaseOrders.filter((item) => ['sent', 'partially_received'].includes(item.status));
  const supplierOptions = catalog.suppliers;

  return <div className="supply-chain-page">
    <div className="page-heading">
      <div><div className="eyebrow">PROCUREMENT · LOGISTICS · INBOUND <span className="eyebrow-line" /></div>
        <h1>See every shipment before it becomes a stock problem.</h1>
        <p>Trace goods from supplier origin to warehouse receipt, measure lead times and investigate delivery exceptions.</p></div>
      <button className="secondary-button" onClick={() => void loadSupplyChain(true)} disabled={loading}>{loading ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />} Refresh supply chain</button>
    </div>
    {error && <div className="alert alert-warning"><CircleHelp size={16}/><span>{error}</span></div>}
    {notice && <div className="alert alert-info"><Check size={16}/><span>{notice}</span></div>}
    <div className="metric-grid supply-metrics">
      <MetricCard label="Open purchase orders" value={formatNumber(overview?.open_purchase_orders)} icon={<FileText size={18}/>} tone="blue" detail="Sent or partially received" loading={loading}/>
      <MetricCard label="Active inbound shipments" value={formatNumber(overview?.active_shipments)} icon={<Truck size={18}/>} tone="green" detail="Not yet fully received or cancelled" loading={loading}/>
      <MetricCard label="Delayed shipments" value={formatNumber(overview?.delayed_shipments)} icon={<AlertTriangle size={18}/>} tone="orange" detail={`${formatNumber(overview?.stale_tracking_shipments)} with stale tracking`} trend={overview?.delayed_shipments ? 'negative' : 'positive'} loading={loading}/>
      <MetricCard label="Average transit time" value={overview?.avg_transit_days == null ? '—' : `${formatNumber(overview.avg_transit_days, 1)} days`} icon={<Clock3 size={18}/>} tone="purple" detail="Completed shipments · historical" loading={loading}/>
    </div>
    <div className="supply-summary-strip"><div><span>Outstanding PO goods value</span><strong>{formatCurrency(overview?.open_po_goods_value, currency, true)}</strong></div><div><span>Shipments recorded</span><strong>{formatNumber(overview?.total_shipments)}</strong></div><div><span>Tracking approach</span><strong>Manual event updates</strong></div></div>

    <div className="supply-workflow-grid">
      <section className="panel tracking-panel"><div className="panel-header"><div><h3><Building2 size={15}/> Add supplier origin site</h3><p>Record the factory, warehouse or port goods are dispatched from.</p></div></div>
        <form className="tracking-form" onSubmit={createSupplierSite}>
          <label>Supplier<select required value={siteSupplierId} onChange={(e) => setSiteSupplierId(e.target.value)}><option value="">Select supplier</option>{supplierOptions.map((item) => <option key={item.id} value={item.id}>{item.supplier_code} · {item.name}</option>)}</select></label>
          <div className="supply-form-row"><label>Site code<input required value={siteCode} onChange={(e) => setSiteCode(e.target.value)} maxLength={40}/></label><label>Site type<select value={siteType} onChange={(e) => setSiteType(e.target.value)}><option value="factory">Factory</option><option value="warehouse">Warehouse</option><option value="distribution_center">Distribution centre</option><option value="port">Port</option><option value="other">Other</option></select></label></div>
          <label>Site name<input required value={siteName} onChange={(e) => setSiteName(e.target.value)} maxLength={160}/></label>
          <div className="supply-form-row"><label>Origin city<input required value={siteCity} onChange={(e) => setSiteCity(e.target.value)} maxLength={120}/></label><label>State<input value={siteState} onChange={(e) => setSiteState(e.target.value)} maxLength={120}/></label></div>
          <div className="supply-form-row"><label>Country<input required value={siteCountry} onChange={(e) => setSiteCountry(e.target.value)} maxLength={100}/></label><label>Country code<input value={siteCountryCode} onChange={(e) => setSiteCountryCode(e.target.value.toUpperCase().slice(0,2))} maxLength={2}/></label></div>
          <div className="supply-form-row"><label>Origin port (optional)<input value={siteOriginPort} onChange={(e) => setSiteOriginPort(e.target.value)} maxLength={120} placeholder="Port / terminal"/></label><label>Lead time (days)<input type="number" min="0" max="730" value={siteLeadDays} onChange={(e) => setSiteLeadDays(e.target.value)}/></label></div>
          <label>Preferred transport<select value={siteMode} onChange={(e) => setSiteMode(e.target.value)}><option value="road">Road</option><option value="rail">Rail</option><option value="air">Air</option><option value="sea">Sea</option><option value="courier">Courier</option><option value="multimodal">Multimodal</option></select></label>
          <label className="supply-checkbox"><input type="checkbox" checked={sitePrimary} onChange={(e) => setSitePrimary(e.target.checked)}/> Set as supplier's primary origin</label>
          <button className="primary-button" type="submit" disabled={saving || !siteSupplierId}>{saving ? 'Saving…' : <><Plus size={15}/> Save origin site</>}</button>
        </form>
      </section>

      <section className="panel tracking-panel"><div className="panel-header"><div><h3><FileText size={15}/> Create purchase order</h3><p>Commit product quantities and expected delivery dates.</p></div></div>
        <form className="tracking-form" onSubmit={createPurchaseOrder}>
          <label>Supplier<select required value={poSupplierId} onChange={(e) => setPoSupplierId(e.target.value)}><option value="">Select supplier</option>{supplierOptions.map((item) => <option key={item.id} value={item.id}>{item.supplier_code} · {item.name}</option>)}</select></label>
          <label>PO number<input required value={poNumber} onChange={(e) => setPoNumber(e.target.value)} placeholder="e.g. PO-2026-0140" maxLength={80}/></label>
          <div className="supply-form-row"><label>Order date<input type="date" required value={poOrderDate} onChange={(e) => setPoOrderDate(e.target.value)}/></label><label>Expected date<input type="date" value={poExpectedDate} onChange={(e) => setPoExpectedDate(e.target.value)}/></label></div>
          <label>Product<select required value={poProductId} onChange={(e) => { setPoProductId(e.target.value); const product = catalog.products.find((item) => item.id === e.target.value); setPoUnitCost(product ? String(product.unit_cost) : ''); }}><option value="">Select product</option>{catalog.products.map((item) => <option key={item.id} value={item.id}>{item.sku} · {item.name}</option>)}</select></label>
          <div className="supply-form-row"><label>Quantity<input type="number" required min="0.001" step="0.001" value={poQuantity} onChange={(e) => setPoQuantity(e.target.value)}/></label><label>Unit cost ({currency})<input type="number" required min="0" step="0.01" value={poUnitCost} onChange={(e) => setPoUnitCost(e.target.value)}/></label></div>
          <button className="primary-button" type="submit" disabled={saving || !poSupplierId || !poProductId}>{saving ? 'Creating…' : <><Plus size={15}/> Create draft PO</>}</button>
          <p className="supply-form-note">Creating a PO does not email the supplier. Review and mark it sent when your team has approved it.</p>
        </form>
      </section>

      <section className="panel tracking-panel"><div className="panel-header"><div><h3><Truck size={15}/> Dispatch inbound shipment</h3><p>Link a sent PO to its supplier origin, carrier and destination.</p></div></div>
        <form className="tracking-form" onSubmit={createShipment}>
          <label>Purchase order<select required value={shipmentPoId} onChange={(e) => { const nextPo = purchaseOrders.find((item) => item.id === e.target.value); setShipmentPoId(e.target.value); const site = supplierSites.find((item) => item.supplier_id === nextPo?.supplier_id && item.supplier_site_id && item.is_primary) || supplierSites.find((item) => item.supplier_id === nextPo?.supplier_id && item.supplier_site_id); setShipmentSiteId(site?.supplier_site_id || ''); }}><option value="">Select sent / partial PO</option>{openPurchaseOrders.map((item) => <option key={item.id} value={item.id}>{item.po_number} · {item.supplier_name}</option>)}</select></label>
          <label>Supplier origin site<select required value={shipmentSiteId} onChange={(e) => setShipmentSiteId(e.target.value)}><option value="">Select origin site</option>{supplierSites.filter((item) => item.supplier_id === purchaseOrders.find((po) => po.id === shipmentPoId)?.supplier_id && item.supplier_site_id).map((item) => <option key={item.supplier_site_id} value={item.supplier_site_id || ''}>{item.site_name} · {item.origin_city}, {item.origin_country}</option>)}</select></label>
          <label>Destination warehouse<select required value={shipmentWarehouseId} onChange={(e) => setShipmentWarehouseId(e.target.value)}><option value="">Select warehouse</option>{catalog.warehouses.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.city}</option>)}</select></label>
          <label>Shipment number<input required value={shipmentNumber} onChange={(e) => setShipmentNumber(e.target.value)} placeholder="e.g. SHP-2026-0088" maxLength={80}/></label>
          <div className="supply-form-row"><label>Mode<select value={shipmentMode} onChange={(e) => setShipmentMode(e.target.value)}><option value="road">Road</option><option value="rail">Rail</option><option value="air">Air</option><option value="sea">Sea</option><option value="courier">Courier</option><option value="multimodal">Multimodal</option></select></label><label>Carrier<input value={shipmentCarrier} onChange={(e) => setShipmentCarrier(e.target.value)} placeholder="Carrier name"/></label></div>
          <label>Tracking number<input value={shipmentTracking} onChange={(e) => setShipmentTracking(e.target.value)} placeholder="Carrier reference"/></label>
          <div className="supply-form-row"><label>Planned departure<input type="datetime-local" value={shipmentDeparture} onChange={(e) => setShipmentDeparture(e.target.value)}/></label><label>Promised arrival / ETA<input required type="datetime-local" value={shipmentEta} onChange={(e) => setShipmentEta(e.target.value)}/></label></div>
          <button className="primary-button" type="submit" disabled={saving || !shipmentPoId || !shipmentWarehouseId}>{saving ? 'Creating…' : <><Plus size={15}/> Create shipment</>}</button>
        </form>
      </section>

      <section className="panel tracking-panel"><div className="panel-header"><div><h3><Check size={15}/> Record goods receipt</h3><p>Reconcile physically received, accepted and rejected quantities.</p></div></div>
        <form className="tracking-form" onSubmit={submitGoodsReceipt}>
          <label>Shipment<select required value={receiptShipmentId} onChange={(e) => void loadReceiptTimeline(e.target.value)}><option value="">Select shipment that has arrived at warehouse</option>{shipments.filter((item) => item.status === 'arrived_at_warehouse').map((item) => <option key={item.id} value={item.id}>{item.shipment_number} · {item.supplier_name} · {displayStatus(item.status)}</option>)}</select></label>
          {loadingTimeline && <span className="supply-footnote">Loading shipment items…</span>}
          {receiptTimeline && <>
            <div className="supply-receipt-items">
              {receiptLines.map((line) => <div className="supply-receipt-line" key={line.shipment_item_id}>
                <strong>{line.product_name} <span>{line.sku}</span></strong>
                <small>Shipped {formatNumber(line.quantity_shipped)} · Outstanding {formatNumber(line.quantity_outstanding)}</small>
                <div className="supply-form-row supply-quantity-row">
                  <label>Received<input type="number" min="0" max={line.quantity_outstanding} step="0.001" value={line.receiveNow} onChange={(e) => updateReceiptLine(line.shipment_item_id,'receiveNow',e.target.value)}/></label>
                  <label>Accepted<input type="number" min="0" step="0.001" value={line.acceptNow} onChange={(e) => updateReceiptLine(line.shipment_item_id,'acceptNow',e.target.value)}/></label>
                  <label>Rejected<input type="number" min="0" step="0.001" value={line.rejectNow} onChange={(e) => updateReceiptLine(line.shipment_item_id,'rejectNow',e.target.value)}/></label>
                </div>
              </div>)}
              {!receiptLines.length && <EmptyState title="No outstanding shipment quantities" detail="This shipment has already been fully received."/>}
            </div>
            {receiptLines.length > 0 && <>
              <div className="supply-form-row"><label>Receipt number<input required value={receiptNumber} onChange={(e) => setReceiptNumber(e.target.value)} placeholder="GRN-2026-0001"/></label><label>Received at<input required type="datetime-local" value={receiptAt} onChange={(e) => setReceiptAt(e.target.value)}/></label></div>
              <label>Inspection status<select value={receiptStatus} onChange={(e) => setReceiptStatus(e.target.value)}><option value="passed">Passed</option><option value="partial">Partial</option><option value="failed">Failed</option><option value="pending">Pending</option></select></label>
              <label>Notes<textarea rows={2} value={receiptNotes} onChange={(e) => setReceiptNotes(e.target.value)} placeholder="Shortage, damage or inspection notes"/></label>
              <button className="primary-button" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Post goods receipt'}</button>
            </>}
          </>}
        </form>
      </section>
      <section className="panel tracking-panel">
        <div className="panel-header">
          <div>
            <h3><Wallet size={15}/> Record shipment charges</h3>
            <p>Capture freight and other logistics costs against an inbound shipment.</p>
          </div>
        </div>
        <form className="tracking-form" onSubmit={submitShipmentCharge}>
          <label>Shipment
            <select required value={chargeShipmentId} onChange={(e) => setChargeShipmentId(e.target.value)}>
              <option value="">Select shipment</option>
              {shipments.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.shipment_number} · {item.supplier_name}
                </option>
              ))}
            </select>
          </label>
          <label>Charge type
            <select value={chargeType} onChange={(e) => setChargeType(e.target.value)}>
              <option value="freight">Freight</option>
              <option value="insurance">Insurance</option>
              <option value="handling">Handling</option>
              <option value="customs">Customs</option>
              <option value="other">Other</option>
            </select>
          </label>
          <div className="supply-form-row">
            <label>Amount ({currency})
              <input required type="number" min="0.01" step="0.01"
                value={chargeAmount}
                onChange={(e) => setChargeAmount(e.target.value)}
                placeholder="e.g. 2500" />
            </label>
            <label>Charge date
              <input required type="date" value={chargeDate}
                onChange={(e) => setChargeDate(e.target.value)} />
            </label>
          </div>
          <label>Description (optional)
            <input value={chargeDescription}
              onChange={(e) => setChargeDescription(e.target.value)}
              maxLength={200} placeholder="e.g. Hyderabad delivery freight" />
          </label>
          <label>Reference (optional)
            <input value={chargeReference}
              onChange={(e) => setChargeReference(e.target.value)}
              maxLength={120} placeholder="Invoice or carrier reference" />
          </label>
          <button className="primary-button" type="submit"
            disabled={saving || !chargeShipmentId || !chargeAmount}>
            {saving ? 'Saving…' : <><Plus size={15}/> Record charge</>}
          </button>
          <p className="supply-form-note">
            Charges are recorded separately. They are not yet automatically
            allocated to inventory landed cost or posted to the general ledger.
          </p>
        </form>
      </section>
    </div>

    <section className="panel table-panel supply-exceptions-panel">
      <div className="panel-header"><div><h3><AlertTriangle size={15}/> Supply-chain exceptions</h3><p>Prioritise overdue ETAs, delayed shipments and stale tracking.</p></div><span className={`status-pill ${exceptions.length ? 'status-warn' : 'status-good'}`}>{exceptions.length ? `${exceptions.length} needs attention` : 'No open exceptions'}</span></div>
      {exceptions.length ? <div className="exception-list">{exceptions.map((item) => <div className="exception-row" key={item.id}><div className="exception-icon"><AlertTriangle size={15}/></div><div className="exception-copy"><strong>{item.shipment_number} · {item.supplier_name}</strong><span>{item.origin_city}, {item.origin_country} → {item.destination_city || 'Destination warehouse'} · {displayStatus(item.exception_type)}</span></div><div className="exception-meta"><strong>{item.overdue_days ? `${item.overdue_days} day${item.overdue_days === 1 ? '' : 's'} overdue` : displayDate(item.current_eta_at)}</strong><span>{item.latest_location || 'No latest location'}</span></div></div>)}</div> : <EmptyState title="No active supply-chain exceptions" detail="Overdue ETAs, delayed shipments and tracking gaps will appear here."/>}
    </section>

    <section className="panel table-panel"><div className="panel-header"><div><h3><FileText size={15}/> Procurement pipeline</h3><p>Purchase-order status, expected delivery and outstanding goods value.</p></div><span className="panel-chip">{purchaseOrders.length} purchase orders</span></div>
      <div className="table-scroll"><table><thead><tr><th>PO</th><th>SUPPLIER</th><th>ORDER DATE</th><th>EXPECTED</th><th>STATUS</th><th>OUTSTANDING VALUE</th><th>ACTION</th></tr></thead><tbody>
        {purchaseOrders.map((item) => <tr key={item.id}><td><strong>{item.po_number}</strong></td><td>{item.supplier_name}</td><td>{displayDate(item.order_date)}</td><td>{displayDate(item.expected_date)}</td><td><span className={`status-pill ${statusClass(item.status)}`}>{displayStatus(item.status)}</span></td><td>{formatCurrency(item.outstanding_goods_value,currency,true)}</td><td>{item.status === 'draft' ? <button className="table-action" disabled={saving} onClick={() => void sendPurchaseOrder(item.id)}>Mark sent</button> : '—'}</td></tr>)}
      </tbody></table>{!loading && !purchaseOrders.length && <EmptyState title="No purchase orders" detail="Create a draft purchase order to begin procurement tracking."/>}</div>
    </section>

    <section className="panel table-panel"><div className="panel-header"><div><h3><Route size={15}/> Inbound shipment visibility</h3><p>Supplier origin, destination, carrier, ETA and latest recorded location.</p></div><span className="panel-chip">{shipments.length} shipments</span></div>
      <div className="table-scroll"><table><thead><tr><th>SHIPMENT</th><th>SUPPLIER / ORIGIN</th><th>DESTINATION</th><th>CARRIER / TRACKING</th><th>ETA</th><th>STATUS</th><th>TRANSIT</th><th>RECORDED CHARGES</th><th>ACTION</th></tr></thead><tbody>
        {shipments.map((item) => <tr key={item.id}><td><strong>{item.shipment_number}</strong><span className="table-sub">{item.transport_mode.toUpperCase()} · {item.incoterm || 'Incoterm n/a'}</span></td><td><strong>{item.supplier_name}</strong><span className="table-sub"><MapPin size={11}/>{item.origin_city}{item.origin_state ? `, ${item.origin_state}` : ''}, {item.origin_country}</span></td><td>{item.destination_warehouse}<span className="table-sub">{item.destination_city || ''}</span></td><td>{item.carrier_name || 'Carrier not set'}<span className="table-sub">{item.tracking_number || 'No tracking number'}</span></td><td>{displayDate(item.current_eta_at)}<span className="table-sub">Last: {item.latest_location || 'No event'}</span></td><td><span className={`status-pill ${statusClass(item.status)}`}>{displayStatus(item.status)}</span>{item.delay_days ? <span className="table-sub">{item.delay_days} days late</span> : null}</td><td>{item.transit_days == null ? 'In progress' : `${formatNumber(item.transit_days,1)} days`}</td><td>{formatCurrency(item.charges_total,currency,true)}</td><td><button className="table-action" onClick={() => void loadShipmentTimeline(item.id)}>Timeline</button></td></tr>)}
      </tbody></table>{!loading && !shipments.length && <EmptyState title="No inbound shipments recorded" detail="Create and send a purchase order, then dispatch an inbound shipment."/>}</div>
    </section>

    {viewTimeline && <section className="panel tracking-panel shipment-timeline-panel">
      <div className="panel-header"><div><h3><Route size={15}/> Shipment timeline · {viewTimeline.shipment.shipment_number}</h3><p>{viewTimeline.shipment.origin_city}, {viewTimeline.shipment.origin_country} → {viewTimeline.shipment.destination_warehouse} · {displayStatus(viewTimeline.shipment.status)}</p></div><button className="table-action" onClick={() => setViewTimeline(null)}>Close</button></div>
      {viewTimelineLoading ? <div className="supply-footnote">Loading timeline…</div> : <div className="supply-timeline-grid">
        <div><strong>Recorded milestones</strong>{viewTimeline.events.length ? <ol className="supply-timeline">{viewTimeline.events.map((event, index) => <li key={`${event.event_code}-${event.occurred_at}-${index}`}><span className="supply-timeline-dot"/><div><b>{displayStatus(event.event_code)}</b><small>{displayDate(event.occurred_at)} · {event.location_name || 'Location not recorded'} · {event.source}</small>{event.notes && <small>{event.notes}</small>}</div></li>)}</ol> : <p className="supply-form-note">No milestones recorded yet.</p>}</div>
        <div><strong>Shipment items</strong><div className="table-scroll"><table><thead><tr><th>PRODUCT</th><th>SHIPPED</th><th>RECEIVED</th><th>OUTSTANDING</th></tr></thead><tbody>{viewTimeline.items.map((item) => <tr key={item.shipment_item_id}><td>{item.product_name}<span className="table-sub">{item.sku} · {item.po_number}</span></td><td>{formatNumber(item.quantity_shipped,2)}</td><td>{formatNumber(item.quantity_received,2)}</td><td>{formatNumber(item.quantity_outstanding,2)}</td></tr>)}</tbody></table></div>
          <strong className="supply-timeline-cost-title">Recorded charges</strong>{viewTimeline.costs.length ? viewTimeline.costs.map((cost, index) => <div className="supply-cost-row" key={`${cost.cost_type}-${cost.charge_date}-${index}`}><span>{displayStatus(cost.cost_type)} · {cost.charge_date}</span><b>{formatCurrency(cost.amount,cost.currency)}</b></div>) : <p className="supply-form-note">No shipment charges recorded.</p>}</div>
      </div>}
    </section>}

    <div className="supply-lower-grid">
      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <h3><Building2 size={15}/> Supplier intelligence scorecards</h3>
            <p>Compare delivery reliability, order fulfilment and outstanding procurement exposure.</p>
          </div>
          <span className="panel-chip">{scorecards.length} suppliers</span>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>SUPPLIER</th>
                <th>ORDERS</th>
                <th>ON-TIME</th>
                <th>OTIF</th>
                <th>OVERALL FILL</th>
                <th>COMPLETED FILL</th>
                <th>OUTSTANDING</th>
                <th>PROCUREMENT LEAD</th>
                <th>TRANSIT</th>
                <th>REJECTED</th>
              </tr>
            </thead>
            <tbody>
              {scorecards.map((item) => (
                <tr key={item.supplier_id}>
                  <td>
                    <strong>{item.supplier_name}</strong>
                    <span className="table-sub">{item.supplier_code}</span>
                  </td>
                  <td>
                    <strong>{formatNumber(item.purchase_order_count)}</strong>
                    <span className="table-sub">
                      {formatNumber(item.completed_po_count)} completed · {formatNumber(item.open_po_count ?? 0)} open
                    </span>
                  </td>
                  <td>{item.on_time_po_pct == null ? '—' : `${formatNumber(item.on_time_po_pct, 1)}%`}</td>
                  <td>{item.otif_pct == null ? '—' : `${formatNumber(item.otif_pct, 1)}%`}</td>
                  <td>{item.fill_rate_pct == null ? '—' : `${formatNumber(item.fill_rate_pct, 1)}%`}</td>
                  <td>{item.completed_po_fill_rate_pct == null ? '—' : `${formatNumber(item.completed_po_fill_rate_pct, 1)}%`}</td>
                  <td>
                    <strong>{formatNumber(item.outstanding_quantity ?? 0)}</strong>
                    <span className="table-sub">{formatCurrency(item.open_po_value, currency, true)}</span>
                  </td>
                  <td>{item.avg_procurement_lead_days == null ? '—' : `${formatNumber(item.avg_procurement_lead_days, 1)} days`}</td>
                  <td>{item.avg_transit_days == null ? '—' : `${formatNumber(item.avg_transit_days, 1)} days`}</td>
                  <td>{item.rejected_quantity_pct == null ? '—' : `${formatNumber(item.rejected_quantity_pct, 1)}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && !scorecards.length && (
            <EmptyState
              title="No supplier scorecards available"
              detail="Supplier performance will appear when procurement records are available."
            />
          )}
        </div>
        <p className="supply-footnote">
          Overall fill includes open purchase orders. Completed fill measures received quantities against completed orders only.
          OTIF means on time and in full. Rejection rate is unavailable until goods receipts are recorded.
          Metrics are descriptive and depend on recorded data; small samples are not conclusive.
        </p>
      </section>
      <section className="panel tracking-panel"><div className="panel-header"><div><h3><MapPin size={15}/> Record a tracking update</h3><p>Log a manual carrier or warehouse milestone.</p></div></div>
        <form className="tracking-form" onSubmit={submitTrackingEvent}>
          <label>Shipment<select required value={selectedShipment} onChange={(e) => setSelectedShipment(e.target.value)}><option value="">Select active shipment</option>{activeShipments.map((item) => <option key={item.id} value={item.id}>{item.shipment_number} · {item.supplier_name}</option>)}</select></label>
          <label>Milestone<select value={eventCode} onChange={(e) => setEventCode(e.target.value)}><option value="picked_up">Picked up</option><option value="departed_origin">Departed origin</option><option value="in_transit">In transit</option><option value="arrived_origin_port">Arrived origin port</option><option value="customs_started">Customs started</option><option value="customs_cleared">Customs cleared</option><option value="departed_port">Departed port</option><option value="arrived_destination_port">Arrived destination port</option><option value="out_for_delivery">Out for delivery</option><option value="arrived_warehouse">Arrived at warehouse</option><option value="delayed">Delayed</option><option value="exception">Exception</option><option value="note">Note</option></select></label>
          <label>Current location<input value={locationName} onChange={(e) => setLocationName(e.target.value)} placeholder="e.g. Kurnool transit hub" maxLength={160}/></label>
          <label>Revised ETA (optional)<input type="datetime-local" value={eventEta} onChange={(e) => setEventEta(e.target.value)}/></label>
          <label>Notes<textarea value={eventNotes} onChange={(e) => setEventNotes(e.target.value)} placeholder="Reason, reference or carrier update" rows={3}/></label>
          <button className="primary-button" type="submit" disabled={saving || !selectedShipment}>{saving ? 'Saving…' : <><Plus size={15}/> Record milestone</>}</button>
        </form>
      </section>
    </div>
    <div className="knowledge-footnote"><ShieldCheck size={15}/><span>Development release: organization-scoped demo tenant and manually entered tracking events. No live GPS, carrier webhook, customs or EDI connection is active. Accepted receipts post inventory movements after the latest stock snapshot; rejected quantities remain outside available stock. Shipment charges are recorded separately and are not yet automatically allocated into product landed cost or posted to the general ledger.</span></div>
  </div>;
}


type IpoTargetRoute = 'mainboard' | 'sme_nse';
type IpoChecklistStatus = 'not_started' | 'in_progress' | 'ready' | 'not_applicable';
type IpoChecklistEntry = { status: IpoChecklistStatus; evidence: string };
type IpoChecklistItem = {
  id: string;
  title: string;
  detail: string;
  priority: 'critical' | 'high' | 'medium';
};
type IpoChecklistGroup = { title: string; description: string; items: IpoChecklistItem[] };

const IPO_READINESS_STORAGE_KEY = `profitpulse:ipo-readiness:${DEMO_ORGANIZATION_ID}:v1`;

const IPO_READINESS_GROUPS: IpoChecklistGroup[] = [
  {
    title: 'Financial statements & controls',
    description: 'Build a consistent, reviewable financial record before beginning offer-document due diligence.',
    items: [
      { id: 'audited_fs', title: 'Three years of audited financial statements', detail: 'Collect signed financial statements, audit reports, schedules and comparative figures for the relevant financial years.', priority: 'critical' },
      { id: 'restated_fs', title: 'Restated financial information and audit adjustments', detail: 'Agree the required restatement scope with the lead manager and reporting accountant; document every material adjustment.', priority: 'critical' },
      { id: 'tax_recon', title: 'Tax and statutory dues reconciliations', detail: 'Reconcile income tax, GST, TDS, PF/ESI and other applicable dues; document notices, disputes and payment status.', priority: 'high' },
      { id: 'bank_debt', title: 'Bank, lender and borrowing confirmations', detail: 'Prepare lender confirmations, facility agreements, security details, covenant status and a history of defaults, if any.', priority: 'high' },
      { id: 'internal_controls', title: 'Financial close and internal-control evidence', detail: 'Document monthly close, approval controls, reconciliations, revenue recognition, inventory and access controls.', priority: 'high' },
    ],
  },
  {
    title: 'Ownership, governance & corporate records',
    description: 'Reconcile who owns the company, who controls it and whether corporate records are complete.',
    items: [
      { id: 'cap_table', title: 'Reconciled cap table and securities register', detail: 'Reconcile issued shares, transfers, beneficial ownership, ESOPs, warrants and outstanding convertibles against statutory records.', priority: 'critical' },
      { id: 'promoter_director', title: 'Promoter, director and key-management disclosures', detail: 'Compile identity, experience, interests, directorships, shareholdings, background checks and required declarations.', priority: 'high' },
      { id: 'roc_records', title: 'MCA/ROC filings, statutory registers and minutes', detail: 'Check annual and event-based filings, registers, board/shareholder minutes and corporate approvals for completeness.', priority: 'critical' },
      { id: 'related_party', title: 'Related-party transaction register and approvals', detail: 'Identify related parties, balances, transactions, commercial rationale, approvals and financial-statement disclosures.', priority: 'high' },
      { id: 'governance', title: 'Governance framework mapped to the proposed route', detail: 'Review board composition, committees, policies and governance obligations with company-secretarial and legal advisers.', priority: 'medium' },
    ],
  },
  {
    title: 'Legal, compliance & business disclosures',
    description: 'Create a reliable evidence trail for the company’s business, risks and obligations.',
    items: [
      { id: 'contracts', title: 'Material contracts and change-of-control clauses', detail: 'Index customer, supplier, lease, financing, employment, technology and other material agreements with amendments.', priority: 'high' },
      { id: 'litigation', title: 'Litigation, claims and contingent liabilities', detail: 'Obtain a matter-wise register of claims, notices, investigations, guarantees and contingent liabilities with current status.', priority: 'critical' },
      { id: 'licenses_ip', title: 'Licences, permits, IP and regulatory compliance', detail: 'Confirm operating licences, registrations, intellectual-property ownership, renewals and material compliance obligations.', priority: 'high' },
      { id: 'concentration', title: 'Customer, supplier and revenue concentration analysis', detail: 'Document material customer/supplier dependencies, concentration, revenue policies and key business metrics.', priority: 'medium' },
      { id: 'risk_factors', title: 'Risk factors and proposed use of proceeds', detail: 'Prepare evidence-supported business risks and a traceable rationale and budget for each proposed use of issue proceeds.', priority: 'high' },
    ],
  },
  {
    title: 'IPO execution & due-diligence preparation',
    description: 'Organise the working team and the evidence room. This is preparation tracking, not an application to list.',
    items: [
      { id: 'route_assessment', title: 'Route-specific eligibility assessment reviewed by advisers', detail: 'Have a SEBI-registered lead manager assess the current rules, exchange criteria, promoter conditions and issue structure for the selected route.', priority: 'critical' },
      { id: 'data_room', title: 'Due-diligence data room and document index', detail: 'Create a version-controlled index with document owner, period covered, approval status and evidence reference.', priority: 'high' },
      { id: 'advisers', title: 'Lead manager, legal counsel and audit advisers identified', detail: 'Record adviser selection, scope, independence/conflict checks, engagement status and responsibilities.', priority: 'medium' },
      { id: 'timeline', title: 'Board-approved readiness plan and responsibility calendar', detail: 'Assign owners and target dates for financial restatement, legal diligence, governance remediation and offer-document inputs.', priority: 'medium' },
    ],
  },
];

function readIpoReadinessEntries(): Record<string, IpoChecklistEntry> {
  try {
    const raw = window.localStorage.getItem(IPO_READINESS_STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return parsed as Record<string, IpoChecklistEntry>;
  } catch {
    return {};
  }
}

function readIpoTargetRoute(): IpoTargetRoute {
  try {
    return window.localStorage.getItem(`${IPO_READINESS_STORAGE_KEY}:route`) === 'sme_nse' ? 'sme_nse' : 'mainboard';
  } catch {
    return 'mainboard';
  }
}

function IpoReadinessPage({
  months,
  metrics,
  currency,
}: {
  months: MonthMetric[];
  metrics: FinancialMetrics;
  currency: string;
}) {
  const [entries, setEntries] = useState<Record<string, IpoChecklistEntry>>(() => readIpoReadinessEntries());
  const [targetRoute, setTargetRoute] = useState<IpoTargetRoute>(() => readIpoTargetRoute());

  useEffect(() => {
    try {
      window.localStorage.setItem(IPO_READINESS_STORAGE_KEY, JSON.stringify(entries));
    } catch {
      // The checklist remains usable for this session if browser storage is unavailable.
    }
  }, [entries]);

  useEffect(() => {
    try {
      window.localStorage.setItem(`${IPO_READINESS_STORAGE_KEY}:route`, targetRoute);
    } catch {
      // Route selection remains available for this session if browser storage is unavailable.
    }
  }, [targetRoute]);

  const allItems = IPO_READINESS_GROUPS.flatMap((group) => group.items);
  const applicableItems = allItems.filter((item) => entries[item.id]?.status !== 'not_applicable');
  const readyCount = applicableItems.filter((item) => entries[item.id]?.status === 'ready').length;
  const inProgressCount = applicableItems.filter((item) => entries[item.id]?.status === 'in_progress').length;
  const openCriticalCount = applicableItems.filter((item) => item.priority === 'critical' && entries[item.id]?.status !== 'ready').length;
  const completionPct = applicableItems.length ? Math.round((readyCount / applicableItems.length) * 100) : 0;
  const firstMonth = months[0]?.month;
  const lastMonth = months[months.length - 1]?.month;

  const updateEntry = (id: string, patch: Partial<IpoChecklistEntry>) => {
    setEntries((current) => ({
      ...current,
      [id]: {
        status: current[id]?.status || 'not_started',
        evidence: current[id]?.evidence || '',
        ...patch,
      },
    }));
  };

  return (
    <div className="ipo-readiness-page">
      <div className="page-heading ipo-heading">
        <div>
          <div className="eyebrow">CORPORATE FINANCE · GOVERNANCE · DUE DILIGENCE <span className="eyebrow-line" /></div>
          <h1>Prepare for the public markets.</h1>
          <p>A practical IPO preparation workspace for financial records, corporate governance, legal diligence and transaction planning.</p>
        </div>
        <div className="ipo-route-control">
          <label htmlFor="ipo-target-route">TARGET LISTING ROUTE</label>
          <select id="ipo-target-route" value={targetRoute} onChange={(event) => setTargetRoute(event.target.value as IpoTargetRoute)}>
            <option value="mainboard">Main Board · SEBI ICDR</option>
            <option value="sme_nse">SME · NSE Emerge reference</option>
          </select>
        </div>
      </div>

      <div className="ipo-disclaimer">
        <ShieldCheck size={17} />
        <span><strong>Preparation tracker, not an eligibility certificate.</strong> Completion only reflects checklist items marked Ready by your team. It does not determine IPO eligibility, guarantee listing or replace advice from a SEBI-registered merchant banker, practising CA, CS or legal counsel.</span>
      </div>

      <section className="ipo-overview-panel">
        <div className="ipo-overview-heading">
          <div>
            <div className="eyebrow">IPO PREPARATION STATUS <span className="eyebrow-line" /></div>
            <h2>Readiness work, made visible.</h2>
            <p>Track evidence and ownership across the preparation checklist. Mark an item Ready only after the supporting work has been reviewed.</p>
          </div>
          <span className="ipo-local-badge"><Database size={13}/> Saved in this browser</span>
        </div>
        <div className="ipo-kpi-grid">
          <div className="ipo-kpi-card ipo-kpi-progress">
            <span>Checklist completion</span>
            <strong>{completionPct}%</strong>
            <div className="ipo-progress-track"><span style={{ width: `${completionPct}%` }} /></div>
            <small>{readyCount} of {applicableItems.length} applicable items marked Ready</small>
          </div>
          <div className="ipo-kpi-card">
            <span>Critical gaps</span>
            <strong className={openCriticalCount ? 'ipo-danger-text' : 'ipo-good-text'}>{openCriticalCount}</strong>
            <small>Critical items not yet marked Ready</small>
          </div>
          <div className="ipo-kpi-card">
            <span>In progress</span>
            <strong>{inProgressCount}</strong>
            <small>Items with active preparation work</small>
          </div>
          <div className="ipo-kpi-card">
            <span>Target route</span>
            <strong className="ipo-route-value">{targetRoute === 'sme_nse' ? 'NSE Emerge' : 'Main Board'}</strong>
            <small>Route selection is a planning assumption, not approval</small>
          </div>
        </div>
      </section>

      <div className="ipo-content-grid">
        <section className="ipo-checklist-column">
          {IPO_READINESS_GROUPS.map((group, groupIndex) => (
            <section className="panel ipo-checklist-group" key={group.title}>
              <div className="ipo-group-header">
                <div className="ipo-group-number">0{groupIndex + 1}</div>
                <div>
                  <h3>{group.title}</h3>
                  <p>{group.description}</p>
                </div>
                <span className="panel-chip">{group.items.filter((item) => entries[item.id]?.status === 'ready').length}/{group.items.filter((item) => entries[item.id]?.status !== 'not_applicable').length} ready</span>
              </div>
              <div className="ipo-checklist-items">
                {group.items.map((item) => {
                  const entry = entries[item.id] || { status: 'not_started' as IpoChecklistStatus, evidence: '' };
                  return (
                    <article className={`ipo-checklist-item ipo-item-${entry.status}`} key={item.id}>
                      <div className="ipo-item-main">
                        <div className="ipo-item-copy">
                          <div className="ipo-item-title-row">
                            <strong>{item.title}</strong>
                            <span className={`ipo-priority ipo-priority-${item.priority}`}>{item.priority}</span>
                          </div>
                          <p>{item.detail}</p>
                        </div>
                        <label className="ipo-status-control">
                          <span>STATUS</span>
                          <select
                            value={entry.status}
                            onChange={(event) => updateEntry(item.id, { status: event.target.value as IpoChecklistStatus })}
                            aria-label={`Status for ${item.title}`}
                          >
                            <option value="not_started">Not started</option>
                            <option value="in_progress">In progress</option>
                            <option value="ready">Ready</option>
                            <option value="not_applicable">Not applicable</option>
                          </select>
                        </label>
                      </div>
                      <label className="ipo-evidence-control">
                        <span>Evidence reference / owner / next action</span>
                        <textarea
                          rows={2}
                          value={entry.evidence}
                          onChange={(event) => updateEntry(item.id, { evidence: event.target.value })}
                          placeholder="Example: FY2024–FY2026 audit folder · Owner: Finance · Next: obtain signed report"
                        />
                      </label>
                    </article>
                  );
                })}
              </div>
            </section>
          ))}
        </section>

        <aside className="ipo-side-column">
          <section className="panel ipo-side-panel">
            <div className="panel-header">
              <div><h3><FileText size={15}/> Financial data currently connected</h3><p>Existing ProfitPulse ledger data, not audited IPO restatements.</p></div>
            </div>
            <div className="ipo-financial-window">
              <span>Loaded monthly window</span>
              <strong>{firstMonth && lastMonth ? `${monthLabel(firstMonth)} – ${monthLabel(lastMonth)}` : 'No monthly period loaded'}</strong>
              <small>{months.length} monthly periods available in the current dashboard filter</small>
            </div>
            <div className="ipo-financial-metrics">
              <div><span>Net revenue</span><strong>{formatCurrency(metrics.net_revenue, currency, true)}</strong></div>
              <div><span>Gross profit</span><strong>{formatCurrency(metrics.gross_profit, currency, true)}</strong></div>
              <div><span>EBITDA</span><strong>{formatCurrency(metrics.ebitda, currency, true)}</strong></div>
              <div><span>Profit after tax</span><strong>{formatCurrency(metrics.pat, currency, true)}</strong></div>
            </div>
            <div className="ipo-data-warning"><AlertTriangle size={15}/><span>The current demo contains monthly ledger data for the selected window. It does not demonstrate three full years of audited/restated financial statements or confirm IPO financial eligibility.</span></div>
          </section>

          <section className="panel ipo-side-panel ipo-route-guidance">
            <div className="panel-header">
              <div><h3><Building2 size={15}/> Route-specific reference</h3><p>Use the current official rules for the selected market.</p></div>
            </div>
            {targetRoute === 'sme_nse' ? (
              <>
                <span className="ipo-reference-tag">NSE Emerge reference</span>
                <ul className="ipo-route-list">
                  <li>Issuer should be an Indian company under the Companies Act.</li>
                  <li>Post-issue paid-up capital should not exceed ₹25 crore.</li>
                  <li>Track record of at least three years under the eligible applicant/promoter/group route described by NSE.</li>
                  <li>Operating profit of at least ₹1 crore from operations in any two of the previous three financial years.</li>
                  <li>Positive net worth and positive FCFE in at least two of the previous three financial years.</li>
                  <li>Other conditions and disqualifiers, including insolvency, winding-up and regulatory matters, require separate review.</li>
                </ul>
                <a className="ipo-source-link" href="https://www.nseindia.com/static/companies-listing/raising-capital-public-issues-emerge-eligibility-criteria" target="_blank" rel="noreferrer">Open NSE Emerge eligibility criteria <ArrowRight size={13}/></a>
              </>
            ) : (
              <>
                <span className="ipo-reference-tag">SEBI ICDR reference</span>
                <p className="ipo-guidance-copy">Main Board eligibility and offer conditions must be assessed against the current SEBI Issue of Capital and Disclosure Requirements Regulations, including route-specific financial tests, promoter contribution and lock-in, public shareholding, offer structure and disclosures.</p>
                <a className="ipo-source-link" href="https://www.sebi.gov.in/legal/regulations/mar-2026/securities-and-exchange-board-of-india-issue-of-capital-and-disclosure-requirements-regulations-2018-last-amended-on-march-21-2026-_100581.html" target="_blank" rel="noreferrer">Open SEBI ICDR Regulations (amended 21 Mar 2026) <ArrowRight size={13}/></a>
              </>
            )}
            <p className="ipo-route-caveat">The reference summary is not exhaustive. Listing rules, exchange circulars and interpretations can change. Have the lead manager and legal advisers confirm the current criteria before relying on them.</p>
          </section>

          <section className="panel ipo-side-panel">
            <div className="panel-header"><div><h3><ShieldCheck size={15}/> How to use this workspace</h3><p>Keep the tracker evidence-led.</p></div></div>
            <ol className="ipo-howto-list">
              <li>Choose the intended listing route.</li>
              <li>Assign each checklist item to an owner.</li>
              <li>Record an evidence reference or next action.</li>
              <li>Mark Ready only after internal/adviser review.</li>
            </ol>
            <div className="ipo-storage-note"><Database size={14}/><span>Checklist status and notes are saved in this browser for this demo organization only. They are not yet synced to PostgreSQL or shared with other users.</span></div>
          </section>
        </aside>
      </div>

      <div className="knowledge-footnote ipo-footnote">
        <ShieldCheck size={15}/>
        <span>IPO preparation support only. This workspace does not provide legal, audit, investment-banking or eligibility opinions, does not file documents with SEBI or an exchange, and does not guarantee listing. Confirm all requirements with qualified professionals and current official rules.</span>
      </div>
    </div>
  );
}

export default App;
