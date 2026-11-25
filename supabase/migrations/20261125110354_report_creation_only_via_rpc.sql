-- Reports can only be created through the report functions: a staff user can no longer insert a draft report
-- with a forged evidence grade or general rating directly through the API.
-- Mechanism: create_scout_report_bundle sets a transaction-local flag (vel.report_rpc) around its INSERT; the insert guard
-- requires that flag for the API roles. The flag cannot be set from the API (set_config is not exposed) and is reset right after the insert.
-- Maintenance connections (migrations, SQL editor) are not affected.
--
-- Rollback:
--   1) restore the previous insert guard (status check only):
--      create or replace function private.guard_scout_report_insert() returns trigger language plpgsql set search_path = '' as $f$
--      begin
--        if current_user in ('authenticated','anon') and new.report_status <> 'draft' then
--          raise exception 'New reports must start as drafts.' using errcode = '55000';
--        end if;
--        return new;
--      end; $f$;
--   2) remove the two `perform set_config('vel.report_rpc', ...)` lines from public.create_scout_report_bundle
--      (re-create it from 20261111105655_use_existing_secure_scout_report_bundle.sql / 20261111105858_fix_report_bundle_uuid_aggregate.sql lineage).

do $migration$
declare
  v_def text;
begin
  select pg_get_functiondef('public.create_scout_report_bundle(uuid,date,text,text,text[],text,text,text,text,boolean,uuid[],jsonb)'::regprocedure)
    into v_def;
  if v_def is null then
    raise exception 'create_scout_report_bundle not found';
  end if;
  if position('vel.report_rpc' in v_def) = 0 then
    if (length(v_def) - length(replace(v_def, 'insert into public.scout_reports (', ''))) / length('insert into public.scout_reports (') <> 1 then
      raise exception 'unexpected function shape: insert anchor not unique';
    end if;
    if (length(v_def) - length(replace(v_def, ') returning id into v_report_id;', ''))) / length(') returning id into v_report_id;') <> 1 then
      raise exception 'unexpected function shape: returning anchor not unique';
    end if;
    v_def := replace(v_def, 'insert into public.scout_reports (',
      E'perform set_config(''vel.report_rpc'', ''on'', true);\n  insert into public.scout_reports (');
    v_def := replace(v_def, ') returning id into v_report_id;',
      E') returning id into v_report_id;\n  perform set_config(''vel.report_rpc'', ''off'', true);');
    execute v_def;
  end if;
end
$migration$;

create or replace function private.guard_scout_report_insert()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if current_user in ('authenticated','anon') then
    if new.report_status <> 'draft' then
      raise exception 'New reports must start as drafts.'
        using errcode = '55000';
    end if;
    if coalesce(current_setting('vel.report_rpc', true), '') <> 'on' then
      raise exception 'Reports can only be created through the report function.'
        using errcode = '55000';
    end if;
  end if;
  return new;
end;
$$;
