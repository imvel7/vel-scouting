-- Vel Scouting: column-level privacy hardening for anonymous reads.
-- Applied to the live project as migration 20261121080323 (verified against the live schema on 2026-11-21).
--
-- Problem: anon had table-wide SELECT on players and scout_reports. RLS limits rows to
-- published records, but any column of a published row (players.date_of_birth,
-- scout_reports.created_by) was readable through a direct API call, even though
-- index.html only requests a fixed column list.
--
-- Fix: replace table-level SELECT with column-level SELECT for anon, excluding
-- players.date_of_birth and scout_reports.created_by. Columns referenced by RLS
-- policies (profile_status, current_club_id, report_status, player_id) stay readable,
-- because policy expressions are evaluated with the caller's privileges.
-- authenticated staff access is unchanged. clubs is left as is (name/location only).

REVOKE SELECT ON TABLE public.players FROM anon;
GRANT SELECT (
  id, full_name, nationality, current_club_id, main_position, secondary_position,
  preferred_foot, height_cm, profile_status, created_at, updated_at
) ON TABLE public.players TO anon;

REVOKE SELECT ON TABLE public.scout_reports FROM anon;
GRANT SELECT (
  id, player_id, report_date, methodology_version, evidence_grade, general_rating,
  main_role, alternative_roles, strengths, development_areas, final_verdict,
  report_status, created_at, updated_at
) ON TABLE public.scout_reports TO anon;


-- Verification (run read-only after applying):
-- select table_name, column_name from information_schema.column_privileges
--  where grantee='anon' and table_schema='public' and privilege_type='SELECT'
--    and table_name in ('players','scout_reports') order by 1,2;
-- Expect no date_of_birth and no created_by.
-- Rollback:
-- GRANT SELECT ON TABLE public.players, public.scout_reports TO anon;
