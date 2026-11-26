# Schema baseline (snapshot of the live database, 25 November 2026)

The first migrations in `supabase/migrations/` assume tables that were created in the Supabase dashboard before the
migration ledger started, so the migration files alone cannot rebuild the database. These files are a snapshot of the
live `public` schema (plus the `private` helper functions), taken after migration `20261125203057`:

`01_tables` → `02_constraints` → `03_indexes` → `04_functions` → `05_triggers` → `06_rls_policies_grants` → `07_report_functions`.
`00_supabase_stubs.sql` is CI-only (stand-ins for Supabase roles and `auth`).

Verified: replayed on an empty PostgreSQL, `schema_fingerprint.sql` returns identical counts and hashes to the live
database for columns (203), constraints (131), indexes (86), policies (26), triggers (17), functions (11),
RLS flags (21) and table grants (83), and the two report bundle functions match the live definitions.

CI (`.github/workflows/db-baseline-tests.yml`) loads the baseline into a throw-away PostgreSQL 17 and runs the rolled-back
tests in `supabase/tests/` (with a tiny rubric fixture, `ci_fixture.sql`). New migrations must also update this baseline
(or the fingerprint comparison with live will show the drift). Not included: seed data (rubrics, anchors), the platform
function `rls_auto_enable`, `auth`/`storage` internals.
