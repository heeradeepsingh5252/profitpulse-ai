CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.current_org_id()
RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.current_organization_id', true), '')::uuid;
$$;

CREATE TABLE organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  legal_name text NOT NULL,
  display_name text NOT NULL,
  industry text NOT NULL CHECK (industry IN ('retail','wholesale_distribution','retail_and_distribution','other')),
  base_currency char(3) NOT NULL DEFAULT 'INR',
  fiscal_year_start_month smallint NOT NULL DEFAULT 4 CHECK (fiscal_year_start_month BETWEEN 1 AND 12),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE,
  full_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE organization_members (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner','admin','analyst','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id,user_id)
);

CREATE TABLE data_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  source_name text NOT NULL,
  source_type text NOT NULL CHECK (source_type IN ('csv','xlsx','postgresql','api','manual')),
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,id)
);
CREATE TABLE import_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  source_id uuid,
  entity_type text NOT NULL CHECK (entity_type IN ('customers','products')),
  file_name text NOT NULL,
  status text NOT NULL DEFAULT 'processing' CHECK (status IN ('processing','completed','completed_with_errors','failed')),
  total_rows integer NOT NULL DEFAULT 0 CHECK (total_rows >= 0),
  accepted_rows integer NOT NULL DEFAULT 0 CHECK (accepted_rows >= 0),
  rejected_rows integer NOT NULL DEFAULT 0 CHECK (rejected_rows >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  UNIQUE (organization_id,id),
  FOREIGN KEY (organization_id,source_id) REFERENCES data_sources(organization_id,id)
);
CREATE TABLE import_row_errors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  import_job_id uuid NOT NULL,
  row_number integer NOT NULL CHECK (row_number >= 0),
  error_message text NOT NULL,
  raw_row jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (organization_id,import_job_id) REFERENCES import_jobs(organization_id,id) ON DELETE CASCADE
);

CREATE TABLE customers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  customer_code text NOT NULL,
  name text NOT NULL,
  email text,
  phone text,
  city text,
  state text,
  region text,
  customer_type text NOT NULL DEFAULT 'retail' CHECK (customer_type IN ('retail','wholesale','b2b','other')),
  credit_limit numeric(18,2) NOT NULL DEFAULT 0 CHECK (credit_limit >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,customer_code),
  UNIQUE (organization_id,email),
  UNIQUE (organization_id,id)
);
CREATE TABLE suppliers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  supplier_code text NOT NULL,
  name text NOT NULL,
  email text,
  phone text,
  city text,
  state text,
  payment_terms_days integer NOT NULL DEFAULT 30 CHECK (payment_terms_days >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,supplier_code),
  UNIQUE (organization_id,id)
);
CREATE TABLE products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  sku text NOT NULL,
  name text NOT NULL,
  category text NOT NULL,
  unit_of_measure text NOT NULL DEFAULT 'unit',
  unit_price numeric(18,2) NOT NULL CHECK (unit_price >= 0),
  unit_cost numeric(18,2) NOT NULL CHECK (unit_cost >= 0),
  reorder_level integer NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,sku),
  UNIQUE (organization_id,id)
);
CREATE TABLE warehouses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  warehouse_code text NOT NULL,
  name text NOT NULL,
  city text,
  state text,
  UNIQUE (organization_id,warehouse_code),
  UNIQUE (organization_id,id)
);

