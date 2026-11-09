-- Optional 10-store clothing retail demo seed.
-- Run after the multi-store migration. Safe to re-run.
INSERT INTO retail_stores (organization_id, store_code, store_name, city, monthly_revenue_threshold)
SELECT '11111111-1111-4111-8111-111111111111'::uuid, v.store_code, v.store_name, v.city, v.threshold
FROM (VALUES
  ('ST01','Banjara Hills Flagship','Hyderabad',1500000::numeric),
  ('ST02','Kukatpally Store','Hyderabad',900000::numeric),
  ('ST03','Secunderabad Store','Secunderabad',850000::numeric),
  ('ST04','Warangal Central','Warangal',650000::numeric),
  ('ST05','Vijayawada Store','Vijayawada',800000::numeric),
  ('ST06','Guntur Store','Guntur',600000::numeric),
  ('ST07','Visakhapatnam Store','Visakhapatnam',1100000::numeric),
  ('ST08','Tirupati Store','Tirupati',700000::numeric),
  ('ST09','Karimnagar Store','Karimnagar',500000::numeric),
  ('ST10','Nizamabad Store','Nizamabad',450000::numeric)
) AS v(store_code,store_name,city,threshold)
WHERE EXISTS (
  SELECT 1 FROM organizations
  WHERE id='11111111-1111-4111-8111-111111111111'::uuid
)
ON CONFLICT (organization_id,store_code) DO NOTHING;
