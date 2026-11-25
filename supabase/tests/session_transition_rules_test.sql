-- Rolled-back live test for session status transitions (API role = authenticated editor).
-- Always ends with RAISE EXCEPTION 'SESSION_TRANSITION_TESTS_PASSED|FAILED'; nothing persists. Not run in CI.
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
  insert into public.players(full_name) values ('ZZ transition player') returning id into v_player;
  insert into public.matches(match_date) values (current_date) returning id into v_m;
  insert into public.player_matches(player_id, match_id) values (v_player, v_m) returning id into v_pm;
  insert into public.scouting_sessions(player_id, player_match_id, match_id, rubric_version_id, evaluator_user_id, status, started_at)
    values (v_player, v_pm, v_m, v_rv, v_editor, 'draft', now()) returning id into v_s;
  insert into public.videos(match_id, source_name, video_url, video_type) values (v_m, 'zz test', 'https://example.invalid/t', 'full_match') returning id into v_vid;
  insert into public.scouting_session_videos(session_id, match_id, video_id, is_primary) values (v_s, v_m, v_vid, true) returning id into v_sv;

  perform set_config('request.jwt.claims', json_build_object('sub', v_editor, 'role','authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', v_editor::text, true);
  execute 'set local role authenticated';

  begin update public.scouting_sessions set status='locked' where id=v_s;
    failed := failed || 'draft_to_locked_allowed ; '; exception when sqlstate '55000' then results := results || 'draft_to_locked_blocked:ok '; end;
  begin update public.scouting_sessions set status='in_review' where id=v_s;
    failed := failed || 'review_without_scores_allowed ; '; exception when sqlstate '55000' then results := results || 'review_needs_saved_criteria_blocked:ok '; end;
  begin update public.scouting_sessions set private_notes='x' where id=v_s; results := results || 'same_status_edit_ok:ok ';
  exception when others then failed := failed || 'same_status_edit: '||sqlerrm||' ; '; end;

  for i in 1..v_n loop
    insert into public.criterion_scores(session_id, rubric_version_id, criterion_id, score, applicability, rationale) values (v_s, v_rv, v_crit[i], null, 'not_observed', 'no opportunity');
  end loop;
  begin update public.scouting_sessions set status='in_review' where id=v_s; results := results || 'draft_to_review_ok:ok ';
  exception when others then failed := failed || 'draft_to_review: '||sqlerrm||' ; '; end;

  begin update public.scouting_sessions set status='locked' where id=v_s;
    failed := failed || 'review_to_locked_allowed ; '; exception when sqlstate '55000' then results := results || 'review_to_locked_blocked:ok '; end;
  begin update public.scouting_sessions set status='draft' where id=v_s;
    failed := failed || 'review_to_draft_allowed ; '; exception when sqlstate '55000' then results := results || 'review_to_draft_blocked:ok '; end;

  -- completion path still works: one scored criterion with an observation
  update public.criterion_scores set applicability='scored', score=6, rationale='seen clearly' where session_id=v_s and criterion_id=v_crit[1];
  insert into public.observations(player_match_id, minute, category, criterion, observation, evaluation, session_id, rubric_version_id, criterion_id, session_video_id, video_offset_seconds)
    values (v_pm, 12, 'c', 'c', 'observed behaviour', 'positive', v_s, v_rv, v_crit[1], v_sv, 700);
  begin update public.scouting_sessions set status='completed', completed_at=now() where id=v_s; results := results || 'review_to_completed_ok:ok ';
  exception when others then failed := failed || 'review_to_completed: '||sqlerrm||' ; '; end;
  begin update public.scouting_sessions set status='draft', completed_at=null where id=v_s;
    failed := failed || 'completed_to_draft_allowed ; '; exception when others then results := results || 'completed_to_draft_blocked:ok '; end;
  begin update public.scouting_sessions set status='in_review', completed_at=null where id=v_s; results := results || 'reopen_ok:ok ';
  exception when others then failed := failed || 'reopen: '||sqlerrm||' ; '; end;
  begin update public.scouting_sessions set status='completed', completed_at=now() where id=v_s; results := results || 'recomplete_ok:ok ';
  exception when others then failed := failed || 'recomplete: '||sqlerrm||' ; '; end;
  begin update public.scouting_sessions set status='locked' where id=v_s; results := results || 'completed_to_locked_ok:ok ';
  exception when others then failed := failed || 'lock: '||sqlerrm||' ; '; end;
  begin update public.scouting_sessions set status='in_review' where id=v_s;
    failed := failed || 'locked_reopened ; '; exception when others then results := results || 'locked_is_final:ok '; end;

  execute 'reset role';
  if failed = '' then
    raise exception 'SESSION_TRANSITION_TESTS_PASSED | %', results;
  else
    raise exception 'SESSION_TRANSITION_TESTS_FAILED: % | passed: %', failed, results;
  end if;
end $$;
