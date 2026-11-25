-- Session completion rules in the database (they only lived in admin.html until now).
-- For the API roles (authenticated, anon) a session can become `completed` only from `in_review` and only when:
--   * the rubric has criteria and every criterion has a saved scoring state for this session,
--   * at least one criterion is scored,
--   * every criterion row (scored, not applicable, not observed) has a rationale,
--   * every scored criterion has at least one observation tied to it,
--   * a score of 9 or 10 has a rationale of at least 50 characters and at least two observations.
-- These are the same rules the staff panel applies, so a direct API call cannot skip them.
-- Maintenance connections (migrations, SQL editor) are not affected.
--
-- Also closes a table gap: a 'scored' row with a NULL score passed the old CHECK (NULL counts as pass),
-- so criterion_scores_scored_requires_score now requires a score for scored rows (table had 0 rows when applied).
--
-- Rollback:
--   ALTER TABLE public.criterion_scores DROP CONSTRAINT IF EXISTS criterion_scores_scored_requires_score;
--   DROP TRIGGER IF EXISTS scouting_sessions_validate_completion ON public.scouting_sessions;
--   DROP FUNCTION IF EXISTS private.validate_scouting_session_completion();

alter table public.criterion_scores
  add constraint criterion_scores_scored_requires_score
  check (applicability <> 'scored' or score is not null);

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
  if not (new.status = 'completed' and old.status is distinct from 'completed') then
    return new;
  end if;

  if old.status <> 'in_review' then
    raise exception 'A session must be in review before it can be completed.' using errcode = '55000';
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

create trigger scouting_sessions_validate_completion
  before update on public.scouting_sessions
  for each row execute function private.validate_scouting_session_completion();
