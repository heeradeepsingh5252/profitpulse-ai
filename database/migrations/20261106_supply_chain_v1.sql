-- ProfitPulse AI Supply Chain Intelligence v1
-- Additive migration. Safe to apply to an existing Day 1-5 database.
-- Run as the PostgreSQL admin role; do not drop or recreate existing volumes.

BEGIN;

-- Supplier origins can differ by factory/site, so retain the existing supplier
-- master and add one-or-many origin sites instead of overwriting supplier city.
CREATE TABLE IF NOT EXISTS sc_supplier_sites (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  supplier_id uuid NOT NULL,
  site_code text NOT NULL,
  site_name text NOT NULL,
  site_type text NOT NULL DEFAULT 'factory' CHECK (site_type IN ('factory','warehouse','distribution_center','port','other')),
  origin_city text NOT NULL,
  origin_state text,
  origin_country text NOT NULL,
  origin_country_code char(2),
  origin_postal_code text,
  origin_port text,
  default_lead_time_days integer CHECK (default_lead_time_days IS NULL OR default_lead_time_days >= 0),
  preferred_transport_mode text CHECK (preferred_transport_mode IS NULL OR preferred_transport_mode IN ('road','rail','air','sea','courier','multimodal')),
  is_primary boolean NOT NULL DEFAULT false,
  is_active boolean NOT NULL DEFAULT true,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,id),
  UNIQUE (organization_id,supplier_id,site_code),
  FOREIGN KEY (organization_id,supplier_id) REFERENCES suppliers(organization_id,id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sc_supplier_primary_site
  ON sc_supplier_sites(organization_id,supplier_id) WHERE is_primary;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_purchase_order_items_org_po_item') THEN
    ALTER TABLE purchase_order_items ADD CONSTRAINT uq_purchase_order_items_org_po_item
      UNIQUE (organization_id,purchase_order_id,id);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS sc_inbound_shipments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  shipment_number text NOT NULL,
  supplier_id uuid NOT NULL,
  supplier_site_id uuid,
  destination_warehouse_id uuid NOT NULL,
  origin_city text NOT NULL,
  origin_state text,
  origin_country text NOT NULL,
  origin_country_code char(2),
  origin_port text,
  destination_port text,
  carrier_name text,
  carrier_service text,
  tracking_number text,
  transport_mode text NOT NULL CHECK (transport_mode IN ('road','rail','air','sea','courier','multimodal')),
  incoterm text CHECK (incoterm IS NULL OR incoterm IN ('EXW','FCA','CPT','CIP','DAP','DPU','DDP','FAS','FOB','CFR','CIF')),
  status text NOT NULL DEFAULT 'booked' CHECK (status IN ('planned','booked','picked_up','in_transit','at_origin_port','in_customs','at_destination_port','out_for_delivery','arrived_at_warehouse','delayed','exception','delivered','cancelled')),
  planned_departure_at timestamptz,
  actual_departure_at timestamptz,
  promised_arrival_at timestamptz,
  current_eta_at timestamptz,
  actual_arrival_at timestamptz,
  currency char(3) NOT NULL DEFAULT 'INR',
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,id),
  UNIQUE (organization_id,shipment_number),
  FOREIGN KEY (organization_id,supplier_id) REFERENCES suppliers(organization_id,id),
  FOREIGN KEY (organization_id,supplier_site_id) REFERENCES sc_supplier_sites(organization_id,id),
  FOREIGN KEY (organization_id,destination_warehouse_id) REFERENCES warehouses(organization_id,id),
  CHECK (current_eta_at IS NULL OR actual_departure_at IS NULL OR current_eta_at >= actual_departure_at),
  CHECK (promised_arrival_at IS NULL OR planned_departure_at IS NULL OR promised_arrival_at >= planned_departure_at),
  CHECK (actual_arrival_at IS NULL OR actual_departure_at IS NULL OR actual_arrival_at >= actual_departure_at)
);

CREATE TABLE IF NOT EXISTS sc_shipment_purchase_orders (
  organization_id uuid NOT NULL,
  shipment_id uuid NOT NULL,
  purchase_order_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id,shipment_id,purchase_order_id),
  FOREIGN KEY (organization_id,shipment_id) REFERENCES sc_inbound_shipments(organization_id,id) ON DELETE CASCADE,
  FOREIGN KEY (organization_id,purchase_order_id) REFERENCES purchase_orders(organization_id,id)
);

CREATE TABLE IF NOT EXISTS sc_shipment_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  shipment_id uuid NOT NULL,
  purchase_order_id uuid NOT NULL,
  purchase_order_item_id uuid NOT NULL,
  quantity_shipped numeric(18,3) NOT NULL CHECK (quantity_shipped > 0),
  quantity_received numeric(18,3) NOT NULL DEFAULT 0 CHECK (quantity_received >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,id),
  UNIQUE (organization_id,shipment_id,purchase_order_item_id),
  FOREIGN KEY (organization_id,shipment_id,purchase_order_id)
    REFERENCES sc_shipment_purchase_orders(organization_id,shipment_id,purchase_order_id) ON DELETE CASCADE,
  FOREIGN KEY (organization_id,purchase_order_id,purchase_order_item_id)
    REFERENCES purchase_order_items(organization_id,purchase_order_id,id),
  CHECK (quantity_received <= quantity_shipped)
);

