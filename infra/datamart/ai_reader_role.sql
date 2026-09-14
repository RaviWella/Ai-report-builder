-- ============================================================================
-- WS-4 · Defense-in-depth datamart role: `ai_reader`
-- ----------------------------------------------------------------------------
-- The Report Builder already enforces read-only at the APP layer (a read-only
-- login user + read-only transaction + assert_select_only). This adds the
-- DATABASE layer underneath it: a role granted SELECT *only* on the semantic +
-- curated mart schemas, with NO writes, NO DDL, and NO access to raw/staging.
-- So even if every app guard were bypassed, the database itself still refuses.
--
-- Apply once per tenant datamart database (hrm_wh_<tenant>). Then set
--   DATAMART_READONLY_ROLE=ai_reader
-- and the runtime will `SET ROLE ai_reader` on every datamart session.
--
-- Mirrors mint-analytics' `ai_reader` (USAGE+SELECT on the semantic schema only),
-- widened here to the marts this project's catalogue actually reads (hr_semantic
-- views + hr marts/dims/facts), while keeping staging/raw out.
-- Run as a superuser / the datamart owner. Adjust schema names if yours differ.
-- ============================================================================

\set semantic_schema 'hr_semantic'
\set core_schema     'hr'
\set app_login_user  'warehouse_user'   -- the role the app logs in as

-- 1) The role: a NOLOGIN group the app's login user is made a member of.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_reader') THEN
    CREATE ROLE ai_reader NOLOGIN;
  END IF;
END $$;

-- 2) USAGE on the two allowed schemas only (NOT on any raw/staging schema).
GRANT USAGE ON SCHEMA :"semantic_schema" TO ai_reader;
GRANT USAGE ON SCHEMA :"core_schema"     TO ai_reader;

-- 3) SELECT only — semantic views (all) + the marts/dims/facts in the core schema.
GRANT SELECT ON ALL TABLES IN SCHEMA :"semantic_schema" TO ai_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA :"core_schema"     TO ai_reader;

-- 4) Keep staging/raw OUT. If staging objects live inside the core schema as
--    stg_* , revoke them explicitly. (Raw in a separate schema simply never gets
--    USAGE above, so it stays inaccessible.)
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'hr' AND tablename LIKE 'stg\_%' ESCAPE '\'
  LOOP
    EXECUTE format('REVOKE ALL ON hr.%I FROM ai_reader', r.tablename);
  END LOOP;
END $$;

-- 5) Future tables in these schemas are SELECT-only for ai_reader too.
ALTER DEFAULT PRIVILEGES IN SCHEMA :"semantic_schema" GRANT SELECT ON TABLES TO ai_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA :"core_schema"     GRANT SELECT ON TABLES TO ai_reader;

-- 6) Belt-and-braces: never let ai_reader write or change schema.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON ALL TABLES IN SCHEMA :"semantic_schema" FROM ai_reader;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON ALL TABLES IN SCHEMA :"core_schema" FROM ai_reader;

-- 7) Let the app's login user assume the role (so `SET ROLE ai_reader` works).
GRANT ai_reader TO :"app_login_user";

-- ----------------------------------------------------------------------------
-- Acceptance check (WS-4) — run after applying; app guards are irrelevant here:
--   SET ROLE ai_reader;
--   SELECT count(*) FROM hr_semantic.vw_payroll_summary;   -- ✓ allowed
--   SELECT count(*) FROM hr.mart_employee_current;         -- ✓ allowed (mart)
--   CREATE TABLE hr.x(i int);                              -- ✗ permission denied
--   UPDATE hr.mart_employee_current SET emp_no = emp_no;   -- ✗ read-only / denied
--   SELECT * FROM hr.stg_ledger LIMIT 1;                   -- ✗ permission denied (if present)
--   RESET ROLE;
-- ============================================================================
