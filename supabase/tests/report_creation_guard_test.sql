-- Self-rolling-back test for *_report_creation_only_via_rpc: reports exist only through the report function.
-- Needs the migration applied. Ends with RAISE EXCEPTION so nothing persists.
do $$
declare
  v_admin uuid := gen_random_uuid(); v_editor uuid := gen_random_uuid();
  v_rv uuid; v_meth text; v_player uuid; v_res jsonb;
  v_m uuid; v_pm uuid; v_s uuid; v_v uuid; v_sessions uuid[]; i int;
  v_rb uuid; v_rn uuid; v_flag text;
  results text := ''; failed text := '';
begin
  select id, methodology_version into v_rv, v_meth from public.rubric_versions where status in ('pilot','active') order by created_at desc limit 1;
  insert into auth.users(id, email) values (v_admin, 'zz-admin@example.invalid'), (v_editor, 'zz-editor@example.invalid');
  insert into public.user_roles(user_id, role) values (v_admin, 'admin'), (v_editor, 'editor');
  insert into public.players(full_name, profile_status) values ('ZZ guard player', 'published') returning id into v_player;
  v_sessions := '{}';
  for i in 1..3 loop
    insert into public.matches(match_date) values (current_date - i) returning id into v_m;
    insert into public.player_matches(player_id, match_id) values (v_player, v_m) returning id into v_pm;
    insert into public.scouting_sessions(player_id, player_match_id, match_id, rubric_version_id, evaluator_user_id, status, started_at)
      values (v_player, v_pm, v_m, v_rv, v_editor, 'draft', now()) returning id into v_s;
    insert into public.videos(match_id, source_name, video_url, video_type) values (v_m, 'zz test', 'https://example.invalid/g'||i, 'full_match') returning id into v_v;
    insert into public.scouting_session_videos(session_id, match_id, video_id, is_primary) values (v_s, v_m, v_v, true);
    insert into public.criterion_scores(session_id, rubric_version_id, criterion_id, score, applicability)
      select v_s, v_rv, c.id, 6, 'scored' from public.rubric_criteria c where c.rubric_version_id = v_rv;
    update public.scouting_sessions set status='completed', completed_at=now() where id = v_s;
    v_sessions := v_sessions || v_s;
  end loop;

  perform set_config('request.jwt.claims', json_build_object('sub', v_editor, 'role','authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', v_editor::text, true);
  execute 'set local role authenticated';
  v_res := public.create_multi_match_scout_report_bundle(v_player, v_rv, current_date, v_meth, null, '{}', null, 'graded', null, null, true, v_sessions, '{}'::jsonb);
  v_rb := (v_res->>'report_id')::uuid;
  v_res := public.create_multi_match_scout_report_bundle(v_player, v_rv, current_date, v_meth, null, '{}', null, 'no grade', null, null, false, v_sessions, '{}'::jsonb);
  v_rn := (v_res->>'report_id')::uuid;
  results := results || 'rpc_as_editor:ok ';
  v_flag := coalesce(current_setting('vel.report_rpc', true), '');
  if v_flag = 'off' then results := results || 'flag_reset_after_rpc:ok '; else failed := failed || 'flag_not_reset('||v_flag||') ; '; end if;
  if (select evidence_grade from public.scout_reports where id = v_rb) = 'B' and (select evidence_grade from public.scout_reports where id = v_rn) is null then results := results || 'rpc_grades_computed:ok '; else failed := failed || 'rpc_grades_wrong ; '; end if;

  begin insert into public.scout_reports(player_id, report_date, methodology_version, evidence_grade, general_rating, report_status, created_by) values (v_player, current_date, v_meth, 'A', 9.5, 'draft', v_editor);
    failed := failed || 'forged_grade_insert_allowed ; ';
  exception when sqlstate '55000' then results := results || 'forged_grade_insert_blocked:ok '; end;
  begin insert into public.scout_reports(player_id, report_date, methodology_version, report_status, created_by) values (v_player, current_date, v_meth, 'published', v_editor);
    failed := failed || 'direct_published_insert_allowed ; ';
  exception when sqlstate '55000' then results := results || 'direct_published_insert_blocked:ok '; end;

  begin update public.scout_reports set report_status='review' where id=v_rb; results := results || 'editor_draft_to_review:ok ';
  exception when others then failed := failed || 'editor_draft_to_review: '||sqlerrm||' ; '; end;
  begin update public.scout_reports set report_status='published' where id=v_rb; failed := failed || 'editor_published ; ';
  exception when sqlstate '42501' then results := results || 'editor_publish_blocked:ok '; end;

  perform set_config('request.jwt.claims', json_build_object('sub', v_admin, 'role','authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', v_admin::text, true);
  begin update public.scout_reports set report_status='published' where id=v_rb; results := results || 'admin_publish:ok ';
  exception when others then failed := failed || 'admin_publish: '||sqlerrm||' ; '; end;
  begin update public.scout_reports set report_status='review' where id=v_rn; update public.scout_reports set report_status='published' where id=v_rn;
    failed := failed || 'null_grade_published ; ';
  exception when sqlstate '55000' then results := results || 'null_grade_publish_blocked:ok '; end;
  begin update public.scout_reports set report_status='archived' where id=v_rb; results := results || 'admin_archive:ok ';
  exception when others then failed := failed || 'admin_archive: '||sqlerrm||' ; '; end;

  execute 'reset role';
  execute 'set local role anon';
  begin insert into public.scout_reports(player_id, report_date, methodology_version, report_status) values (v_player, current_date, v_meth, 'draft');
    failed := failed || 'anon_insert_allowed ; ';
  exception when others then results := results || 'anon_insert_blocked:ok '; end;
  execute 'reset role';
  if failed = '' then
    raise exception 'REPORT_CREATION_GUARD_TESTS_PASSED | %', results;
  else
    raise exception 'REPORT_CREATION_GUARD_TESTS_FAILED: % | passed: %', failed, results;
  end if;
end $$;