CREATE TABLE IF NOT EXISTS sc_shipment_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  shipment_id uuid NOT NULL,
  event_code text NOT NULL CHECK (event_code IN ('booked','picked_up','departed_origin','in_transit','arrived_origin_port','customs_started','customs_cleared','departed_port','arrived_destination_port','out_for_delivery','arrived_warehouse','delayed','exception','goods_received','note')),
  status_after text CHECK (status_after IS NULL OR status_after IN ('planned','booked','picked_up','in_transit','at_origin_port','in_customs','at_destination_port','out_for_delivery','arrived_at_warehouse','delayed','exception','delivered','cancelled')),
  location_name text,
  city text,
  state text,
  country text,
  occurred_at timestamptz NOT NULL,
  notes text,
  source text NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','carrier_api','edi','csv','system')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,id),
  UNIQUE (organization_id,shipment_id,event_code,occurred_at),
  FOREIGN KEY (organization_id,shipment_id) REFERENCES sc_inbound_shipments(organization_id,id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sc_shipment_costs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  shipment_id uuid NOT NULL,
  cost_type text NOT NULL CHECK (cost_type IN ('freight','insurance','customs_duty','customs_brokerage','port_handling','inland_transport','other')),
  description text,
  amount numeric(18,2) NOT NULL CHECK (amount >= 0),
  currency char(3) NOT NULL,
  charge_date date NOT NULL,
  reference text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,id),
  FOREIGN KEY (organization_id,shipment_id) REFERENCES sc_inbound_shipments(organization_id,id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sc_goods_receipts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  shipment_id uuid NOT NULL,
  warehouse_id uuid NOT NULL,
  receipt_number text NOT NULL,
  received_at timestamptz NOT NULL,
  inspection_status text NOT NULL DEFAULT 'pending' CHECK (inspection_status IN ('pending','passed','partial','failed')),
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,id),
  UNIQUE (organization_id,receipt_number),
  FOREIGN KEY (organization_id,shipment_id) REFERENCES sc_inbound_shipments(organization_id,id),
  FOREIGN KEY (organization_id,warehouse_id) REFERENCES warehouses(organization_id,id)
);

CREATE TABLE IF NOT EXISTS sc_goods_receipt_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  goods_receipt_id uuid NOT NULL,
  shipment_item_id uuid NOT NULL,
  quantity_received numeric(18,3) NOT NULL CHECK (quantity_received > 0),
  quantity_accepted numeric(18,3) NOT NULL CHECK (quantity_accepted >= 0),
  quantity_rejected numeric(18,3) NOT NULL CHECK (quantity_rejected >= 0),
  inspection_notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id,id),
  FOREIGN KEY (organization_id,goods_receipt_id) REFERENCES sc_goods_receipts(organization_id,id) ON DELETE CASCADE,
  FOREIGN KEY (organization_id,shipment_item_id) REFERENCES sc_shipment_items(organization_id,id),
  CHECK (quantity_accepted + quantity_rejected = quantity_received)
);

CREATE INDEX IF NOT EXISTS idx_sc_sites_org_supplier ON sc_supplier_sites(organization_id,supplier_id,is_active);
CREATE INDEX IF NOT EXISTS idx_sc_shipments_org_status_eta ON sc_inbound_shipments(organization_id,status,current_eta_at);
CREATE INDEX IF NOT EXISTS idx_sc_shipments_org_supplier ON sc_inbound_shipments(organization_id,supplier_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sc_events_org_shipment_time ON sc_shipment_events(organization_id,shipment_id,occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_sc_costs_org_shipment ON sc_shipment_costs(organization_id,shipment_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sc_shipment_cost_reference
  ON sc_shipment_costs(organization_id,shipment_id,reference) WHERE reference IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sc_receipts_org_shipment ON sc_goods_receipts(organization_id,shipment_id,received_at DESC);

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'sc_supplier_sites','sc_inbound_shipments','sc_shipment_purchase_orders','sc_shipment_items',
    'sc_shipment_events','sc_shipment_costs','sc_goods_receipts','sc_goods_receipt_items'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I',t);
    EXECUTE format('CREATE POLICY tenant_isolation ON %I USING (organization_id = app.current_org_id()) WITH CHECK (organization_id = app.current_org_id())',t);
  END LOOP;
END $$;

GRANT SELECT,INSERT,UPDATE ON sc_supplier_sites,sc_inbound_shipments,sc_shipment_purchase_orders,
  sc_shipment_items,sc_shipment_events,sc_shipment_costs,sc_goods_receipts,sc_goods_receipt_items
  TO profitpulse_app;
GRANT INSERT,UPDATE ON purchase_orders,purchase_order_items TO profitpulse_app;
GRANT INSERT ON inventory_movements,audit_events TO profitpulse_app;

COMMIT;
