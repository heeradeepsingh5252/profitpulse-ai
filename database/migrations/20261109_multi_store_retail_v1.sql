-- Multi-store retail intelligence v1
CREATE TABLE IF NOT EXISTS retail_stores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  store_code text NOT NULL,
  store_name text NOT NULL,
  city text NOT NULL,
  monthly_revenue_threshold numeric(18,2) NOT NULL DEFAULT 0 CHECK (monthly_revenue_threshold >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, store_code),
  UNIQUE (organization_id, id)
);
CREATE TABLE IF NOT EXISTS retail_import_batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  store_id uuid NOT NULL,
  import_type text NOT NULL CHECK (import_type IN ('sales','inventory')),
  file_name text NOT NULL,
  row_count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, store_id) REFERENCES retail_stores(organization_id, id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS retail_sales (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  store_id uuid NOT NULL,
  import_batch_id uuid NOT NULL,
  row_number integer NOT NULL,
  sale_date date NOT NULL,
  sku text NOT NULL,
  product_name text NOT NULL,
  category text,
  quantity numeric(14,3) NOT NULL CHECK (quantity >= 0),
  unit_price numeric(18,2) NOT NULL CHECK (unit_price >= 0),
  unit_cost numeric(18,2) NOT NULL CHECK (unit_cost >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, import_batch_id, row_number),
  FOREIGN KEY (organization_id, store_id) REFERENCES retail_stores(organization_id, id) ON DELETE CASCADE,
  FOREIGN KEY (organization_id, import_batch_id) REFERENCES retail_import_batches(organization_id, id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS retail_inventory_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  store_id uuid NOT NULL,
  snapshot_date date NOT NULL,
  sku text NOT NULL,
  product_name text NOT NULL,
  category text,
  stock_on_hand numeric(14,3) NOT NULL CHECK (stock_on_hand >= 0),
  reorder_level numeric(14,3) NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
  unit_cost numeric(18,2) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, store_id, snapshot_date, sku),
  FOREIGN KEY (organization_id, store_id) REFERENCES retail_stores(organization_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_retail_sales_org_store_date ON retail_sales(organization_id, store_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_retail_inventory_org_store_date ON retail_inventory_snapshots(organization_id, store_id, snapshot_date DESC);
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['retail_stores','retail_import_batches','retail_sales','retail_inventory_snapshots']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
    EXECUTE format('CREATE POLICY tenant_isolation ON %I USING (organization_id = app.current_org_id()) WITH CHECK (organization_id = app.current_org_id())', t);
  END LOOP;
END $$;
