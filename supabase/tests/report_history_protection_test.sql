-- Self-rolling-back test for supabase/migrations/*_protect_report_history.sql.
-- Run against a database where the migration is applied (or run the migration first in the same transaction).
-- It creates throw-away rows, checks every guard, and always ends with RAISE EXCEPTION so nothing persists:
-- the message starts with REPORT_HISTORY_TESTS_PASSED or lists the failed checks.
do $$
declare
  v_user uuid; v_rv uuid; v_meth text; v_player uuid;
  v_m uuid; v_pm uuid; v_s uuid; v_v uuid; v_sessions uuid[]; i int;
  v_r1 uuid; v_r2 uuid; v_r3 uuid; v_res jsonb;
  results text := ''; failed text := '';
  v_ok boolean; v_note text;

begin
  select user_id into v_user from public.user_roles where role in ('admin','editor') limit 1;
  select id, methodology_version into v_rv, v_meth from public.rubric_versions where status in ('pilot','active') order by created_at desc limit 1;
  perform set_config('request.jwt.claims', json_build_object('sub', v_user, 'role','authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', v_user::text, true);
  insert into public.players(full_name) values ('ZZ history test player') returning id into v_player;
  v_sessions := '{}';
  for i in 1..3 loop
    insert into public.matches(match_date) values (current_date - i) returning id into v_m;
    insert into public.player_matches(player_id, match_id) values (v_player, v_m) returning id into v_pm;
    insert into public.scouting_sessions(player_id, player_match_id, match_id, rubric_version_id, status, started_at)
      values (v_player, v_pm, v_m, v_rv, 'draft', now()) returning id into v_s;
    insert into public.videos(match_id, source_name, video_url, video_type) values (v_m, 'zz test', 'https://example.invalid/h'||i, 'full_match') returning id into v_v;
    insert into public.scouting_session_videos(session_id, match_id, video_id, is_primary) values (v_s, v_m, v_v, true);
    insert into public.criterion_scores(session_id, rubric_version_id, criterion_id, score, applicability)
      select v_s, v_rv, c.id, 6, 'scored' from public.rubric_criteria c where c.rubric_version_id = v_rv;
    update public.scouting_sessions set status='completed', completed_at=now() where id = v_s;
    v_sessions := v_sessions || v_s;
  end loop;
  v_res := public.create_multi_match_scout_report_bundle(v_player, v_rv, current_date, v_meth, null, '{}', null, 'draft strengths', null, null, true, v_sessions, '{}'::jsonb);
  v_r1 := (v_res->>'report_id')::uuid;
  v_res := public.create_multi_match_scout_report_bundle(v_player, v_rv, current_date, v_meth, null, '{}', null, 'second', null, null, true, v_sessions, '{}'::jsonb);
  v_r2 := (v_res->>'report_id')::uuid;
  v_res := public.create_multi_match_scout_report_bundle(v_player, v_rv, current_date, v_meth, null, '{}', null, 'third', null, null, true, v_sessions, '{}'::jsonb);
  v_r3 := (v_res->>'report_id')::uuid;

  -- helper pattern: each check runs in its own sub-block; "expect fail" checks must raise errcode 55000.
  -- 1 draft content editable
  begin update public.scout_reports set strengths='edited' where id=v_r1; results := results || 'draft_content_editable:ok' || ' ';
  exception when others then failed := failed || 'draft_content_editable: '||sqlerrm || ' ; '; end;
  -- 2 computed fields immutable
  begin update public.scout_reports set evidence_grade='A' where id=v_r1; failed := failed || 'evidence_grade_changed' || ' ; ';
  exception when sqlstate '55000' then results := results || 'evidence_grade_locked:ok' || ' '; end;
  begin update public.scout_reports set general_rating=9 where id=v_r1; failed := failed || 'general_rating_changed' || ' ; ';
  exception when sqlstate '55000' then results := results || 'general_rating_locked:ok' || ' '; end;
  begin update public.scout_reports set methodology_version='X' where id=v_r1; failed := failed || 'methodology_changed' || ' ; ';
  exception when sqlstate '55000' then results := results || 'methodology_locked:ok' || ' '; end;
  begin update public.scout_reports set player_id=gen_random_uuid() where id=v_r1; failed := failed || 'player_changed' || ' ; ';
  exception when sqlstate '55000' then results := results || 'player_locked:ok' || ' '; when others then results := results || 'player_locked_by_fk:ok' || ' '; end;
  -- 3 versions append-only
  begin update public.report_versions set report_snapshot='{}'::jsonb where report_id=v_r1; failed := failed || 'version_updated' || ' ; ';
  exception when sqlstate '55000' then results := results || 'version_update_blocked:ok' || ' '; end;
  begin insert into public.report_versions(report_id, version_number, report_snapshot) values (v_r1, 2, '{"note":"revision"}'::jsonb);
    results := results || 'version_append_ok:ok' || ' ';
  exception when others then failed := failed || 'version_append: '||sqlerrm || ' ; '; end;
  -- 4 status path
  begin update public.scout_reports set report_status='published' where id=v_r1; failed := failed || 'draft_to_published_allowed' || ' ; ';
  exception when sqlstate '55000' then results := results || 'draft_to_published_blocked:ok' || ' '; end;
  begin update public.scout_reports set report_status='review' where id=v_r1; update public.scout_reports set report_status='published' where id=v_r1;
    results := results || 'review_then_published:ok' || ' ';
  exception when others then failed := failed || 'status_path: '||sqlerrm || ' ; '; end;
  -- 5 published content frozen, status limited
  begin update public.scout_reports set strengths='after publish' where id=v_r1; failed := failed || 'published_content_edited' || ' ; ';
  exception when sqlstate '55000' then results := results || 'published_content_frozen:ok' || ' '; end;
  begin update public.scout_reports set report_status='draft' where id=v_r1; failed := failed || 'published_to_draft_allowed' || ' ; ';
  exception when sqlstate '55000' then results := results || 'published_to_draft_blocked:ok' || ' '; end;
  -- 6 direct deletes blocked for non-drafts
  begin delete from public.scout_reports where id=v_r1; failed := failed || 'published_report_deleted' || ' ; ';
  exception when sqlstate '55000' then results := results || 'published_delete_blocked:ok' || ' '; end;
  begin delete from public.report_versions where report_id=v_r1; failed := failed || 'published_versions_deleted' || ' ; ';
  exception when sqlstate '55000' then results := results || 'published_versions_delete_blocked:ok' || ' '; end;
  begin delete from public.scout_report_sessions where report_id=v_r1; failed := failed || 'published_links_deleted' || ' ; ';
  exception when sqlstate '55000' then results := results || 'published_links_delete_blocked:ok' || ' '; end;
  begin insert into public.scout_report_sessions(report_id, session_id, player_id) values (v_r1, v_sessions[1], v_player);
    failed := failed || 'published_link_inserted' || ' ; ';
  exception when sqlstate '55000' then results := results || 'published_link_insert_blocked:ok' || ' '; when unique_violation then results := results || 'published_link_insert_blocked_by_unique:ok' || ' '; end;
  -- 7 archive allowed, archived final
  begin update public.scout_reports set report_status='archived' where id=v_r1; results := results || 'published_to_archived:ok' || ' ';
  exception when others then failed := failed || 'archive: '||sqlerrm || ' ; '; end;
  begin update public.scout_reports set report_status='published' where id=v_r1; failed := failed || 'archived_reopened' || ' ; ';
  exception when sqlstate '55000' then results := results || 'archived_final:ok' || ' '; end;
  -- 8 draft delete allowed (cascade of versions and links)
  begin delete from public.scout_reports where id=v_r3; results := results || 'draft_delete_allowed:ok' || ' ';
  exception when others then failed := failed || 'draft_delete: '||sqlerrm || ' ; '; end;
  -- 9 report-session link update blocked
  begin update public.scout_report_sessions set contribution_note='x' where report_id=v_r2; failed := failed || 'link_updated' || ' ; ';
  exception when sqlstate '55000' then results := results || 'link_update_blocked:ok' || ' '; end;
  -- 10 erasure path (informational): deleting the player
  v_note := 'erasure_probe: ';
  begin delete from public.players where id=v_player; v_note := v_note || 'player_delete_succeeded';
  exception when others then v_note := v_note || 'player_delete_blocked_by: ' || sqlerrm; end;

  if failed = '' then
    raise exception 'REPORT_HISTORY_TESTS_PASSED | % | %', results, v_note;
  else
    raise exception 'REPORT_HISTORY_TESTS_FAILED: % | passed: % | %', failed, results, v_note;
  end if;
end $$;
