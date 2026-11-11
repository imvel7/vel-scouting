-- Atomic creation of a private multi-match scouting report.
-- Only authenticated Vel staff may execute this invoker-rights function.
create or replace function public.create_multi_match_scout_report(
  p_player_id uuid,
  p_rubric_version_id uuid,
  p_session_ids uuid[],
  p_report_date date,
  p_general_rating numeric,
  p_evidence_grade text,
  p_main_role text,
  p_alternative_roles text[],
  p_strengths text,
  p_development_areas text,
  p_final_verdict text,
  p_snapshot jsonb
)
returns uuid
language plpgsql
security invoker
set search_path = public, pg_temp
as $function$
declare
  v_user_id uuid := auth.uid();
  v_methodology_version text;
  v_session_count integer;
  v_match_count integer;
  v_report_id uuid;
begin
  if v_user_id is null or not private.is_vel_staff() then
    raise exception 'Vel Scouting staff access is required' using errcode = '42501';
  end if;

  if p_player_id is null or p_rubric_version_id is null or p_report_date is null then
    raise exception 'Player, rubric version and report date are required' using errcode = '22023';
  end if;

  if p_general_rating is not null and (p_general_rating < 1 or p_general_rating > 10) then
    raise exception 'General rating must be between 1 and 10' using errcode = '22023';
  end if;

  if p_evidence_grade is not null and p_evidence_grade not in ('A','B','C') then
    raise exception 'Evidence grade must be A, B or C' using errcode = '22023';
  end if;

  if p_snapshot is null or jsonb_typeof(p_snapshot) <> 'object' then
    raise exception 'A report snapshot object is required' using errcode = '22023';
  end if;

  if p_session_ids is null
     or cardinality(p_session_ids) < 2
     or array_position(p_session_ids, null) is not null then
    raise exception 'At least two valid scouting sessions are required' using errcode = '22023';
  end if;

  if (
    select count(distinct selected_id)
    from unnest(p_session_ids) as selected(selected_id)
  ) <> cardinality(p_session_ids) then
    raise exception 'Duplicate scouting session IDs are not allowed' using errcode = '22023';
  end if;

  select count(*), count(distinct s.match_id)
    into v_session_count, v_match_count
  from public.scouting_sessions s
  where s.id = any(p_session_ids)
    and s.player_id = p_player_id
    and s.rubric_version_id = p_rubric_version_id
    and s.status in ('completed','locked');

  if v_session_count <> cardinality(p_session_ids) then
    raise exception 'Every selected session must belong to this player and rubric and be completed or locked' using errcode = '22023';
  end if;

  if v_match_count < 2 then
    raise exception 'Selected sessions must cover at least two different matches' using errcode = '22023';
  end if;

  select rv.methodology_version
    into v_methodology_version
  from public.rubric_versions rv
  where rv.id = p_rubric_version_id;

  if v_methodology_version is null then
    raise exception 'Rubric version was not found' using errcode = '22023';
  end if;

  insert into public.scout_reports (
    player_id, report_date, methodology_version, evidence_grade,
    general_rating, main_role, alternative_roles, strengths,
    development_areas, final_verdict, report_status, created_by
  )
  values (
    p_player_id, p_report_date, v_methodology_version, p_evidence_grade,
    p_general_rating, nullif(btrim(p_main_role), ''),
    coalesce(p_alternative_roles, array[]::text[]),
    nullif(btrim(p_strengths), ''),
    nullif(btrim(p_development_areas), ''),
    nullif(btrim(p_final_verdict), ''),
    'draft', v_user_id
  )
  returning id into v_report_id;

  insert into public.scout_report_sessions(report_id, session_id, player_id)
  select v_report_id, s.id, p_player_id
  from public.scouting_sessions s
  where s.id = any(p_session_ids)
  order by s.created_at, s.id;

  insert into public.report_versions(report_id, version_number, report_snapshot)
  values (
    v_report_id,
    1,
    p_snapshot || jsonb_build_object(
      'report_id', v_report_id,
      'player_id', p_player_id,
      'rubric_version_id', p_rubric_version_id,
      'methodology_version', v_methodology_version,
      'session_ids', to_jsonb(p_session_ids),
      'created_by', v_user_id,
      'created_at', now(),
      'report_status', 'draft'
    )
  );

  return v_report_id;
end;
$function$;

revoke all on function public.create_multi_match_scout_report(
  uuid, uuid, uuid[], date, numeric, text, text, text[], text, text, text, jsonb
) from public, anon, authenticated;

grant execute on function public.create_multi_match_scout_report(
  uuid, uuid, uuid[], date, numeric, text, text, text[], text, text, text, jsonb
) to authenticated;

comment on function public.create_multi_match_scout_report(
  uuid, uuid, uuid[], date, numeric, text, text, text[], text, text, text, jsonb
) is 'Atomically creates a staff-only draft report, links validated completed scouting sessions, and writes immutable version 1 snapshot.';
