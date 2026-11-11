-- VEL SCOUT LIVE FUNCTION RECOVERY SNAPSHOT
-- Captured from project xlvteloclijsudxbwszd on 2026-11-11.
--
-- IMPORTANT:
-- This is a recovery baseline of the two CURRENT live function definitions only.
-- It is NOT a reconstruction of the six missing historical migration files.
-- It is NOT an instruction to apply this script to the active production database.
-- The script assumes the required schema, tables, columns, constraints, helper
-- functions (especially private.is_vel_staff()), and role setup already exist.
-- Test in a separate restored/staging database first. Review dependencies and
-- compare against the target database before any use.
--
-- Current observed ACL for both functions: postgres owner + authenticated EXECUTE.
-- Both functions are SECURITY INVOKER with an empty search_path.

CREATE OR REPLACE FUNCTION public.create_scout_report_bundle(p_player_id uuid, p_report_date date, p_methodology_version text, p_main_role text, p_alternative_roles text[], p_main_role_evidence text, p_strengths text, p_development_areas text, p_final_verdict text, p_full_match_review_confirmed boolean, p_session_ids uuid[], p_snapshot jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
declare
  v_user_id uuid;
  v_report_id uuid;
  v_rubric_version_id uuid;
  v_session_count integer;
  v_valid_session_count integer;
  v_match_count integer;
  v_score_count integer;
  v_full_match_count integer := 0;
  v_has_clip_sources boolean := false;
  v_evidence_grade text;
  v_general_rating numeric(4,2);
  v_category_metrics jsonb;
  v_category_count integer := 0;
  v_all_areas_eligible boolean := false;
  v_snapshot jsonb;
begin
  v_user_id := auth.uid();
  if v_user_id is null then raise exception 'Authentication is required to create a scout report.'; end if;
  if not private.is_vel_staff() then raise exception 'Only Vel Scouting staff can create scout reports.'; end if;
  if p_player_id is null or p_report_date is null then raise exception 'Player and report date are required.'; end if;
  if nullif(btrim(coalesce(p_methodology_version, '')), '') is null then raise exception 'Methodology version is required.'; end if;
  if p_session_ids is null or cardinality(p_session_ids) < 1 then raise exception 'At least one scouting session must support the report.'; end if;

  select count(*), count(distinct s.id), count(distinct s.rubric_version_id), min(s.rubric_version_id::text)::uuid
    into v_session_count, v_valid_session_count, v_match_count, v_rubric_version_id
  from unnest(p_session_ids) as chosen(session_id)
  left join public.scouting_sessions s on s.id = chosen.session_id and s.player_id = p_player_id;

  if v_valid_session_count <> cardinality(p_session_ids) then raise exception 'Every selected session must belong to the report player.'; end if;
  if v_session_count <> v_valid_session_count then raise exception 'Duplicate or invalid scouting session identifiers were supplied.'; end if;
  if v_match_count <> 1 then raise exception 'All selected sessions must use the same rubric version.'; end if;

  select count(distinct s.match_id) into v_match_count
  from public.scouting_sessions s where s.id = any(p_session_ids) and s.player_id = p_player_id;
  if v_match_count < 1 then raise exception 'Selected sessions do not contain a valid match sample.'; end if;

  if (nullif(btrim(coalesce(p_main_role, '')), '') is not null or coalesce(cardinality(p_alternative_roles), 0) > 0)
     and (v_match_count < 3 or char_length(btrim(coalesce(p_main_role_evidence, ''))) < 50) then
    raise exception 'Role conclusions require at least three separate matches and a role-evidence note of at least 50 characters.';
  end if;

  select count(*) into v_score_count
  from public.criterion_scores cs
  where cs.session_id = any(p_session_ids) and cs.rubric_version_id = v_rubric_version_id;
  if v_score_count = 0 then raise exception 'At least one saved criterion score is required to create a consolidated report.'; end if;

  select
    count(distinct v.match_id) filter (where v.video_type = 'full_match'),
    coalesce(bool_or(v.video_type in ('highlights','extended_highlights','other')), false)
  into v_full_match_count, v_has_clip_sources
  from public.scouting_session_videos sv
  join public.videos v on v.id = sv.video_id and v.match_id = sv.match_id
  where sv.session_id = any(p_session_ids);

  if coalesce(p_full_match_review_confirmed, false) and v_full_match_count >= 6 then
    v_evidence_grade := 'A';
  elsif coalesce(p_full_match_review_confirmed, false) and v_full_match_count >= 3 then
    v_evidence_grade := 'B';
  elsif (coalesce(p_full_match_review_confirmed, false) and v_full_match_count >= 1) or v_has_clip_sources then
    v_evidence_grade := 'C';
  else
    v_evidence_grade := null;
  end if;

  with selected_sessions as (
    select s.id, s.match_id
    from public.scouting_sessions s
    where s.id = any(p_session_ids) and s.player_id = p_player_id and s.rubric_version_id = v_rubric_version_id
  ),
  match_ids as (select distinct match_id from selected_sessions),
  match_criterion_raw as (
    select
      m.match_id,c.id as criterion_id,c.rubric_category_id,c.weight_percent,
      count(ss.id) as session_count,count(cs.id) as score_row_count,
      count(cs.id) filter (where cs.applicability = 'scored') as scored_row_count,
      count(cs.id) filter (where cs.applicability = 'not_applicable'
        and nullif(btrim(coalesce(cs.rationale, '')), '') is not null) as reasoned_na_row_count,
      avg(cs.score) filter (where cs.applicability = 'scored') as match_score
    from match_ids m
    cross join public.rubric_criteria c
    join selected_sessions ss on ss.match_id = m.match_id
    left join public.criterion_scores cs
      on cs.session_id = ss.id and cs.criterion_id = c.id and cs.rubric_version_id = v_rubric_version_id
    where c.rubric_version_id = v_rubric_version_id
    group by m.match_id,c.id,c.rubric_category_id,c.weight_percent
  ),
  match_criterion as (
    select *,
      case when scored_row_count > 0 then 'scored'
           when score_row_count = session_count and reasoned_na_row_count = session_count then 'not_applicable'
           else 'not_observed' end as match_state
    from match_criterion_raw
  ),
  category_rollup as (
    select
      cat.id as category_id,cat.category_name,cat.category_weight_percent,
      coalesce(sum(mc.weight_percent) filter (where mc.match_state <> 'not_applicable'),0) as applicable_weight,
      coalesce(sum(mc.weight_percent) filter (where mc.match_state = 'scored'),0) as scored_weight,
      coalesce(sum(mc.match_score * mc.weight_percent) filter (where mc.match_state = 'scored'),0) as weighted_score_total
    from public.rubric_categories cat
    left join match_criterion mc on mc.rubric_category_id = cat.id
    where cat.rubric_version_id = v_rubric_version_id
    group by cat.id,cat.category_name,cat.category_weight_percent,cat.sort_order
  ),
  metrics as (
    select category_id,category_name,category_weight_percent,applicable_weight,scored_weight,
      case when scored_weight > 0 then weighted_score_total / scored_weight else null end as area_score,
      case when applicable_weight > 0 then scored_weight::numeric / applicable_weight * 100 else 0 end as coverage_pct
    from category_rollup
  )
  select
    coalesce(jsonb_agg(jsonb_build_object(
      'category_id',category_id,'category_name',category_name,
      'category_weight_percent',category_weight_percent,
      'applicable_weight_units',applicable_weight,'scored_weight_units',scored_weight,
      'coverage_percent',round(coverage_pct,2),
      'area_score',case when area_score is null then null else round(area_score,2) end,
      'eligible',area_score is not null and coverage_pct >= 80
    ) order by category_name),'[]'::jsonb),
    count(*),
    coalesce(bool_and(area_score is not null and coverage_pct >= 80),false),
    case when count(*) > 0 and bool_and(area_score is not null and coverage_pct >= 80)
      then round(sum(area_score * category_weight_percent) / nullif(sum(category_weight_percent),0),2)
      else null end
  into v_category_metrics,v_category_count,v_all_areas_eligible,v_general_rating
  from metrics;

  if v_category_count = 0 then raise exception 'No scoring categories exist for the selected rubric version.'; end if;
  if coalesce(v_evidence_grade,'') not in ('A','B') or not v_all_areas_eligible then v_general_rating := null; end if;

  v_snapshot := coalesce(p_snapshot,'{}'::jsonb) || jsonb_build_object(
    'player_id',p_player_id,'report_date',p_report_date,'methodology_version',p_methodology_version,
    'rubric_version_id',v_rubric_version_id,'evidence_grade',v_evidence_grade,
    'full_match_count',v_full_match_count,'full_match_review_confirmed',coalesce(p_full_match_review_confirmed,false),
    'general_rating',v_general_rating,'general_rating_eligible',v_general_rating is not null,
    'category_metrics',v_category_metrics,'session_ids',to_jsonb(p_session_ids),
    'main_role_evidence',p_main_role_evidence,'report_status','draft','created_by',v_user_id
  );

  insert into public.scout_reports (
    player_id,report_date,methodology_version,evidence_grade,general_rating,main_role,
    alternative_roles,strengths,development_areas,final_verdict,report_status,created_by
  ) values (
    p_player_id,p_report_date,p_methodology_version,v_evidence_grade,v_general_rating,
    nullif(btrim(coalesce(p_main_role,'')),''),
    coalesce(p_alternative_roles,'{}'::text[]),
    nullif(btrim(coalesce(p_strengths,'')),''),
    nullif(btrim(coalesce(p_development_areas,'')),''),
    nullif(btrim(coalesce(p_final_verdict,'')),''),
    'draft',v_user_id
  ) returning id into v_report_id;

  insert into public.scout_report_sessions(report_id,session_id,player_id,contribution_note)
  select v_report_id,s.id,p_player_id,'Included in the consolidated multi-match performance profile.'
  from public.scouting_sessions s where s.id = any(p_session_ids) and s.player_id = p_player_id;

  insert into public.report_versions(report_id,version_number,report_snapshot)
  values(v_report_id,1,v_snapshot);

  return jsonb_build_object(
    'report_id',v_report_id,'evidence_grade',v_evidence_grade,
    'full_match_count',v_full_match_count,'general_rating',v_general_rating,
    'general_rating_eligible',v_general_rating is not null,'category_metrics',v_category_metrics
  );
end;
$function$
;

REVOKE ALL ON FUNCTION public.create_scout_report_bundle(
  uuid, date, text, text, text[], text, text, text, text, boolean, uuid[], jsonb
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.create_scout_report_bundle(
  uuid, date, text, text, text[], text, text, text, text, boolean, uuid[], jsonb
) TO authenticated;

CREATE OR REPLACE FUNCTION public.create_multi_match_scout_report_bundle(p_player_id uuid, p_rubric_version_id uuid, p_report_date date, p_methodology_version text, p_main_role text, p_alternative_roles text[], p_main_role_evidence text, p_strengths text, p_development_areas text, p_final_verdict text, p_full_match_review_confirmed boolean, p_session_ids uuid[], p_snapshot jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
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
$function$
;

REVOKE ALL ON FUNCTION public.create_multi_match_scout_report_bundle(
  uuid, uuid, date, text, text, text[], text, text, text, text, boolean, uuid[], jsonb
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.create_multi_match_scout_report_bundle(
  uuid, uuid, date, text, text, text[], text, text, text, text, boolean, uuid[], jsonb
) TO authenticated;

-- End of live-state recovery snapshot.
