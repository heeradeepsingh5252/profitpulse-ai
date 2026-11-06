ProfitPulse Supply Chain demo seed fix v3

This version resolves the follow-on PL/pgSQL variable/column name ambiguity by
renaming local variables consistently with a v_ prefix, including all product_id variable references (v_org, v_po_id,
v_product_id, v_shipment_id, v_site_id, v_wh_id, v_supplier_row).

It retains the earlier idempotent ON CONFLICT DO NOTHING fix for shipment-item
seeding. The seed remains an optional synthetic-data script for the local demo
organization only.

Apply by extracting into the project root, then rerun the seed with psql
-v ON_ERROR_STOP=1. A failed prior attempt inside BEGIN/COMMIT is rolled back
by PostgreSQL; do not rerun the database migration and do not reset volumes.
