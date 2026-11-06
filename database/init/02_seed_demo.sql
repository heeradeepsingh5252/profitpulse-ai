DO $$
DECLARE
  org uuid := '11111111-1111-4111-8111-111111111111';
  u uuid := '22222222-2222-4222-8222-222222222222';
  cat record;
  acct_code text;
BEGIN
  INSERT INTO organizations(id,legal_name,display_name,industry,base_currency)
  VALUES(org,'Deccan Wholesale and Retail Demo Private Limited','Deccan Wholesale & Retail Demo Co.','retail_and_distribution','INR');
  INSERT INTO app_users(id,email,full_name) VALUES(u,'demo.owner@profitpulse.local','Demo Owner');
  INSERT INTO organization_members(organization_id,user_id,role) VALUES(org,u,'owner');

  INSERT INTO gl_accounts(organization_id,account_code,account_name,account_type,financial_category,financial_statement,normal_balance)
  VALUES
  (org,'1000','Cash and Cash Equivalents','asset','cash','balance_sheet','debit'),
  (org,'1100','Accounts Receivable','asset','receivable','balance_sheet','debit'),
  (org,'1200','Inventory','asset','inventory','balance_sheet','debit'),
  (org,'1500','Property, Plant and Equipment','asset','fixed_asset','balance_sheet','debit'),
  (org,'1590','Accumulated Depreciation','contra_asset','accumulated_depreciation','balance_sheet','credit'),
  (org,'2000','Accounts Payable','liability','payable','balance_sheet','credit'),
  (org,'2100','Bank Loan Payable','liability','debt','balance_sheet','credit'),
  (org,'2200','Income Tax Payable','liability','tax_payable','balance_sheet','credit'),
  (org,'3000','Owner Capital','equity','equity','balance_sheet','credit'),
  (org,'4000','Sales Revenue','revenue','revenue','income_statement','credit'),
  (org,'4050','Sales Returns and Allowances','contra_revenue','contra_revenue','income_statement','debit'),
  (org,'5000','Cost of Goods Sold','expense','cogs','income_statement','debit'),
  (org,'6000','Salaries and Wages','expense','operating_expense','income_statement','debit'),
  (org,'6100','Rent Expense','expense','operating_expense','income_statement','debit'),
  (org,'6200','Marketing Expense','expense','operating_expense','income_statement','debit'),
  (org,'6300','Utilities and Administration','expense','operating_expense','income_statement','debit'),
  (org,'6400','Logistics Expense','expense','operating_expense','income_statement','debit'),
  (org,'7000','Depreciation Expense','expense','depreciation','income_statement','debit'),
  (org,'7100','Amortisation Expense','expense','amortization','income_statement','debit'),
  (org,'7200','Interest Expense','expense','interest_expense','income_statement','debit'),
  (org,'7300','Income Tax Expense','expense','income_tax','income_statement','debit');

  INSERT INTO customers(organization_id,customer_code,name,email,phone,city,state,region,customer_type,credit_limit)
  SELECT org,'CUS-'||lpad(gs.n::text,4,'0'),
    (ARRAY['Aarav Traders','BlueSky Retail','City Mart','Deccan Stores','Evergreen Supplies','Fresh Basket','Galaxy Distributors','Harbor Retail','Indus Enterprises','Jupiter Stores'])[((gs.n-1)%10)+1]||' '||gs.n,
    'customer'||gs.n||'@example.test','+91-90000'||lpad(gs.n::text,5,'0'),
    (ARRAY['Hyderabad','Warangal','Vijayawada','Bengaluru','Chennai','Pune'])[((gs.n-1)%6)+1],
    (ARRAY['Telangana','Telangana','Andhra Pradesh','Karnataka','Tamil Nadu','Maharashtra'])[((gs.n-1)%6)+1],
    (ARRAY['South','South','South','South','South','West'])[((gs.n-1)%6)+1],
    CASE WHEN gs.n%4=0 THEN 'wholesale' ELSE 'retail' END,
    CASE WHEN gs.n%4=0 THEN 250000 ELSE 50000 END
  FROM generate_series(1,30) AS gs(n);

  INSERT INTO suppliers(organization_id,supplier_code,name,email,city,state,payment_terms_days)
  SELECT org,'SUP-'||lpad(gs.n::text,3,'0'),
    (ARRAY['Metro Wholesale Supply','Prime Goods Pvt Ltd','SouthStar Manufacturing','Unity Consumer Products','Vega Components'])[gs.n],
    'supplier'||gs.n||'@example.test',
    (ARRAY['Hyderabad','Mumbai','Bengaluru','Chennai','Pune'])[gs.n],
    (ARRAY['Telangana','Maharashtra','Karnataka','Tamil Nadu','Maharashtra'])[gs.n],30
  FROM generate_series(1,5) AS gs(n);

  INSERT INTO products(organization_id,sku,name,category,unit_of_measure,unit_price,unit_cost,reorder_level)
  VALUES
  (org,'SKU-001','Wireless Keyboard','Electronics','unit',1499,900,20),
  (org,'SKU-002','Bluetooth Headphones','Electronics','unit',2499,1550,15),
  (org,'SKU-003','Office Chair','Furniture','unit',6499,4200,8),
  (org,'SKU-004','LED Desk Lamp','Home and Office','unit',1199,650,25),
  (org,'SKU-005','Storage Organizer','Home and Office','unit',899,480,30),
  (org,'SKU-006','Cotton T-Shirt','Apparel','unit',699,320,40),
  (org,'SKU-007','Running Shoes','Apparel','pair',2999,1800,18),
  (org,'SKU-008','Water Bottle','Accessories','unit',499,180,50),
  (org,'SKU-009','USB-C Hub','Electronics','unit',1899,1100,15),
  (org,'SKU-010','Notebook Pack','Stationery','pack',299,120,60);

  INSERT INTO warehouses(organization_id,warehouse_code,name,city,state)
  VALUES(org,'WH-HYD','Hyderabad Central Warehouse','Hyderabad','Telangana'),
        (org,'WH-WGL','Warangal Distribution Hub','Warangal','Telangana');

  INSERT INTO orders(organization_id,customer_id,order_number,order_date,order_type,status,sales_channel,sales_region)
  SELECT org,c.id,'ORD-2026-'||lpad(gs.n::text,5,'0'),DATE '2026-08-01'+((gs.n*3)%90),
    CASE WHEN gs.n%3=0 THEN 'wholesale' ELSE 'retail' END,'delivered',
    CASE WHEN gs.n%4=0 THEN 'online' ELSE 'store' END,
    (ARRAY['South','South','West','North'])[((gs.n-1)%4)+1]
  FROM generate_series(1,90) AS gs(n)
  JOIN customers c ON c.organization_id=org AND c.customer_code='CUS-'||lpad((((gs.n-1)%30)+1)::text,4,'0');

  WITH item_source AS (
    SELECT o.id AS order_id, p.id AS product_id,
      (1+((substring(o.order_number from 10)::integer+gs.item_no)%4))::numeric AS qty,
      p.unit_price,p.unit_cost,
      ((1+((substring(o.order_number from 10)::integer+gs.item_no)%5))::numeric/100) AS disc_rate
    FROM orders o CROSS JOIN generate_series(1,2) AS gs(item_no)
    JOIN products p ON p.organization_id=org AND p.sku='SKU-'||lpad((((substring(o.order_number from 10)::integer+gs.item_no*3-1)%10)+1)::text,3,'0')
    WHERE o.organization_id=org
  )
  INSERT INTO order_items(organization_id,order_id,product_id,quantity,unit_price,unit_cost_snapshot,discount_amount,line_total)
  SELECT org,order_id,product_id,qty,unit_price,unit_cost,
    round(qty*unit_price*disc_rate,2),round(qty*unit_price-qty*unit_price*disc_rate,2)
  FROM item_source;

  UPDATE orders o SET subtotal=x.subtotal,discount_amount=x.discount,total_amount=x.total
  FROM (SELECT order_id,sum(quantity*unit_price) subtotal,sum(discount_amount) discount,sum(line_total) total
        FROM order_items WHERE organization_id=org GROUP BY order_id) x
  WHERE o.organization_id=org AND o.id=x.order_id;

  INSERT INTO purchase_orders(organization_id,supplier_id,po_number,order_date,expected_date,received_date,status,total_amount)
  SELECT org,s.id,'PO-2026-'||lpad(gs.n::text,4,'0'),DATE '2026-08-01'+gs.n*3,DATE '2026-08-05'+gs.n*3,DATE '2026-08-06'+gs.n*3,'received',0
  FROM generate_series(1,12) AS gs(n)
  JOIN suppliers s ON s.organization_id=org AND s.supplier_code='SUP-'||lpad((((gs.n-1)%5)+1)::text,3,'0');

  INSERT INTO purchase_order_items(organization_id,purchase_order_id,product_id,quantity_ordered,quantity_received,unit_cost,line_total)
  SELECT org,po.id,p.id,30+(gs.item_no%20),30+(gs.item_no%20),p.unit_cost,(30+(gs.item_no%20))*p.unit_cost
  FROM purchase_orders po CROSS JOIN generate_series(1,2) AS gs(item_no)
  JOIN products p ON p.organization_id=org AND p.sku='SKU-'||lpad((((gs.item_no+substring(po.po_number from 9)::integer-1)%10)+1)::text,3,'0')
  WHERE po.organization_id=org;
  UPDATE purchase_orders po SET total_amount=x.total
  FROM (SELECT purchase_order_id,sum(line_total) total FROM purchase_order_items WHERE organization_id=org GROUP BY purchase_order_id) x
  WHERE po.organization_id=org AND po.id=x.purchase_order_id;

  INSERT INTO inventory_movements(organization_id,product_id,warehouse_id,movement_date,movement_type,quantity_delta,unit_cost,reference)
  SELECT org,poi.product_id,w.id,po.received_date,'purchase',poi.quantity_received,poi.unit_cost,po.po_number
  FROM purchase_order_items poi JOIN purchase_orders po ON po.organization_id=poi.organization_id AND po.id=poi.purchase_order_id
  JOIN warehouses w ON w.organization_id=org AND w.warehouse_code='WH-HYD' WHERE poi.organization_id=org;
  INSERT INTO inventory_movements(organization_id,product_id,warehouse_id,movement_date,movement_type,quantity_delta,unit_cost,reference)
  SELECT org,oi.product_id,w.id,o.order_date,'sale',-oi.quantity,oi.unit_cost_snapshot,o.order_number
  FROM order_items oi JOIN orders o ON o.organization_id=oi.organization_id AND o.id=oi.order_id
  JOIN warehouses w ON w.organization_id=org AND w.warehouse_code=CASE WHEN o.sales_region='South' THEN 'WH-HYD' ELSE 'WH-WGL' END
  WHERE oi.organization_id=org;

  INSERT INTO inventory_snapshots(organization_id,product_id,warehouse_id,snapshot_date,quantity_on_hand,unit_cost)
  SELECT org,p.id,w.id,DATE '2026-11-01',
    CASE WHEN w.warehouse_code='WH-HYD' THEN 80+(substring(p.sku from 5)::integer*3) ELSE 20+substring(p.sku from 5)::integer END,
    p.unit_cost
  FROM products p CROSS JOIN warehouses w WHERE p.organization_id=org AND w.organization_id=org;

  INSERT INTO payments(organization_id,order_id,payment_direction,payment_date,amount,payment_method,status,reference)
  SELECT org,o.id,'inbound',o.order_date+10,round(o.total_amount*0.65,2),'bank_transfer','completed','COLL-'||o.order_number
  FROM orders o WHERE o.organization_id=org AND substring(o.order_number from 10)::integer%3<>0;

  INSERT INTO payments(organization_id,purchase_order_id,payment_direction,payment_date,amount,payment_method,status,reference)
  SELECT org,po.id,'outbound',po.received_date+15,round(po.total_amount*0.70,2),'bank_transfer','completed','PAY-'||po.po_number
  FROM purchase_orders po WHERE po.organization_id=org;

  INSERT INTO expenses(organization_id,expense_date,category,vendor_name,description,amount,payment_status)
  VALUES
  (org,'2026-08-31','salaries','Payroll','August payroll',120000,'paid'),
  (org,'2026-09-30','salaries','Payroll','September payroll',125000,'paid'),
  (org,'2026-10-31','salaries','Payroll','October payroll',130000,'paid'),
  (org,'2026-08-05','rent','Property Owner','Warehouse rent',45000,'paid'),
  (org,'2026-09-05','rent','Property Owner','Warehouse rent',45000,'paid'),
  (org,'2026-10-05','rent','Property Owner','Warehouse rent',45000,'paid'),
  (org,'2026-08-15','marketing','Digital Agency','Campaign spend',25000,'paid'),
  (org,'2026-09-15','marketing','Digital Agency','Campaign spend',32000,'paid'),
  (org,'2026-10-15','marketing','Digital Agency','Campaign spend',41000,'paid'),
  (org,'2026-10-20','utilities','Utility Provider','Power and internet',18000,'paid'),
  (org,'2026-10-21','logistics','Transport Vendor','Local transport',28000,'paid'),
  (org,'2026-10-22','admin','Office Vendor','Administration',14000,'paid');

  PERFORM create_balanced_journal_entry(org,'2026-08-01','Opening balances','OPEN-2026',
    '[{"account_code":"1000","debit":2000000,"credit":0},{"account_code":"1200","debit":1500000,"credit":0},{"account_code":"1500","debit":800000,"credit":0},{"account_code":"2000","debit":0,"credit":400000},{"account_code":"2100","debit":0,"credit":600000},{"account_code":"3000","debit":0,"credit":3300000}]'::jsonb);

  -- Post operational ledger entries by month so period comparisons remain meaningful.
  FOR cat IN
    SELECT date_trunc('month',received_date)::date AS month_start, sum(total_amount) AS amount
    FROM purchase_orders WHERE organization_id=org GROUP BY 1 ORDER BY 1
  LOOP
    PERFORM create_balanced_journal_entry(org,(cat.month_start+interval '1 month - 1 day')::date,
      'Inventory purchases received','PURCHASES-'||to_char(cat.month_start,'YYYYMM'),
      jsonb_build_array(jsonb_build_object('account_code','1200','debit',cat.amount,'credit',0),
                        jsonb_build_object('account_code','2000','debit',0,'credit',cat.amount)));
  END LOOP;

  FOR cat IN
    SELECT m.month_start,
      (SELECT COALESCE(sum(o.total_amount),0) FROM orders o
       WHERE o.organization_id=org AND date_trunc('month',o.order_date)::date=m.month_start) AS sales_amount,
      (SELECT COALESCE(sum(oi.quantity*oi.unit_cost_snapshot),0)
       FROM order_items oi JOIN orders o ON o.organization_id=oi.organization_id AND o.id=oi.order_id
       WHERE oi.organization_id=org AND date_trunc('month',o.order_date)::date=m.month_start) AS cogs_amount
    FROM (SELECT DISTINCT date_trunc('month',order_date)::date AS month_start FROM orders WHERE organization_id=org) m
    ORDER BY m.month_start
  LOOP
    IF cat.sales_amount > 0 THEN
      PERFORM create_balanced_journal_entry(org,(cat.month_start+interval '1 month - 1 day')::date,
        'Revenue from delivered orders','SALES-'||to_char(cat.month_start,'YYYYMM'),
        jsonb_build_array(jsonb_build_object('account_code','1100','debit',cat.sales_amount,'credit',0),
                          jsonb_build_object('account_code','4000','debit',0,'credit',cat.sales_amount)));
    END IF;
    IF cat.cogs_amount > 0 THEN
      PERFORM create_balanced_journal_entry(org,(cat.month_start+interval '1 month - 1 day')::date,
        'Cost of goods sold','COGS-'||to_char(cat.month_start,'YYYYMM'),
        jsonb_build_array(jsonb_build_object('account_code','5000','debit',cat.cogs_amount,'credit',0),
                          jsonb_build_object('account_code','1200','debit',0,'credit',cat.cogs_amount)));
    END IF;
  END LOOP;

  FOR cat IN
    SELECT date_trunc('month',payment_date)::date AS month_start, sum(amount) AS amount
    FROM payments WHERE organization_id=org AND payment_direction='inbound' AND status='completed'
    GROUP BY 1 ORDER BY 1
  LOOP
    PERFORM create_balanced_journal_entry(org,(cat.month_start+interval '1 month - 1 day')::date,
      'Customer receipts','COLLECTIONS-'||to_char(cat.month_start,'YYYYMM'),
      jsonb_build_array(jsonb_build_object('account_code','1000','debit',cat.amount,'credit',0),
                        jsonb_build_object('account_code','1100','debit',0,'credit',cat.amount)));
  END LOOP;

  FOR cat IN
    SELECT date_trunc('month',payment_date)::date AS month_start, sum(amount) AS amount
    FROM payments WHERE organization_id=org AND payment_direction='outbound' AND status='completed'
    GROUP BY 1 ORDER BY 1
  LOOP
    PERFORM create_balanced_journal_entry(org,(cat.month_start+interval '1 month - 1 day')::date,
      'Supplier payments','SUPPLIER-PAYMENTS-'||to_char(cat.month_start,'YYYYMM'),
      jsonb_build_array(jsonb_build_object('account_code','2000','debit',cat.amount,'credit',0),
                        jsonb_build_object('account_code','1000','debit',0,'credit',cat.amount)));
  END LOOP;

  FOR cat IN
    SELECT date_trunc('month',expense_date)::date AS month_start, category, sum(amount) AS amount
    FROM expenses WHERE organization_id=org GROUP BY 1,2 ORDER BY 1,2
  LOOP
    acct_code := CASE cat.category WHEN 'salaries' THEN '6000' WHEN 'rent' THEN '6100'
      WHEN 'marketing' THEN '6200' WHEN 'utilities' THEN '6300' WHEN 'logistics' THEN '6400' ELSE '6300' END;
    PERFORM create_balanced_journal_entry(org,(cat.month_start+interval '1 month - 1 day')::date,
      'Operating expenses - '||cat.category,'OPEX-'||upper(cat.category)||'-'||to_char(cat.month_start,'YYYYMM'),
      jsonb_build_array(jsonb_build_object('account_code',acct_code,'debit',cat.amount,'credit',0),
                        jsonb_build_object('account_code','1000','debit',0,'credit',cat.amount)));
  END LOOP;

  FOR cat IN SELECT generate_series(DATE '2026-08-01',DATE '2026-10-01',interval '1 month')::date AS month_start
  LOOP
    PERFORM create_balanced_journal_entry(org,(cat.month_start+interval '1 month - 1 day')::date,
      'Depreciation expense','DEPR-'||to_char(cat.month_start,'YYYYMM'),
      '[{"account_code":"7000","debit":16666.67,"credit":0},{"account_code":"1590","debit":0,"credit":16666.67}]'::jsonb);
    PERFORM create_balanced_journal_entry(org,(cat.month_start+interval '1 month - 1 day')::date,
      'Interest expense','INTEREST-'||to_char(cat.month_start,'YYYYMM'),
      '[{"account_code":"7200","debit":8000,"credit":0},{"account_code":"1000","debit":0,"credit":8000}]'::jsonb);
    PERFORM create_balanced_journal_entry(org,(cat.month_start+interval '1 month - 1 day')::date,
      'Income tax expense','TAX-'||to_char(cat.month_start,'YYYYMM'),
      '[{"account_code":"7300","debit":10000,"credit":0},{"account_code":"2200","debit":0,"credit":10000}]'::jsonb);
  END LOOP;

  INSERT INTO fixed_assets(organization_id,asset_code,asset_name,acquisition_date,acquisition_cost,useful_life_months,residual_value)
  VALUES(org,'FA-001','Warehouse equipment','2026-08-01',800000,96,50000);
  INSERT INTO loan_accounts(organization_id,lender_name,loan_reference,principal_amount,annual_interest_rate,start_date,maturity_date,outstanding_principal)
  VALUES(org,'Demo Bank','TERM-LOAN-001',600000,11.5,'2026-08-01','2029-08-01',600000);
  INSERT INTO budgets(organization_id,period_start,period_end,metric_code,budget_amount)
  VALUES(org,'2026-10-01','2026-10-31','net_revenue',500000),(org,'2026-10-01','2026-10-31','operating_expense',250000);
END $$;
