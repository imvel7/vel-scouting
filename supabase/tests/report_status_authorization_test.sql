-- Self-rolling-back test for the report status workflow (migration *_report_status_authorization).
-- Uses real API roles (SET LOCAL ROLE authenticated / anon) and two throw-away users (admin and editor)
-- created inside the transaction. Ends with RAISE EXCEPTION so nothing persists.
do $$
declare
  v_admin uuid := gen_random_uuid(); v_editor uuid := gen_random_uuid();
  v_rv uuid; v_meth text; v_player uuid; v_res jsonb;
  v_m uuid; v_pm uuid; v_s uuid; v_v uuid; v_sessions uuid[]; i int;
  v_rb uuid; v_rn uuid; v_vis int;
  results text := ''; failed text := '';
begin
  select id, methodology_version into v_rv, v_meth from public.rubric_versions where status in ('pilot','active') order by created_at desc limit 1;
  insert into auth.users(id, email) values (v_admin, 'zz-admin@example.invalid'), (v_editor, 'zz-editor@example.invalid');
  insert into public.user_roles(user_id, role) values (v_admin, 'admin'), (v_editor, 'editor');
  insert into public.players(full_name, profile_status) values ('ZZ workflow player', 'published') returning id into v_player;
  v_sessions := '{}';
  for i in 1..3 loop
    insert into public.matches(match_date) values (current_date - i) returning id into v_m;
    insert into public.player_matches(player_id, match_id) values (v_player, v_m) returning id into v_pm;
    insert into public.scouting_sessions(player_id, player_match_id, match_id, rubric_version_id, evaluator_user_id, status, started_at)
      values (v_player, v_pm, v_m, v_rv, v_editor, 'draft', now()) returning id into v_s;
    insert into public.videos(match_id, source_name, video_url, video_type) values (v_m, 'zz test', 'https://example.invalid/w'||i, 'full_match') returning id into v_v;
    insert into public.scouting_session_videos(session_id, match_id, video_id, is_primary) values (v_s, v_m, v_v, true);
    insert into public.criterion_scores(session_id, rubric_version_id, criterion_id, score, applicability)
      select v_s, v_rv, c.id, 6, 'scored' from public.rubric_criteria c where c.rubric_version_id = v_rv;
    update public.scouting_sessions set status='completed', completed_at=now() where id = v_s;
    v_sessions := v_sessions || v_s;
  end loop;

  -- reports are created through the real RPC as the editor (authenticated API role)
  perform set_config('request.jwt.claims', json_build_object('sub', v_editor, 'role','authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', v_editor::text, true);
  execute 'set local role authenticated';
  v_res := public.create_multi_match_scout_report_bundle(v_player, v_rv, current_date, v_meth, null, '{}', null, 'graded', null, null, true, v_sessions, '{}'::jsonb);
  v_rb := (v_res->>'report_id')::uuid;
  v_res := public.create_multi_match_scout_report_bundle(v_player, v_rv, current_date, v_meth, null, '{}', null, 'no grade', null, null, false, v_sessions, '{}'::jsonb);
  v_rn := (v_res->>'report_id')::uuid;
  results := results || 'rpc_as_editor:ok ';

  -- editor: draft -> review ok, review -> draft ok, publish/archive blocked
  begin update public.scout_reports set report_status='review' where id=v_rb; results := results || 'editor_draft_to_review:ok ';
  exception when others then failed := failed || 'editor_draft_to_review: '||sqlerrm||' ; '; end;
  begin update public.scout_reports set report_status='draft' where id=v_rb; update public.scout_reports set report_status='review' where id=v_rb;
    results := results || 'editor_review_to_draft_and_back:ok ';
  exception when others then failed := failed || 'editor_back: '||sqlerrm||' ; '; end;
  begin update public.scout_reports set report_status='published' where id=v_rb; failed := failed || 'editor_published ; ';
  exception when sqlstate '42501' then results := results || 'editor_publish_blocked:ok '; end;
  begin insert into public.scout_reports(player_id, report_date, methodology_version, report_status, created_by) values (v_player, current_date, v_meth, 'published', v_editor);
    failed := failed || 'direct_published_insert_allowed ; ';
  exception when sqlstate '55000' then results := results || 'direct_published_insert_blocked:ok '; end;
  begin insert into public.scout_reports(player_id, report_date, methodology_version, report_status, created_by) values (v_player, current_date, v_meth, 'draft', v_editor);
    failed := failed || 'direct_draft_insert_allowed ; ';
  exception when sqlstate '55000' then results := results || 'direct_draft_insert_blocked:ok '; end;

  -- admin: publish ok; null-grade report cannot be published; archive ok; editor cannot archive
  perform set_config('request.jwt.claims', json_build_object('sub', v_admin, 'role','authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', v_admin::text, true);
  begin update public.scout_reports set report_status='published' where id=v_rb; results := results || 'admin_publish:ok ';
  exception when others then failed := failed || 'admin_publish: '||sqlerrm||' ; '; end;
  begin update public.scout_reports set report_status='review' where id=v_rn; update public.scout_reports set report_status='published' where id=v_rn;
    failed := failed || 'null_grade_published ; ';
  exception when sqlstate '55000' then results := results || 'null_grade_publish_blocked:ok '; end;

  -- anonymous visibility: published visible, draft/review/archived not
  execute 'reset role';
  execute 'set local role anon';
  select count(*) into v_vis from public.scout_reports where player_id = v_player;
  if v_vis = 1 then results := results || 'anon_sees_only_published:ok '; else failed := failed || 'anon_sees_'||v_vis||'_reports ; '; end if;
  execute 'reset role';
  execute 'set local role authenticated';

  -- editor cannot archive; admin can; archived no longer visible to anon
  perform set_config('request.jwt.claims', json_build_object('sub', v_editor, 'role','authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', v_editor::text, true);
  begin update public.scout_reports set report_status='archived' where id=v_rb; failed := failed || 'editor_archived ; ';
  exception when sqlstate '42501' then results := results || 'editor_archive_blocked:ok '; end;
  perform set_config('request.jwt.claims', json_build_object('sub', v_admin, 'role','authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', v_admin::text, true);
  begin update public.scout_reports set report_status='archived' where id=v_rb; results := results || 'admin_archive:ok ';
  exception when others then failed := failed || 'admin_archive: '||sqlerrm||' ; '; end;
  execute 'reset role';
  execute 'set local role anon';
  select count(*) into v_vis from public.scout_reports where player_id = v_player;
  if v_vis = 0 then results := results || 'anon_sees_no_archived:ok '; else failed := failed || 'anon_still_sees_'||v_vis||' ; '; end if;
  execute 'reset role';
  execute 'set local role authenticated';

  -- history protection from PR #80 still holds for real API roles
  begin update public.scout_reports set general_rating=9 where id=v_rb; failed := failed || 'rating_changed ; ';
  exception when sqlstate '55000' then results := results || 'rating_locked_for_api_role:ok '; end;
  begin update public.report_versions set report_snapshot='{}'::jsonb where report_id=v_rb; failed := failed || 'version_updated ; ';
  exception when sqlstate '55000' then results := results || 'version_append_only_for_api_role:ok '; end;
  begin update public.scout_reports set strengths='late edit' where id=v_rb; failed := failed || 'archived_content_edited ; ';
  exception when sqlstate '55000' then results := results || 'archived_content_frozen:ok '; end;
  begin update public.scout_reports set report_status='published' where id=v_rb; failed := failed || 'archived_reopened ; ';
  exception when sqlstate '55000' then results := results || 'archived_final:ok '; end;

  execute 'reset role';
  if failed = '' then
    raise exception 'REPORT_WORKFLOW_TESTS_PASSED | %', results;
  else
    raise exception 'REPORT_WORKFLOW_TESTS_FAILED: % | passed: %', failed, results;
  end if;
end $$;
