-- The report methodology must match the selected rubric version.

create or replace function public.create_multi_match_scout_report_bundle(
  p_player_id uuid,
  p_rubric_version_id uuid,
  p_report_date date,
  p_methodology_version text,
  p_main_role text,
  p_alternative_roles text[],
  p_main_role_evidence text,
  p_strengths text,
  p_development_areas text,
  p_final_verdict text,
  p_full_match_review_confirmed boolean,
  p_session_ids uuid[],
  p_snapshot jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $function$
declare
  v_session_count integer;
  v_match_count integer;
  v_methodology_version text;
begin
  if auth.uid() is null or not private.is_vel_staff() then
    raise exception 'Only authenticated Vel Scouting staff can create multi-match reports.'
      using errcode = '42501';
  end if;

  if p_player_id is null or p_rubric_version_id is null then
    raise exception 'Player and rubric version are required.'
      using errcode = '22023';
  end if;

  if p_session_ids is null
     or cardinality(p_session_ids) < 2
     or array_position(p_session_ids, null) is not null then
    raise exception 'At least two scouting sessions are required.'
      using errcode = '22023';
  end if;

  if (
    select count(distinct selected_id)
    from unnest(p_session_ids) as selected(selected_id)
  ) <> cardinality(p_session_ids) then
    raise exception 'Duplicate scouting session IDs are not allowed.'
      using errcode = '22023';
  end if;

  select count(*), count(distinct s.match_id)
    into v_session_count, v_match_count
  from public.scouting_sessions s
  where s.id = any(p_session_ids)
    and s.player_id = p_player_id
    and s.rubric_version_id = p_rubric_version_id
    and s.status in ('completed','locked');

  if v_session_count <> cardinality(p_session_ids) then
    raise exception 'Every selected session must be completed or locked and match the player and rubric.'
      using errcode = '22023';
  end if;

  if v_match_count < 2 then
    raise exception 'At least two distinct matches are required for a multi-match report.'
      using errcode = '22023';
  end if;

  select rv.methodology_version
    into v_methodology_version
  from public.rubric_versions rv
  where rv.id = p_rubric_version_id;

  if v_methodology_version is null or p_methodology_version is distinct from v_methodology_version then
    raise exception 'The report methodology must match the selected rubric version.'
      using errcode = '22023';
  end if;

  return public.create_scout_report_bundle(
    p_player_id,
    p_report_date,
    v_methodology_version,
    p_main_role,
    p_alternative_roles,
    p_main_role_evidence,
    p_strengths,
    p_development_areas,
    p_final_verdict,
    p_full_match_review_confirmed,
    p_session_ids,
    p_snapshot
  );
end;
$function$;
