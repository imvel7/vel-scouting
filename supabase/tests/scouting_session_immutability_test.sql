-- Self-rolling-back test for migration 20261121080628_enforce_scouting_session_immutability.
-- Run read-only-safe against the live project: it uses an existing DRAFT scouting session inside a
-- DO block that always ends with RAISE EXCEPTION, so every change is rolled back.
-- Expected result: an error whose message starts with "TEST_RESULT (rolled back):" and contains
-- 15 "=ok" entries and NO "FAIL" entry. "TEST_SKIPPED" means there was no draft session to test with.
DO $test$
DECLARE
  s record;
  crit uuid;
  crit2 uuid;
  vid uuid;
  log text := '';
BEGIN
  SELECT * INTO s FROM public.scouting_sessions WHERE status = 'draft' LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'TEST_SKIPPED: no draft session found'; END IF;
  SELECT id INTO crit FROM public.rubric_criteria WHERE rubric_version_id = s.rubric_version_id ORDER BY id LIMIT 1;
  SELECT id INTO crit2 FROM public.rubric_criteria WHERE rubric_version_id = s.rubric_version_id ORDER BY id OFFSET 1 LIMIT 1;
  SELECT id INTO vid FROM public.scouting_session_videos WHERE session_id = s.id LIMIT 1;

  INSERT INTO public.criterion_scores(session_id, rubric_version_id, criterion_id, applicability, rationale)
    VALUES (s.id, s.rubric_version_id, crit, 'not_observed', 't');
  INSERT INTO public.observations(player_match_id, minute, category, criterion, observation, session_id, rubric_version_id, criterion_id)
    VALUES (s.player_match_id, 10, 'test', 'test', 'test obs', s.id, s.rubric_version_id, crit);
  UPDATE public.scouting_session_videos SET usage_note = 'draft-ok' WHERE id = vid;
  UPDATE public.scouting_sessions SET private_notes = 'draft-ok' WHERE id = s.id;
  log := log || 'draft_writes_allowed=ok; ';

  UPDATE public.scouting_sessions SET status = 'in_review' WHERE id = s.id;
  UPDATE public.scouting_sessions SET status = 'completed', completed_at = now() WHERE id = s.id;

  BEGIN UPDATE public.criterion_scores SET rationale = 'x' WHERE session_id = s.id; log := log || 'FAIL score_update_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'score_update_blocked=ok; '; ELSE log := log || 'FAIL score_update_other_error:' || SQLERRM || '; '; END IF; END;
  BEGIN DELETE FROM public.criterion_scores WHERE session_id = s.id; log := log || 'FAIL score_delete_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'score_delete_blocked=ok; '; ELSE log := log || 'FAIL score_delete_other_error:' || SQLERRM || '; '; END IF; END;
  BEGIN INSERT INTO public.criterion_scores(session_id, rubric_version_id, criterion_id, applicability) VALUES (s.id, s.rubric_version_id, crit2, 'not_observed'); log := log || 'FAIL score_insert_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'score_insert_blocked=ok; '; ELSE log := log || 'FAIL score_insert_other_error:' || SQLERRM || '; '; END IF; END;
  BEGIN UPDATE public.observations SET observation = 'x' WHERE session_id = s.id; log := log || 'FAIL obs_update_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'obs_update_blocked=ok; '; ELSE log := log || 'FAIL obs_update_other_error:' || SQLERRM || '; '; END IF; END;
  BEGIN DELETE FROM public.observations WHERE session_id = s.id; log := log || 'FAIL obs_delete_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'obs_delete_blocked=ok; '; ELSE log := log || 'FAIL obs_delete_other_error:' || SQLERRM || '; '; END IF; END;
  BEGIN INSERT INTO public.observations(player_match_id, minute, category, criterion, observation, session_id, rubric_version_id, criterion_id) VALUES (s.player_match_id, 11, 'test', 'test', 'late obs', s.id, s.rubric_version_id, crit); log := log || 'FAIL obs_insert_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'obs_insert_blocked=ok; '; ELSE log := log || 'FAIL obs_insert_other_error:' || SQLERRM || '; '; END IF; END;
  BEGIN UPDATE public.scouting_session_videos SET usage_note = 'x' WHERE id = vid; log := log || 'FAIL video_update_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'video_update_blocked=ok; '; ELSE log := log || 'FAIL video_update_other_error:' || SQLERRM || '; '; END IF; END;
  BEGIN UPDATE public.scouting_sessions SET private_notes = 'x' WHERE id = s.id; log := log || 'FAIL session_edit_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'session_edit_blocked=ok; '; ELSE log := log || 'FAIL session_edit_other_error:' || SQLERRM || '; '; END IF; END;
  BEGIN UPDATE public.scouting_sessions SET status = 'draft' WHERE id = s.id; log := log || 'FAIL session_to_draft_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'session_to_draft_blocked=ok; '; ELSE log := log || 'FAIL session_to_draft_other_error:' || SQLERRM || '; '; END IF; END;
  BEGIN DELETE FROM public.scouting_sessions WHERE id = s.id; log := log || 'FAIL session_delete_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'session_delete_blocked=ok; '; ELSE log := log || 'FAIL session_delete_other_error:' || SQLERRM || '; '; END IF; END;

  UPDATE public.scouting_sessions SET status = 'in_review', completed_at = NULL WHERE id = s.id;
  UPDATE public.criterion_scores SET rationale = 'reopened-ok' WHERE session_id = s.id;
  log := log || 'reopen_and_edit_allowed=ok; ';

  UPDATE public.scouting_sessions SET status = 'completed', completed_at = now() WHERE id = s.id;
  UPDATE public.scouting_sessions SET status = 'locked' WHERE id = s.id;
  log := log || 'complete_then_lock_allowed=ok; ';

  BEGIN UPDATE public.scouting_sessions SET status = 'in_review' WHERE id = s.id; log := log || 'FAIL locked_reopen_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'locked_reopen_blocked=ok; '; ELSE log := log || 'FAIL locked_reopen_other_error:' || SQLERRM || '; '; END IF; END;
  BEGIN UPDATE public.criterion_scores SET rationale = 'x' WHERE session_id = s.id; log := log || 'FAIL locked_score_update_allowed; ';
  EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE '%read-only%' THEN log := log || 'locked_score_update_blocked=ok; '; ELSE log := log || 'FAIL locked_score_update_other_error:' || SQLERRM || '; '; END IF; END;

  RAISE EXCEPTION 'TEST_RESULT (rolled back): %', log;
END;
$test$;
