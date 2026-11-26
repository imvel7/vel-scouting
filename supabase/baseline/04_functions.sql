create schema if not exists private;

CREATE OR REPLACE FUNCTION public.set_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'pg_catalog'
AS $function$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION private.is_vel_admin()
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select exists (
    select 1 from public.user_roles
    where user_id = (select auth.uid()) and role = 'admin'
  );
$function$;

CREATE OR REPLACE FUNCTION private.is_vel_staff()
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select exists (
    select 1 from public.user_roles
    where user_id = (select auth.uid()) and role in ('admin', 'editor')
  );
$function$;

CREATE OR REPLACE FUNCTION private.guard_report_sessions_history()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
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
$function$;

CREATE OR REPLACE FUNCTION private.guard_report_versions_history()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
declare
  v_status text;
begin
  if tg_op = 'UPDATE' then
    raise exception 'Report versions are append-only; add a new version instead of editing one.'
      using errcode = '55000';
  end if;
  select r.report_status into v_status from public.scout_reports r where r.id = old.report_id;
  if v_status is not null and v_status <> 'draft' then
    raise exception 'Versions of a report that left draft cannot be deleted.'
      using errcode = '55000';
  end if;
  return old;
end;
$function$;

CREATE OR REPLACE FUNCTION private.guard_scout_report_history()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
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
$function$;

CREATE OR REPLACE FUNCTION private.guard_scout_report_insert()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
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
$function$;

CREATE OR REPLACE FUNCTION private.guard_scouting_session_changes()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE
  v_old jsonb;
  v_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status IN ('completed', 'locked') THEN
      RAISE EXCEPTION 'Scouting session % is % and read-only; DELETE is not allowed.', OLD.id, OLD.status
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
  END IF;

  IF OLD.status = 'locked' THEN
    RAISE EXCEPTION 'Scouting session % is locked and read-only; UPDATE is not allowed.', OLD.id
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;

  IF OLD.status = 'completed' THEN
    v_old := to_jsonb(OLD) - 'updated_at';
    v_new := to_jsonb(NEW) - 'updated_at';

    IF NEW.status = 'in_review' THEN
      IF (v_old - 'status' - 'completed_at') IS DISTINCT FROM (v_new - 'status' - 'completed_at') THEN
        RAISE EXCEPTION 'Scouting session % is completed and read-only; reopening may only change status and completed_at.', OLD.id
          USING ERRCODE = 'integrity_constraint_violation';
      END IF;
    ELSIF NEW.status = 'locked' THEN
      IF (v_old - 'status') IS DISTINCT FROM (v_new - 'status') THEN
        RAISE EXCEPTION 'Scouting session % is completed and read-only; locking may only change status.', OLD.id
          USING ERRCODE = 'integrity_constraint_violation';
      END IF;
    ELSE
      RAISE EXCEPTION 'Scouting session % is completed and read-only; it can only move to in_review or locked.', OLD.id
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
  END IF;

  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION private.guard_scouting_session_children()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
DECLARE
  v_ids uuid[];
  v_id uuid;
  v_status text;
BEGIN
  IF TG_OP = 'INSERT' THEN
    v_ids := ARRAY[NEW.session_id];
  ELSIF TG_OP = 'DELETE' THEN
    v_ids := ARRAY[OLD.session_id];
  ELSE
    v_ids := ARRAY[OLD.session_id, NEW.session_id];
  END IF;

  FOREACH v_id IN ARRAY v_ids LOOP
    CONTINUE WHEN v_id IS NULL;
    SELECT s.status INTO v_status FROM public.scouting_sessions s WHERE s.id = v_id FOR SHARE;
    IF v_status IN ('completed', 'locked') THEN
      RAISE EXCEPTION 'Scouting session % is % and read-only; % on % is not allowed. Reopen the session to in_review first.', v_id, v_status, TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
  END LOOP;

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION private.seed_default_video_rights_assessments()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
begin
  insert into public.video_rights_assessments (
    video_id, right_type, status, basis_type, territory_scope, evidence_note
  )
  select
    new.id, rights.right_type, 'unknown', 'unknown', 'unknown',
    'No item-specific usage-rights evidence has been reviewed yet.'
  from unnest(array[
    'manual_scouting', 'automated_analysis', 'commercial_use',
    'download_storage', 'clip_extraction', 'redistribution'
  ]::text[]) as rights(right_type);

  return new;
