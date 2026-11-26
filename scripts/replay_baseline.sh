#!/usr/bin/env bash
# Rebuilds the schema on an empty PostgreSQL database from supabase/baseline/ and runs the rolled-back
# database tests in supabase/tests/. Usage: PGHOST=... PGUSER=... PGDATABASE=... scripts/replay_baseline.sh
# Each test ends with RAISE EXCEPTION '<NAME>_TESTS_PASSED' (so it rolls back); anything else fails the run.
set -u
cd "$(dirname "$0")/.."
P="psql -q -v ON_ERROR_STOP=1"
for f in supabase/baseline/0*.sql; do echo "load $f"; $P -f "$f" || { echo "FAILED to load $f"; exit 1; }; done
$P -f supabase/tests/ci_fixture.sql || exit 1
fail=0
for t in report_creation_guard report_history_protection report_status_authorization session_completion_rules session_transition_rules; do
  out=$(psql -q -f "supabase/tests/${t}_test.sql" 2>&1)
  if echo "$out" | grep -q "TESTS_PASSED"; then echo "PASS $t: $(echo "$out" | grep -o 'TESTS_PASSED.*' | head -1 | cut -c1-120)"; else echo "FAIL $t"; echo "$out" | head -5; fail=1; fi
done
exit $fail
