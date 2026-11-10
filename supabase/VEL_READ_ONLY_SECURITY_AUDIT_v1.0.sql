-- VEL SCOUTING — READ-ONLY SUPABASE SECURITY AUDIT v1.0
-- Purpose: inspect table columns, RLS flags, policies and grants.
-- Safety: SELECT statements only. This file does not modify data, roles, grants or policies.
-- Run in Supabase SQL Editor using the project's normal SQL Editor session.
-- Do not paste passwords, JWTs, service_role keys or other secrets into GitHub/chat.

-- QUERY 1: table existence, RLS state, columns, policies and table-level grants.
WITH target_tables(table_name) AS (
  VALUES
    ('players'),
    ('clubs'),
    ('competitions'),
    ('seasons'),
    ('matches'),
    ('player_matches'),
    ('videos'),
    ('observations'),
    ('scout_reports'),
    ('report_versions'),
    ('user_roles')
),
table_state AS (
  SELECT
    t.table_name,
    c.relkind,
    COALESCE(c.relrowsecurity, false) AS rls_enabled,
    COALESCE(c.relforcerowsecurity, false) AS force_rls
  FROM target_tables t
  LEFT JOIN pg_namespace n
    ON n.nspname = 'public'
  LEFT JOIN pg_class c
    ON c.relnamespace = n.oid
   AND c.relname = t.table_name
   AND c.relkind IN ('r', 'p')
),
column_info AS (
  SELECT
    table_name,
    jsonb_agg(
      jsonb_build_object(
        'position', ordinal_position,
        'column', column_name,
        'type', data_type,
        'udt', udt_name,
        'nullable', is_nullable,
        'default', column_default
      )
      ORDER BY ordinal_position
    ) AS columns
  FROM information_schema.columns
  WHERE table_schema = 'public'
    AND table_name IN (SELECT table_name FROM target_tables)
  GROUP BY table_name
),
policy_info AS (
  SELECT
    tablename AS table_name,
    jsonb_agg(
      jsonb_build_object(
        'policy', policyname,
        'permissive', permissive,
        'roles', roles,
        'command', cmd,
        'using', qual,
        'with_check', with_check
      )
      ORDER BY policyname
    ) AS policies
  FROM pg_policies
  WHERE schemaname = 'public'
    AND tablename IN (SELECT table_name FROM target_tables)
  GROUP BY tablename
),
grant_info AS (
  SELECT
    table_name,
    jsonb_agg(
      jsonb_build_object(
        'grantee', grantee,
        'privilege', privilege_type,
        'grantable', is_grantable
      )
      ORDER BY grantee, privilege_type
    ) AS grants
  FROM information_schema.table_privileges
  WHERE table_schema = 'public'
    AND table_name IN (SELECT table_name FROM target_tables)
    AND grantee IN ('anon', 'authenticated', 'service_role', 'PUBLIC', 'public')
  GROUP BY table_name
)
SELECT
  s.table_name,
  (s.relkind IS NOT NULL) AS table_exists,
  s.rls_enabled,
  s.force_rls,
  COALESCE(c.columns, '[]'::jsonb) AS columns,
  COALESCE(p.policies, '[]'::jsonb) AS policies,
  COALESCE(g.grants, '[]'::jsonb) AS grants
FROM table_state s
LEFT JOIN column_info c USING (table_name)
LEFT JOIN policy_info p USING (table_name)
LEFT JOIN grant_info g USING (table_name)
ORDER BY s.table_name;


-- QUERY 2: security helper functions and trigger helpers.
-- Vel Scouting's SECURITY DEFINER policy helpers belong in the private schema.
SELECT
  n.nspname AS function_schema,
  p.proname AS function_name,
  pg_get_userbyid(p.proowner) AS owner,
  p.prosecdef AS security_definer,
  p.provolatile AS volatility,
  p.proconfig AS function_settings,
  pg_get_function_identity_arguments(p.oid) AS arguments,
  has_function_privilege('anon', p.oid, 'EXECUTE') AS anon_can_execute,
  has_function_privilege('authenticated', p.oid, 'EXECUTE') AS authenticated_can_execute,
  pg_get_functiondef(p.oid) AS definition
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname IN ('public', 'private')
  AND p.proname IN ('is_vel_staff', 'is_vel_admin', 'rls_auto_enable', 'set_updated_at')
ORDER BY n.nspname, p.proname;


-- QUERY 3: public views that might expose private match/video/scouting fields.
-- Only view names and SQL definitions are returned; no row data is selected.
SELECT
  table_name AS view_name,
  view_definition
FROM information_schema.views
WHERE table_schema = 'public'
  AND view_definition ~* '(videos|video_url|source_url|matches|player_matches|observations|report_versions)'
ORDER BY table_name;


-- QUERY 4: public-schema objects with broad privileges on relevant tables.
-- This makes inherited PUBLIC grants visible as well as anon/authenticated grants.
SELECT
  table_name,
  grantee,
  privilege_type,
  is_grantable
FROM information_schema.table_privileges
WHERE table_schema = 'public'
  AND table_name IN (
    'players', 'clubs', 'competitions', 'seasons', 'matches',
    'player_matches', 'videos', 'observations', 'scout_reports',
    'report_versions', 'user_roles'
  )
ORDER BY table_name, grantee, privilege_type;


-- QUERY 5: default privileges for future objects in public.
-- Review which creator roles automatically grant privileges to anon/authenticated.
SELECT
  pg_get_userbyid(d.defaclrole) AS creator_role,
  COALESCE(n.nspname, '(all schemas)') AS target_schema,
  CASE d.defaclobjtype
    WHEN 'r' THEN 'tables'
    WHEN 'S' THEN 'sequences'
    WHEN 'f' THEN 'functions'
    WHEN 'T' THEN 'types'
    WHEN 'n' THEN 'schemas'
    ELSE d.defaclobjtype::text
  END AS object_type,
  CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,
  a.privilege_type,
  a.is_grantable
FROM pg_default_acl d
LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
CROSS JOIN LATERAL aclexplode(d.defaclacl) a
WHERE d.defaclnamespace = 0 OR n.nspname = 'public'
ORDER BY creator_role, target_schema, object_type, grantee, a.privilege_type;
