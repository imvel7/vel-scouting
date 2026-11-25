-- Session status transitions in the database (until now only admin.html enforced the path).
-- For the API roles (authenticated, anon) a status change is allowed only along:
--   draft -> in_review (rubric has criteria and every criterion has a saved scoring state),
--   in_review -> completed (full rules from enforce_session_completion_rules),
--   completed -> in_review (reopen), completed -> locked.
-- Everything else (draft -> locked, in_review -> locked, in_review -> draft, ...) is rejected with SQLSTATE 55000.
-- Locked stays final through guard_scouting_session_changes. Maintenance connections are not affected.
--
-- Rollback: restore the previous body of private.validate_scouting_session_completion()
-- (see 20261125202823_enforce_session_completion_rules.sql).

create or replace function private.validate_scouting_session_completion()
returns trigger
language plpgsql
set search_path = ''
as $$
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
$$;

revoke all on function private.validate_scouting_session_completion() from public, anon, authenticated;
