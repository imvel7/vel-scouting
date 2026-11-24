-- Protect report history: report snapshots are append-only, the numbers and methodology of a report cannot be
-- edited after creation, and a report that left draft can only change status along an allowed path.
-- Erasure path is kept: deleting the player (ON DELETE CASCADE) still removes their reports and versions.
--
-- Rollback:
--   DROP TRIGGER IF EXISTS scout_reports_guard_history ON public.scout_reports;
--   DROP TRIGGER IF EXISTS report_versions_guard_history ON public.report_versions;
--   DROP TRIGGER IF EXISTS scout_report_sessions_guard_history ON public.scout_report_sessions;
--   DROP FUNCTION IF EXISTS private.guard_scout_report_history();
--   DROP FUNCTION IF EXISTS private.guard_report_versions_history();
--   DROP FUNCTION IF EXISTS private.guard_report_sessions_history();

create or replace function private.guard_scout_report_history()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_player_exists boolean;
begin
  if tg_op = 'DELETE' then
    select exists (select 1 from public.players p where p.id = old.player_id) into v_player_exists;
    -- Only drafts can be deleted directly; removing the player (erasure) cascades through.
    if old.report_status <> 'draft' and v_player_exists then
      raise exception 'Only draft reports can be deleted. Archive a published report instead.'
        using errcode = '55000';
    end if;
    return old;
  end if;

  -- UPDATE: computed and identifying fields never change after creation.
  if new.player_id is distinct from old.player_id
     or new.methodology_version is distinct from old.methodology_version
     or new.evidence_grade is distinct from old.evidence_grade
     or new.general_rating is distinct from old.general_rating
     or new.created_at is distinct from old.created_at
     or (new.created_by is distinct from old.created_by and new.created_by is not null) then
    raise exception 'Player, methodology version, evidence grade, general rating and creation fields of a report cannot be changed. Create a new report instead.'
      using errcode = '55000';
  end if;

  if new.report_status is distinct from old.report_status then
    if not (
         (old.report_status = 'draft'     and new.report_status in ('review','archived'))
      or (old.report_status = 'review'    and new.report_status in ('draft','published','archived'))
      or (old.report_status = 'published' and new.report_status = 'archived')
    ) then
      raise exception 'Report status change % -> % is not allowed.', old.report_status, new.report_status
        using errcode = '55000';
    end if;
  end if;

  -- Once a report left draft, its written content is frozen (status may still move along the path above).
  if old.report_status <> 'draft'
     and (new.report_date is distinct from old.report_date
       or new.main_role is distinct from old.main_role
       or new.alternative_roles is distinct from old.alternative_roles
       or new.strengths is distinct from old.strengths
       or new.development_areas is distinct from old.development_areas
       or new.final_verdict is distinct from old.final_verdict) then
    raise exception 'The content of a report that left draft cannot be edited.'
      using errcode = '55000';
  end if;

  return new;
end;
$$;

create or replace function private.guard_report_versions_history()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_status text;
begin
  if tg_op = 'UPDATE' then
    raise exception 'Report versions are append-only; add a new version instead of editing one.'
      using errcode = '55000';
  end if;
  -- DELETE: allowed for drafts, or when the parent report is already gone (cascade).
  select r.report_status into v_status from public.scout_reports r where r.id = old.report_id;
  if v_status is not null and v_status <> 'draft' then
    raise exception 'Versions of a report that left draft cannot be deleted.'
      using errcode = '55000';
  end if;
  return old;
end;
$$;

create or replace function private.guard_report_sessions_history()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_report_id uuid;
  v_status text;
begin
  if tg_op = 'UPDATE' then
    raise exception 'Report-session links cannot be edited.' using errcode = '55000';
  end if;
  v_report_id := case when tg_op = 'INSERT' then new.report_id else old.report_id end;
  select r.report_status into v_status from public.scout_reports r where r.id = v_report_id;
  if v_status is not null and v_status <> 'draft' then
    raise exception 'Sessions supporting a report that left draft cannot be added or removed.'
      using errcode = '55000';
  end if;
  return case when tg_op = 'INSERT' then new else old end;
end;
$$;

revoke all on function private.guard_scout_report_history() from public, anon, authenticated;
revoke all on function private.guard_report_versions_history() from public, anon, authenticated;
revoke all on function private.guard_report_sessions_history() from public, anon, authenticated;

create trigger scout_reports_guard_history
  before update or delete on public.scout_reports
  for each row execute function private.guard_scout_report_history();

create trigger report_versions_guard_history
  before update or delete on public.report_versions
  for each row execute function private.guard_report_versions_history();

create trigger scout_report_sessions_guard_history
  before insert or update or delete on public.scout_report_sessions
  for each row execute function private.guard_report_sessions_history();