end;
$function$;

CREATE OR REPLACE FUNCTION private.validate_scouting_session_completion()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
declare
  v_criteria int;
  v_missing int;
  v_scored int;
  v_no_rationale int;
  v_no_observation int;
  v_high_unsupported int;
begin
  if current_user not in ('authenticated','anon') then
    return new;
  end if;
  if new.status is not distinct from old.status then
    return new;
  end if;

  if not (
       (old.status = 'draft'     and new.status = 'in_review')
    or (old.status = 'in_review' and new.status = 'completed')
    or (old.status = 'completed' and new.status in ('in_review','locked'))
  ) then
    raise exception 'Session status cannot change from % to %.', old.status, new.status using errcode = '55000';
  end if;

  if new.status not in ('in_review','completed') or old.status = 'completed' then
    return new;
  end if;

  select count(*) into v_criteria from public.rubric_criteria c where c.rubric_version_id = new.rubric_version_id;
  if v_criteria = 0 then
    raise exception 'The rubric of this session has no criteria.' using errcode = '55000';
  end if;

  select count(*) into v_missing
  from public.rubric_criteria c
  where c.rubric_version_id = new.rubric_version_id
    and not exists (
      select 1 from public.criterion_scores s
      where s.session_id = new.id and s.criterion_id = c.id and s.rubric_version_id = new.rubric_version_id
    );
  if v_missing > 0 then
    raise exception '% criteria have no saved scoring state; save all criteria first.', v_missing using errcode = '55000';
  end if;

  if new.status = 'in_review' then
    return new;
  end if;

  select count(*) into v_scored from public.criterion_scores s
  where s.session_id = new.id and s.applicability = 'scored';
  if v_scored = 0 then
    raise exception 'At least one criterion must be scored before the session is completed.' using errcode = '55000';
  end if;

  select count(*) into v_no_rationale from public.criterion_scores s
  where s.session_id = new.id and nullif(btrim(coalesce(s.rationale, '')), '') is null;
  if v_no_rationale > 0 then
    raise exception '% criteria have no rationale.', v_no_rationale using errcode = '55000';
  end if;

  select count(*) into v_no_observation from public.criterion_scores s
  where s.session_id = new.id and s.applicability = 'scored'
    and not exists (select 1 from public.observations o where o.session_id = new.id and o.criterion_id = s.criterion_id);
  if v_no_observation > 0 then
    raise exception '% scored criteria have no timestamped observation.', v_no_observation using errcode = '55000';
  end if;

  select count(*) into v_high_unsupported from public.criterion_scores s
  where s.session_id = new.id and s.applicability = 'scored' and s.score >= 9
    and (char_length(btrim(coalesce(s.rationale, ''))) < 50
      or (select count(*) from public.observations o where o.session_id = new.id and o.criterion_id = s.criterion_id) < 2);
  if v_high_unsupported > 0 then
    raise exception '% criteria scored 9 or 10 need a rationale of at least 50 characters and two observations.', v_high_unsupported
      using errcode = '55000';
  end if;

  return new;
end;
$function$;

revoke all on function
  private.guard_report_sessions_history(), private.guard_report_versions_history(),
  private.guard_scout_report_history(), private.guard_scout_report_insert(),
  private.guard_scouting_session_changes(), private.guard_scouting_session_children(),
  private.seed_default_video_rights_assessments(), private.validate_scouting_session_completion()
  from public, anon, authenticated;
revoke all on function private.is_vel_admin(), private.is_vel_staff() from public, anon;
grant execute on function private.is_vel_admin(), private.is_vel_staff() to authenticated;
