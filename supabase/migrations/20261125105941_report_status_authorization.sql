-- Report status workflow authorization (builds on 20261124071112_protect_report_history).
--  * Publishing or archiving a report requires the admin role; editors can only move draft <-> review.
--  * A report without an evidence grade cannot be published.
--  * Rows inserted through the API must start as drafts (a staff user could previously insert a "published" row directly).
-- Database maintenance connections (postgres, migrations) are not affected: the role check applies to the API roles
-- `authenticated` and `anon` only.
--
-- Rollback (restores the previous guard and removes the insert guard):
--   DROP TRIGGER IF EXISTS scout_reports_guard_insert ON public.scout_reports;
--   DROP FUNCTION IF EXISTS private.guard_scout_report_insert();
--   then re-run `create or replace function private.guard_scout_report_history()` from
--   20261124071112_protect_report_history.sql.

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
    if old.report_status <> 'draft' and v_player_exists then
      raise exception 'Only draft reports can be deleted. Archive a published report instead.'
        using errcode = '55000';
    end if;
    return old;
  end if;

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

    if new.report_status in ('published','archived')
       and current_user in ('authenticated','anon')
       and not private.is_vel_admin() then
      raise exception 'Only an admin can publish or archive a report.'
        using errcode = '42501';
    end if;

    if new.report_status = 'published' and new.evidence_grade is null then
      raise exception 'A report without an evidence grade cannot be published.'
        using errcode = '55000';
    end if;
  end if;

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

create or replace function private.guard_scout_report_insert()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if current_user in ('authenticated','anon') and new.report_status <> 'draft' then
    raise exception 'New reports must start as drafts.'
      using errcode = '55000';
  end if;
  return new;
end;
$$;

revoke all on function private.guard_scout_report_insert() from public, anon, authenticated;

create trigger scout_reports_guard_insert
  before insert on public.scout_reports
  for each row execute function private.guard_scout_report_insert();
