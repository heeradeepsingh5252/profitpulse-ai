-- Optional synthetic Supply Chain demo data (corrected chronology + safe reruns).
-- Run after 20261106_supply_chain_v1.sql. Uses the seeded demo organization only.
-- All suppliers, shipments, carriers and tracking events below are fictional demo records.
-- This script is designed to be rerunnable: inserts use conflict protection, and the
-- historical synthetic booking event is corrected in place before missing events are added.

BEGIN;
DO $$
DECLARE
  v_org uuid := '11111111-1111-4111-8111-111111111111';
  v_supplier_row record;
  v_supplier_id uuid;
  v_po_id uuid;
  v_product_id uuid;
  v_shipment_id uuid;
  v_site_id uuid;
  v_wh_id uuid;
BEGIN
  -- Create primary origin sites for existing synthetic suppliers.
  FOR v_supplier_row IN
    SELECT id,supplier_code,name,city,state
    FROM suppliers WHERE organization_id=v_org
  LOOP
    INSERT INTO sc_supplier_sites(
      organization_id,supplier_id,site_code,site_name,site_type,origin_city,origin_state,
      origin_country,origin_country_code,default_lead_time_days,preferred_transport_mode,is_primary
    ) VALUES (
      v_org,v_supplier_row.id,'PRIMARY','Primary origin - '||v_supplier_row.name,
      'factory',COALESCE(v_supplier_row.city,'Unknown'),v_supplier_row.state,
      'India','IN',CASE v_supplier_row.supplier_code
        WHEN 'SUP-001' THEN 4 WHEN 'SUP-002' THEN 6 WHEN 'SUP-003' THEN 5
        WHEN 'SUP-004' THEN 7 ELSE 6 END,'road',true
    ) ON CONFLICT (organization_id,supplier_id,site_code) DO NOTHING;
  END LOOP;

  SELECT id INTO v_wh_id FROM warehouses WHERE organization_id=v_org AND warehouse_code='WH-HYD';

  -- Create shipment records for existing received POs; idempotent by shipment number.
  INSERT INTO sc_inbound_shipments(
    organization_id,shipment_number,supplier_id,supplier_site_id,destination_warehouse_id,
    origin_city,origin_state,origin_country,origin_country_code,carrier_name,tracking_number,
    transport_mode,status,planned_departure_at,actual_departure_at,promised_arrival_at,
    current_eta_at,actual_arrival_at,currency,notes
  )
  SELECT v_org,'SHP-'||po.po_number,po.supplier_id,site.id,v_wh_id,
         site.origin_city,site.origin_state,site.origin_country,site.origin_country_code,
         'Demo Regional Transport','DEMO-'||po.po_number,'road','delivered',
         (po.order_date + 1)::timestamp + time '09:00',
         (po.order_date + 1)::timestamp + time '10:00',
         po.expected_date::timestamp + time '18:00',
         po.expected_date::timestamp + time '18:00',
         COALESCE(po.received_date,po.expected_date)::timestamp + time '16:00',
         COALESCE(orgs.base_currency,'INR'),
         'Synthetic historical shipment generated for the local Supply Chain demonstration.'
  FROM purchase_orders po
  JOIN suppliers s ON s.organization_id=po.organization_id AND s.id=po.supplier_id
  JOIN sc_supplier_sites site ON site.organization_id=s.organization_id AND site.supplier_id=s.id AND site.is_primary
  JOIN organizations orgs ON orgs.id=v_org
  WHERE po.organization_id=v_org AND po.status='received'
  ON CONFLICT (organization_id,shipment_number) DO NOTHING;

  INSERT INTO sc_shipment_purchase_orders(organization_id,shipment_id,purchase_order_id)
  SELECT v_org,sh.id,po.id
  FROM purchase_orders po
  JOIN sc_inbound_shipments sh ON sh.organization_id=v_org AND sh.shipment_number='SHP-'||po.po_number
  WHERE po.organization_id=v_org
  ON CONFLICT DO NOTHING;

  INSERT INTO sc_shipment_items(organization_id,shipment_id,purchase_order_id,purchase_order_item_id,quantity_shipped,quantity_received)
  SELECT v_org,sh.id,poi.purchase_order_id,poi.id,poi.quantity_ordered,poi.quantity_received
  FROM purchase_order_items poi
  JOIN purchase_orders po ON po.organization_id=poi.organization_id AND po.id=poi.purchase_order_id
  JOIN sc_inbound_shipments sh ON sh.organization_id=v_org AND sh.shipment_number='SHP-'||po.po_number
  WHERE poi.organization_id=v_org AND po.status='received'
  ON CONFLICT DO NOTHING;

  -- Repair booking timestamps created by the earlier version of this seed.
  -- Shipment created_at is the time the demo database row was inserted, not when
  -- the carrier booking occurred. Use the shipment's planned departure instead.
  UPDATE sc_shipment_events e
  SET occurred_at = COALESCE(sh.planned_departure_at, sh.actual_departure_at, sh.created_at)
  FROM sc_inbound_shipments sh
  WHERE e.organization_id = v_org
    AND e.shipment_id = sh.id
    AND sh.organization_id = v_org
    AND sh.status = 'delivered'
    AND e.event_code = 'booked'
    AND e.status_after = 'booked'
    AND e.notes = 'Synthetic demo booking event.'
    AND e.source = 'system'
    AND e.occurred_at IS DISTINCT FROM COALESCE(sh.planned_departure_at, sh.actual_departure_at, sh.created_at);

  -- Add a booking event at the planned departure time, not the DB row creation time.
  INSERT INTO sc_shipment_events(organization_id,shipment_id,event_code,status_after,location_name,city,state,country,occurred_at,notes,source)
  SELECT v_org,sh.id,'booked','booked',sh.origin_city,sh.origin_city,sh.origin_state,sh.origin_country,
         COALESCE(sh.planned_departure_at, sh.actual_departure_at, sh.created_at),
          'Synthetic demo booking event.','system'
  FROM sc_inbound_shipments sh WHERE sh.organization_id=v_org AND sh.status='delivered'
  ON CONFLICT DO NOTHING;
  INSERT INTO sc_shipment_events(organization_id,shipment_id,event_code,status_after,location_name,city,state,country,occurred_at,notes,source)
  SELECT v_org,sh.id,'picked_up','picked_up',sh.origin_city,sh.origin_city,sh.origin_state,sh.origin_country,sh.actual_departure_at,
         'Synthetic demo pickup event.','system'
  FROM sc_inbound_shipments sh WHERE sh.organization_id=v_org AND sh.status='delivered'
  ON CONFLICT DO NOTHING;
  INSERT INTO sc_shipment_events(organization_id,shipment_id,event_code,status_after,location_name,city,state,country,occurred_at,notes,source)
  SELECT v_org,sh.id,'arrived_warehouse','delivered',wh.name,wh.city,wh.state,'India',sh.actual_arrival_at,
         'Synthetic demo warehouse arrival event.','system'
  FROM sc_inbound_shipments sh
  JOIN warehouses wh ON wh.organization_id=sh.organization_id AND wh.id=sh.destination_warehouse_id
  WHERE sh.organization_id=v_org AND sh.status='delivered'
  ON CONFLICT DO NOTHING;

  -- One new, open PO in transit for an end-to-end demo.
  SELECT id INTO v_supplier_id FROM suppliers WHERE organization_id=v_org AND supplier_code='SUP-003';
  IF v_supplier_id IS NOT NULL THEN
    INSERT INTO purchase_orders(organization_id,supplier_id,po_number,order_date,expected_date,status,total_amount)
    VALUES(v_org,v_supplier_id,'PO-SC-DEMO-TRANSIT',DATE '2026-11-03',DATE '2026-11-12','sent',0)
    ON CONFLICT (organization_id,po_number) DO NOTHING;
    SELECT id INTO v_po_id FROM purchase_orders WHERE organization_id=v_org AND po_number='PO-SC-DEMO-TRANSIT';
    SELECT id INTO v_product_id FROM products WHERE organization_id=v_org AND sku='SKU-001';
    IF v_po_id IS NOT NULL AND v_product_id IS NOT NULL THEN
      INSERT INTO purchase_order_items(organization_id,purchase_order_id,product_id,quantity_ordered,quantity_received,unit_cost,line_total)
      SELECT v_org,v_po_id,v_product_id,60,0,p.unit_cost,60*p.unit_cost FROM products p
      WHERE p.organization_id=v_org AND p.id=v_product_id
        AND NOT EXISTS (SELECT 1 FROM purchase_order_items x WHERE x.organization_id=v_org AND x.purchase_order_id=v_po_id AND x.product_id=v_product_id);
      UPDATE purchase_orders SET total_amount=(SELECT COALESCE(sum(line_total),0) FROM purchase_order_items WHERE organization_id=v_org AND purchase_order_id=v_po_id)
      WHERE organization_id=v_org AND id=v_po_id;
      SELECT id INTO v_site_id FROM sc_supplier_sites WHERE organization_id=v_org AND supplier_id=v_supplier_id AND is_primary;
      INSERT INTO sc_inbound_shipments(
        organization_id,shipment_number,supplier_id,supplier_site_id,destination_warehouse_id,
        origin_city,origin_state,origin_country,origin_country_code,carrier_name,carrier_service,tracking_number,
        transport_mode,status,planned_departure_at,actual_departure_at,promised_arrival_at,current_eta_at,currency,notes
      )
      SELECT v_org,'SHP-SC-DEMO-TRANSIT',v_supplier_id,v_site_id,v_wh_id,site.origin_city,site.origin_state,
        site.origin_country,site.origin_country_code,'Deccan Surface Logistics','Surface','DEMO-TRACK-TRANSIT-001',
        'road','in_transit',timestamptz '2026-11-04 09:00:00+05:30',timestamptz '2026-11-05 08:30:00+05:30',
        timestamptz '2026-11-12 18:00:00+05:30',timestamptz '2026-11-11 18:00:00+05:30',orgs.base_currency,
        'Synthetic active shipment for the local Supply Chain demonstration.'
      FROM sc_supplier_sites site JOIN organizations orgs ON orgs.id=v_org
      WHERE site.organization_id=v_org AND site.id=v_site_id
      ON CONFLICT (organization_id,shipment_number) DO NOTHING;
      SELECT id INTO v_shipment_id FROM sc_inbound_shipments WHERE organization_id=v_org AND shipment_number='SHP-SC-DEMO-TRANSIT';
      INSERT INTO sc_shipment_purchase_orders(organization_id,shipment_id,purchase_order_id) VALUES(v_org,v_shipment_id,v_po_id) ON CONFLICT DO NOTHING;
      INSERT INTO sc_shipment_items(organization_id,shipment_id,purchase_order_id,purchase_order_item_id,quantity_shipped,quantity_received)
      SELECT v_org,v_shipment_id,v_po_id,id,quantity_ordered,0 FROM purchase_order_items WHERE organization_id=v_org AND purchase_order_id=v_po_id
      ON CONFLICT DO NOTHING;
      INSERT INTO sc_shipment_events(organization_id,shipment_id,event_code,status_after,location_name,city,state,country,occurred_at,notes,source)
      VALUES
        (v_org,v_shipment_id,'booked','booked','Supplier origin','Bengaluru','Karnataka','India',timestamptz '2026-11-03 11:00:00+05:30','Synthetic booking event.','system'),
        (v_org,v_shipment_id,'picked_up','picked_up','Supplier origin','Bengaluru','Karnataka','India',timestamptz '2026-11-04 09:00:00+05:30','Synthetic pickup event.','system'),
        (v_org,v_shipment_id,'in_transit','in_transit','Transit hub','Kurnool','Andhra Pradesh','India',timestamptz '2026-11-05 08:30:00+05:30','Synthetic in-transit event.','system')
      ON CONFLICT DO NOTHING;
      INSERT INTO sc_shipment_costs(organization_id,shipment_id,cost_type,description,amount,currency,charge_date,reference)
      SELECT v_org,v_shipment_id,'freight','Synthetic demo freight charge',4200,base_currency,DATE '2026-11-05','DEMO-FREIGHT-TRANSIT'
      FROM organizations WHERE id=v_org
      ON CONFLICT DO NOTHING;
    END IF;
  END IF;

  -- One delayed shipment to demonstrate exception monitoring.
  SELECT id INTO v_supplier_id FROM suppliers WHERE organization_id=v_org AND supplier_code='SUP-002';
  IF v_supplier_id IS NOT NULL THEN
    INSERT INTO purchase_orders(organization_id,supplier_id,po_number,order_date,expected_date,status,total_amount)
    VALUES(v_org,v_supplier_id,'PO-SC-DEMO-DELAY',DATE '2026-10-22',DATE '2026-10-31','sent',0)
    ON CONFLICT (organization_id,po_number) DO NOTHING;
    SELECT id INTO v_po_id FROM purchase_orders WHERE organization_id=v_org AND po_number='PO-SC-DEMO-DELAY';
    SELECT id INTO v_product_id FROM products WHERE organization_id=v_org AND sku='SKU-002';
    IF v_po_id IS NOT NULL AND v_product_id IS NOT NULL THEN
      INSERT INTO purchase_order_items(organization_id,purchase_order_id,product_id,quantity_ordered,quantity_received,unit_cost,line_total)
      SELECT v_org,v_po_id,v_product_id,80,0,p.unit_cost,80*p.unit_cost FROM products p
      WHERE p.organization_id=v_org AND p.id=v_product_id
        AND NOT EXISTS (SELECT 1 FROM purchase_order_items x WHERE x.organization_id=v_org AND x.purchase_order_id=v_po_id AND x.product_id=v_product_id);
      UPDATE purchase_orders SET total_amount=(SELECT COALESCE(sum(line_total),0) FROM purchase_order_items WHERE organization_id=v_org AND purchase_order_id=v_po_id)
      WHERE organization_id=v_org AND id=v_po_id;
      SELECT id INTO v_site_id FROM sc_supplier_sites WHERE organization_id=v_org AND supplier_id=v_supplier_id AND is_primary;
      INSERT INTO sc_inbound_shipments(
        organization_id,shipment_number,supplier_id,supplier_site_id,destination_warehouse_id,
        origin_city,origin_state,origin_country,origin_country_code,carrier_name,tracking_number,
        transport_mode,status,planned_departure_at,actual_departure_at,promised_arrival_at,current_eta_at,currency,notes
      )
      SELECT v_org,'SHP-SC-DEMO-DELAY',v_supplier_id,v_site_id,v_wh_id,site.origin_city,site.origin_state,
        site.origin_country,site.origin_country_code,'Demo National Logistics','DEMO-TRACK-DELAY-001',
        'road','delayed',timestamptz '2026-10-23 09:00:00+05:30',timestamptz '2026-10-24 10:00:00+05:30',
        timestamptz '2026-10-31 18:00:00+05:30',timestamptz '2026-11-05 18:00:00+05:30',orgs.base_currency,
        'Synthetic delayed shipment for the local Supply Chain exception demonstration.'
      FROM sc_supplier_sites site JOIN organizations orgs ON orgs.id=v_org
      WHERE site.organization_id=v_org AND site.id=v_site_id
      ON CONFLICT (organization_id,shipment_number) DO NOTHING;
      SELECT id INTO v_shipment_id FROM sc_inbound_shipments WHERE organization_id=v_org AND shipment_number='SHP-SC-DEMO-DELAY';
      INSERT INTO sc_shipment_purchase_orders(organization_id,shipment_id,purchase_order_id) VALUES(v_org,v_shipment_id,v_po_id) ON CONFLICT DO NOTHING;
      INSERT INTO sc_shipment_items(organization_id,shipment_id,purchase_order_id,purchase_order_item_id,quantity_shipped,quantity_received)
      SELECT v_org,v_shipment_id,v_po_id,id,quantity_ordered,0 FROM purchase_order_items WHERE organization_id=v_org AND purchase_order_id=v_po_id
      ON CONFLICT DO NOTHING;
      INSERT INTO sc_shipment_events(organization_id,shipment_id,event_code,status_after,location_name,city,state,country,occurred_at,notes,source)
      VALUES
        (v_org,v_shipment_id,'booked','booked','Supplier origin','Mumbai','Maharashtra','India',timestamptz '2026-10-22 11:00:00+05:30','Synthetic booking event.','system'),
        (v_org,v_shipment_id,'picked_up','picked_up','Supplier origin','Mumbai','Maharashtra','India',timestamptz '2026-10-24 10:00:00+05:30','Synthetic pickup event.','system'),
        (v_org,v_shipment_id,'delayed','delayed','Regional transit hub','Nashik','Maharashtra','India',timestamptz '2026-11-04 12:00:00+05:30','Synthetic weather-related delay event.','system')
      ON CONFLICT DO NOTHING;
      INSERT INTO sc_shipment_costs(organization_id,shipment_id,cost_type,description,amount,currency,charge_date,reference)
      SELECT v_org,v_shipment_id,'freight','Synthetic demo freight charge',6800,base_currency,DATE '2026-10-24','DEMO-FREIGHT-DELAY'
      FROM organizations WHERE id=v_org
      ON CONFLICT DO NOTHING;
    END IF;
  END IF;
END $$;

COMMIT;
