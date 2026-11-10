-- Vel Scouting: least-privilege hardening for existing public tables.
-- Applied to the live project as migration 20261110172515.
-- Note: Supabase's supabase_admin-owned default privileges are platform-managed
-- and were not modifiable through the connected postgres role; see the guide.

CREATE SCHEMA IF NOT EXISTS private AUTHORIZATION postgres;
REVOKE ALL ON SCHEMA private FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA private TO authenticated;

-- Move RLS helpers out of the API-exposed public schema.
ALTER FUNCTION public.is_vel_admin() SET SCHEMA private;
ALTER FUNCTION public.is_vel_staff() SET SCHEMA private;

-- These two helpers are used by RLS policies; authenticated needs EXECUTE.
REVOKE ALL ON FUNCTION private.is_vel_admin() FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION private.is_vel_staff() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION private.is_vel_admin() TO authenticated;
GRANT EXECUTE ON FUNCTION private.is_vel_staff() TO authenticated;

-- Keep the automatic RLS event trigger, but remove its function from the API schema.
ALTER FUNCTION public.rls_auto_enable() SET SCHEMA private;
REVOKE ALL ON FUNCTION private.rls_auto_enable() FROM PUBLIC, anon, authenticated, service_role;

-- Fix the mutable search_path warning on the timestamp trigger helper.
ALTER FUNCTION public.set_updated_at() SET search_path = pg_catalog;

-- Remove maintenance/DDL-level privileges from client roles on current tables.
REVOKE TRUNCATE, REFERENCES, TRIGGER, MAINTAIN
ON TABLE public.players, public.clubs, public.competitions, public.seasons,
          public.matches, public.player_matches, public.videos, public.observations,
          public.scout_reports, public.report_versions, public.user_roles
FROM anon, authenticated;

-- Preserve intended anonymous reads only.
GRANT SELECT ON TABLE public.players, public.clubs, public.scout_reports TO anon;

-- Future tables created as postgres do not inherit unnecessary DDL privileges.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE TRUNCATE, REFERENCES, TRIGGER, MAINTAIN ON TABLES FROM anon, authenticated, service_role;

-- Future public RPCs created as postgres must be explicitly granted.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon, authenticated;