CREATE TABLE orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  customer_id uuid,
  order_number text NOT NULL,
  order_date date NOT NULL,
  order_type text NOT NULL CHECK (order_type IN ('retail','wholesale','b2b')),
  status text NOT NULL CHECK (status IN ('draft','confirmed','processing','shipped','delivered','cancelled','returned')),
  sales_channel text NOT NULL DEFAULT 'direct',
  sales_region text,
  subtotal numeric(18,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
  discount_amount numeric(18,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  tax_amount numeric(18,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
  shipping_amount numeric(18,2) NOT NULL DEFAULT 0 CHECK (shipping_amount >= 0),
  total_amount numeric(18,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
  currency char(3) NOT NULL DEFAULT 'INR',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,order_number),
  UNIQUE (organization_id,id),
  FOREIGN KEY (organization_id,customer_id) REFERENCES customers(organization_id,id)
);
CREATE TABLE order_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  order_id uuid NOT NULL,
  product_id uuid NOT NULL,
  quantity numeric(18,3) NOT NULL CHECK (quantity > 0),
  unit_price numeric(18,2) NOT NULL CHECK (unit_price >= 0),
  unit_cost_snapshot numeric(18,2) NOT NULL CHECK (unit_cost_snapshot >= 0),
  discount_amount numeric(18,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  line_total numeric(18,2) NOT NULL CHECK (line_total >= 0),
  FOREIGN KEY (organization_id,order_id) REFERENCES orders(organization_id,id) ON DELETE CASCADE,
  FOREIGN KEY (organization_id,product_id) REFERENCES products(organization_id,id)
);
CREATE TABLE purchase_orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  supplier_id uuid NOT NULL,
  po_number text NOT NULL,
  order_date date NOT NULL,
  expected_date date,
  received_date date,
  status text NOT NULL CHECK (status IN ('draft','sent','partially_received','received','cancelled')),
  total_amount numeric(18,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
  UNIQUE (organization_id,po_number),
  UNIQUE (organization_id,id),
  FOREIGN KEY (organization_id,supplier_id) REFERENCES suppliers(organization_id,id)
);
CREATE TABLE purchase_order_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  purchase_order_id uuid NOT NULL,
  product_id uuid NOT NULL,
  quantity_ordered numeric(18,3) NOT NULL CHECK (quantity_ordered > 0),
  quantity_received numeric(18,3) NOT NULL DEFAULT 0 CHECK (quantity_received >= 0),
  unit_cost numeric(18,2) NOT NULL CHECK (unit_cost >= 0),
  line_total numeric(18,2) NOT NULL CHECK (line_total >= 0),
  FOREIGN KEY (organization_id,purchase_order_id) REFERENCES purchase_orders(organization_id,id) ON DELETE CASCADE,
  FOREIGN KEY (organization_id,product_id) REFERENCES products(organization_id,id)
);
CREATE TABLE payments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  order_id uuid,
  purchase_order_id uuid,
  payment_direction text NOT NULL CHECK (payment_direction IN ('inbound','outbound')),
  payment_date date NOT NULL,
  amount numeric(18,2) NOT NULL CHECK (amount > 0),
  payment_method text NOT NULL DEFAULT 'bank_transfer',
  status text NOT NULL DEFAULT 'completed' CHECK (status IN ('pending','completed','failed','reversed')),
  reference text,
  CHECK (NOT (order_id IS NOT NULL AND purchase_order_id IS NOT NULL)),
  FOREIGN KEY (organization_id,order_id) REFERENCES orders(organization_id,id),
  FOREIGN KEY (organization_id,purchase_order_id) REFERENCES purchase_orders(organization_id,id)
);
CREATE TABLE inventory_movements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  product_id uuid NOT NULL,
  warehouse_id uuid NOT NULL,
  movement_date date NOT NULL,
  movement_type text NOT NULL CHECK (movement_type IN ('purchase','sale','return','adjustment','transfer_in','transfer_out')),
  quantity_delta numeric(18,3) NOT NULL CHECK (quantity_delta <> 0),
  unit_cost numeric(18,2) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
  reference text,
  FOREIGN KEY (organization_id,product_id) REFERENCES products(organization_id,id),
  FOREIGN KEY (organization_id,warehouse_id) REFERENCES warehouses(organization_id,id)
);
CREATE TABLE inventory_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  product_id uuid NOT NULL,
  warehouse_id uuid NOT NULL,
  snapshot_date date NOT NULL,
  quantity_on_hand numeric(18,3) NOT NULL,
  unit_cost numeric(18,2) NOT NULL DEFAULT 0,
  UNIQUE (organization_id,product_id,warehouse_id,snapshot_date),
  FOREIGN KEY (organization_id,product_id) REFERENCES products(organization_id,id),
  FOREIGN KEY (organization_id,warehouse_id) REFERENCES warehouses(organization_id,id)
);
CREATE TABLE expenses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  expense_date date NOT NULL,
  category text NOT NULL,
  vendor_name text,
  description text,
  amount numeric(18,2) NOT NULL CHECK (amount > 0),
  payment_status text NOT NULL DEFAULT 'paid' CHECK (payment_status IN ('paid','unpaid','partially_paid')),
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Chart of accounts and double-entry general ledger.
CREATE TABLE gl_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  account_code text NOT NULL,
  account_name text NOT NULL,
  account_type text NOT NULL CHECK (account_type IN ('asset','liability','equity','revenue','contra_revenue','expense','contra_asset')),
  financial_category text NOT NULL CHECK (financial_category IN ('cash','receivable','inventory','other_asset','fixed_asset','accumulated_depreciation','payable','debt','tax_payable','equity','revenue','contra_revenue','cogs','operating_expense','depreciation','amortization','interest_expense','income_tax')),
  financial_statement text NOT NULL CHECK (financial_statement IN ('balance_sheet','income_statement')),
  normal_balance text NOT NULL CHECK (normal_balance IN ('debit','credit')),
  is_active boolean NOT NULL DEFAULT true,
  UNIQUE (organization_id,account_code),
  UNIQUE (organization_id,id)
);
CREATE TABLE journal_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  entry_date date NOT NULL,
  description text NOT NULL,
  reference text,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','posted','void')),
  created_at timestamptz NOT NULL DEFAULT now(),
  posted_at timestamptz,
  UNIQUE (organization_id,id)
);
CREATE TABLE journal_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  journal_entry_id uuid NOT NULL,
  account_id uuid NOT NULL,
  debit numeric(18,2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
  credit numeric(18,2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
  memo text,
  CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)),
  FOREIGN KEY (organization_id,journal_entry_id) REFERENCES journal_entries(organization_id,id) ON DELETE CASCADE,
  FOREIGN KEY (organization_id,account_id) REFERENCES gl_accounts(organization_id,id)
);
CREATE TABLE fixed_assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  asset_code text NOT NULL,
  asset_name text NOT NULL,
  acquisition_date date NOT NULL,
  acquisition_cost numeric(18,2) NOT NULL CHECK (acquisition_cost >= 0),
  useful_life_months integer NOT NULL CHECK (useful_life_months > 0),
  residual_value numeric(18,2) NOT NULL DEFAULT 0 CHECK (residual_value >= 0),
  UNIQUE (organization_id,asset_code)
);
CREATE TABLE loan_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  lender_name text NOT NULL,
  loan_reference text NOT NULL,
  principal_amount numeric(18,2) NOT NULL CHECK (principal_amount >= 0),
  annual_interest_rate numeric(8,4) NOT NULL CHECK (annual_interest_rate >= 0),
  start_date date NOT NULL,
  maturity_date date,
  outstanding_principal numeric(18,2) NOT NULL CHECK (outstanding_principal >= 0),
  UNIQUE (organization_id,loan_reference)
);
CREATE TABLE budgets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  period_start date NOT NULL,
  period_end date NOT NULL,
  metric_code text NOT NULL,
  budget_amount numeric(18,2) NOT NULL,
  UNIQUE (organization_id,period_start,period_end,metric_code),
  CHECK (period_end >= period_start)
);
CREATE TABLE business_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  document_name text NOT NULL,
  document_type text NOT NULL,
  storage_key text,
  content_hash text,
  processing_status text NOT NULL DEFAULT 'pending' CHECK (processing_status IN ('pending','processed','failed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,id)
);
CREATE TABLE audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  actor_user_id uuid,
  event_type text NOT NULL,
  resource_type text,
  resource_id text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_customers_org_name ON customers(organization_id,name);
CREATE INDEX idx_products_org_category ON products(organization_id,category);
CREATE INDEX idx_orders_org_date ON orders(organization_id,order_date);
CREATE INDEX idx_orders_org_customer ON orders(organization_id,customer_id);
CREATE INDEX idx_order_items_org_order ON order_items(organization_id,order_id);
CREATE INDEX idx_payments_org_date ON payments(organization_id,payment_date);
CREATE INDEX idx_journal_entries_org_date_status ON journal_entries(organization_id,entry_date,status);
CREATE INDEX idx_journal_lines_org_account ON journal_lines(organization_id,account_id);
CREATE INDEX idx_inventory_snapshots_org_date ON inventory_snapshots(organization_id,snapshot_date);

CREATE OR REPLACE FUNCTION create_balanced_journal_entry(
  p_organization_id uuid, p_entry_date date, p_description text, p_reference text, p_lines jsonb
) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE v_entry_id uuid; v_debits numeric(18,2); v_credits numeric(18,2); v_line_count integer; v_inserted_count integer;
BEGIN
  IF jsonb_typeof(p_lines) <> 'array' OR jsonb_array_length(p_lines) < 2 THEN
    RAISE EXCEPTION 'A journal entry requires at least two lines';
  END IF;
  INSERT INTO journal_entries(organization_id,entry_date,description,reference,status)
  VALUES(p_organization_id,p_entry_date,p_description,p_reference,'draft') RETURNING id INTO v_entry_id;
  SELECT count(*) INTO v_line_count FROM jsonb_array_elements(p_lines);
  INSERT INTO journal_lines(organization_id,journal_entry_id,account_id,debit,credit,memo)
  SELECT p_organization_id,v_entry_id,a.id,COALESCE(x.debit,0),COALESCE(x.credit,0),x.memo
  FROM jsonb_to_recordset(p_lines) AS x(account_code text,debit numeric,credit numeric,memo text)
  JOIN gl_accounts a ON a.organization_id=p_organization_id AND a.account_code=x.account_code;
  GET DIAGNOSTICS v_inserted_count = ROW_COUNT;
  IF v_inserted_count <> v_line_count THEN RAISE EXCEPTION 'One or more account codes were not found'; END IF;
  SELECT COALESCE(sum(debit),0),COALESCE(sum(credit),0) INTO v_debits,v_credits
  FROM journal_lines WHERE organization_id=p_organization_id AND journal_entry_id=v_entry_id;
  IF round(v_debits,2) <> round(v_credits,2) THEN
    RAISE EXCEPTION 'Unbalanced journal entry: debits %, credits %',v_debits,v_credits;
  END IF;
  UPDATE journal_entries SET status='posted',posted_at=now()
  WHERE organization_id=p_organization_id AND id=v_entry_id;
  RETURN v_entry_id;
END;
$$;

CREATE OR REPLACE FUNCTION app.prevent_posted_journal_line_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_status text; v_org uuid; v_entry uuid;
BEGIN
  IF TG_OP='DELETE' THEN v_org:=OLD.organization_id; v_entry:=OLD.journal_entry_id;
  ELSE v_org:=NEW.organization_id; v_entry:=NEW.journal_entry_id; END IF;
  SELECT status INTO v_status FROM journal_entries WHERE organization_id=v_org AND id=v_entry;
  IF v_status='posted' THEN RAISE EXCEPTION 'Posted journal lines are immutable'; END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END;
$$;
CREATE TRIGGER trg_posted_journal_line_immutable
BEFORE INSERT OR UPDATE OR DELETE ON journal_lines
FOR EACH ROW EXECUTE FUNCTION app.prevent_posted_journal_line_mutation();

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'organizations','organization_members','data_sources','import_jobs','import_row_errors','customers','suppliers','products',
    'warehouses','orders','order_items','purchase_orders','purchase_order_items','payments','inventory_movements',
    'inventory_snapshots','expenses','gl_accounts','journal_entries','journal_lines','fixed_assets','loan_accounts',
    'budgets','business_documents','audit_events'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
    IF t='organizations' THEN
      EXECUTE 'CREATE POLICY tenant_isolation ON organizations USING (id = app.current_org_id()) WITH CHECK (id = app.current_org_id())';
    ELSE
      EXECUTE format('CREATE POLICY tenant_isolation ON %I USING (organization_id = app.current_org_id()) WITH CHECK (organization_id = app.current_org_id())',t);
    END IF;
  END LOOP;
END $$;

GRANT USAGE ON SCHEMA public,app TO profitpulse_app;
GRANT EXECUTE ON FUNCTION app.current_org_id() TO profitpulse_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO profitpulse_app;
GRANT INSERT,UPDATE ON customers,products TO profitpulse_app;
GRANT INSERT,SELECT,UPDATE ON import_jobs TO profitpulse_app;
GRANT INSERT,SELECT ON import_row_errors TO profitpulse_app;
REVOKE INSERT,UPDATE,DELETE ON journal_entries,journal_lines,gl_accounts FROM profitpulse_app;
REVOKE ALL ON FUNCTION create_balanced_journal_entry(uuid,date,text,text,jsonb) FROM PUBLIC;
