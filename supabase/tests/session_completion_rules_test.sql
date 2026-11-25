-- Self-rolling-back test: session completion rules and table constraints, with real API roles.
do $$
declare
  v_editor uuid := gen_random_uuid();
  v_rv uuid; v_player uuid; v_m uuid; v_pm uuid; v_s uuid; v_vid uuid; v_sv uuid;
  v_crit uuid[]; v_n int; i int;
  results text := ''; failed text := '';
begin
  select id into v_rv from public.rubric_versions where status in ('pilot','active') order by created_at desc limit 1;
  select array_agg(id order by sort_order) into v_crit from public.rubric_criteria where rubric_version_id = v_rv;
  v_n := cardinality(v_crit);
  insert into auth.users(id, email) values (v_editor, 'zz-editor@example.invalid');
  insert into public.user_roles(user_id, role) values (v_editor, 'editor');
  insert into public.players(full_name) values ('ZZ completion player') returning id into v_player;
  insert into public.matches(match_date) values (current_date) returning id into v_m;
  insert into public.player_matches(player_id, match_id) values (v_player, v_m) returning id into v_pm;
  insert into public.scouting_sessions(player_id, player_match_id, match_id, rubric_version_id, evaluator_user_id, status, started_at)
    values (v_player, v_pm, v_m, v_rv, v_editor, 'draft', now()) returning id into v_s;
  insert into public.videos(match_id, source_name, video_url, video_type) values (v_m, 'zz test', 'https://example.invalid/c', 'full_match') returning id into v_vid;
  insert into public.scouting_session_videos(session_id, match_id, video_id, is_primary) values (v_s, v_m, v_vid, true) returning id into v_sv;

  perform set_config('request.jwt.claims', json_build_object('sub', v_editor, 'role','authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', v_editor::text, true);
  execute 'set local role authenticated';

  -- table constraints
  begin insert into public.criterion_scores(session_id, rubric_version_id, criterion_id, score, applicability) values (v_s, v_rv, v_crit[1], 11, 'scored');
    failed := failed || 'score_11_allowed ; '; exception when check_violation then results := results || 'score_11_blocked:ok '; end;
  begin insert into public.criterion_scores(session_id, rubric_version_id, criterion_id, score, applicability) values (v_s, v_rv, v_crit[1], null, 'scored');
    failed := failed || 'scored_null_allowed ; '; exception when check_violation then results := results || 'scored_without_score_blocked:ok '; end;
  begin insert into public.criterion_scores(session_id, rubric_version_id, criterion_id, score, applicability, rationale) values (v_s, v_rv, v_crit[1], 5, 'not_applicable', 'x');
    failed := failed || 'na_with_score_allowed ; '; exception when check_violation then results := results || 'na_with_score_blocked:ok '; end;
  begin insert into public.observations(player_match_id, minute, category, criterion, observation, evaluation, session_id, rubric_version_id, criterion_id) values (v_pm, 151, 'c', 'c', 'o', 'positive', v_s, v_rv, v_crit[1]);
    failed := failed || 'minute_151_allowed ; '; exception when check_violation then results := results || 'minute_151_blocked:ok '; end;
  begin insert into public.observations(player_match_id, minute, category, criterion, observation, evaluation, session_id, rubric_version_id, criterion_id, video_offset_seconds) values (v_pm, 10, 'c', 'c', 'o', 'positive', v_s, v_rv, v_crit[1], 30);
    failed := failed || 'offset_without_video_allowed ; '; exception when check_violation then results := results || 'offset_without_video_blocked:ok '; end;
  begin insert into public.observations(player_match_id, minute, category, criterion, observation, evaluation, session_id, rubric_version_id, criterion_id, session_video_id, video_offset_seconds) values (v_pm, 10, 'c', 'c', 'o', 'positive', v_s, v_rv, v_crit[1], v_sv, -5);
    failed := failed || 'negative_offset_allowed ; '; exception when check_violation then results := results || 'negative_offset_blocked:ok '; end;

  -- path: draft -> completed directly is blocked
  begin update public.scouting_sessions set status='completed', completed_at=now() where id=v_s;
    failed := failed || 'draft_to_completed_allowed ; '; exception when sqlstate '55000' then results := results || 'draft_to_completed_blocked:ok '; end;
  update public.scouting_sessions set status='in_review' where id=v_s;

  -- completion with nothing saved
  begin update public.scouting_sessions set status='completed', completed_at=now() where id=v_s;
    failed := failed || 'empty_completed ; '; exception when sqlstate '55000' then results := results || 'no_scores_blocked:ok '; end;

  -- save all criteria as not observed with rationale (no scored criterion)
  for i in 1..v_n loop
    insert into public.criterion_scores(session_id, rubric_version_id, criterion_id, score, applicability, rationale) values (v_s, v_rv, v_crit[i], null, 'not_observed', 'no opportunity');
  end loop;
  begin update public.scouting_sessions set status='completed', completed_at=now() where id=v_s;
    failed := failed || 'zero_scored_completed ; '; exception when sqlstate '55000' then results := results || 'zero_scored_blocked:ok '; end;

  -- one criterion missing its row
  delete from public.criterion_scores where session_id=v_s and criterion_id=v_crit[v_n];
  update public.criterion_scores set applicability='scored', score=6 where session_id=v_s and criterion_id=v_crit[1];
  begin update public.scouting_sessions set status='completed', completed_at=now() where id=v_s;
    failed := failed || 'missing_row_completed ; '; exception when sqlstate '55000' then results := results || 'missing_criterion_blocked:ok '; end;
  insert into public.criterion_scores(session_id, rubric_version_id, criterion_id, score, applicability, rationale) values (v_s, v_rv, v_crit[v_n], null, 'not_applicable', 'role does not require');

  -- scored without observation
  begin update public.scouting_sessions set status='completed', completed_at=now() where id=v_s;
    failed := failed || 'scored_without_observation_completed ; '; exception when sqlstate '55000' then results := results || 'scored_without_observation_blocked:ok '; end;
  insert into public.observations(player_match_id, minute, category, criterion, observation, evaluation, session_id, rubric_version_id, criterion_id, session_video_id, video_offset_seconds)
    values (v_pm, 12, 'c', 'c', 'observed behaviour', 'positive', v_s, v_rv, v_crit[1], v_sv, 700);

  -- blank rationale on a scored criterion
  update public.criterion_scores set rationale='   ' where session_id=v_s and criterion_id=v_crit[1];
  begin update public.scouting_sessions set status='completed', completed_at=now() where id=v_s;
    failed := failed || 'blank_rationale_completed ; '; exception when sqlstate '55000' then results := results || 'blank_rationale_blocked:ok '; end;
  update public.criterion_scores set rationale='clear behaviour seen repeatedly' where session_id=v_s and criterion_id=v_crit[1];

  -- score 9 needs a long rationale and two observations
  update public.criterion_scores set score=9 where session_id=v_s and criterion_id=v_crit[1];
  begin update public.scouting_sessions set status='completed', completed_at=now() where id=v_s;
    failed := failed || 'nine_without_support_completed ; '; exception when sqlstate '55000' then results := results || 'score_9_needs_support_blocked:ok '; end;
  update public.criterion_scores set rationale='repeated, high-quality, well-timed behaviour in several different match situations' where session_id=v_s and criterion_id=v_crit[1];
  begin update public.scouting_sessions set status='completed', completed_at=now() where id=v_s;
    failed := failed || 'nine_with_one_observation_completed ; '; exception when sqlstate '55000' then results := results || 'score_9_needs_two_observations_blocked:ok '; end;
  insert into public.observations(player_match_id, minute, category, criterion, observation, evaluation, session_id, rubric_version_id, criterion_id, session_video_id, video_offset_seconds)
    values (v_pm, 55, 'c', 'c', 'second observation', 'positive', v_s, v_rv, v_crit[1], v_sv, 3400);

  -- fully supported completion succeeds, then history is frozen
  begin update public.scouting_sessions set status='completed', completed_at=now() where id=v_s; results := results || 'valid_completion:ok ';
  exception when others then failed := failed || 'valid_completion: '||sqlerrm||' ; '; end;
  begin update public.criterion_scores set score=3 where session_id=v_s and criterion_id=v_crit[1]; failed := failed || 'completed_score_edited ; ';
  exception when others then results := results || 'completed_session_scores_frozen:ok '; end;
  begin update public.scouting_sessions set status='in_review', completed_at=null where id=v_s; results := results || 'reopen_ok:ok ';
  exception when others then failed := failed || 'reopen: '||sqlerrm||' ; '; end;

  execute 'reset role';
  if failed = '' then
    raise exception 'SESSION_COMPLETION_TESTS_PASSED | %', results;
  else
    raise exception 'SESSION_COMPLETION_TESTS_FAILED: % | passed: %', failed, results;
  end if;
end $$;
