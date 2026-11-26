alter table public.clubs enable row level security;
alter table public.competitions enable row level security;
alter table public.criterion_scores enable row level security;
alter table public.matches enable row level security;
alter table public.observations enable row level security;
alter table public.player_matches enable row level security;
alter table public.players enable row level security;
alter table public.report_versions enable row level security;
alter table public.rubric_categories enable row level security;
alter table public.rubric_criteria enable row level security;
alter table public.rubric_versions enable row level security;
alter table public.scout_report_sessions enable row level security;
alter table public.scout_reports enable row level security;
alter table public.scouting_session_videos enable row level security;
alter table public.scouting_sessions enable row level security;
alter table public.seasons enable row level security;
alter table public.user_roles enable row level security;
alter table public.video_access_checks enable row level security;
alter table public.video_rights_assessments enable row level security;
alter table public.video_sources enable row level security;
alter table public.videos enable row level security;

create policy vel_public_read_linked_clubs on public.clubs as PERMISSIVE for SELECT to anon, authenticated using ((EXISTS ( SELECT 1 FROM players p WHERE ((p.current_club_id = clubs.id) AND (p.profile_status = 'published'::text)))));
create policy vel_public_read_published_players on public.players as PERMISSIVE for SELECT to anon, authenticated using ((profile_status = 'published'::text));
create policy vel_public_read_published_reports on public.scout_reports as PERMISSIVE for SELECT to anon, authenticated using (((report_status = 'published'::text) AND (EXISTS ( SELECT 1 FROM players p WHERE ((p.id = scout_reports.player_id) AND (p.profile_status = 'published'::text))))));
create policy vel_admin_manage_roles on public.user_roles as PERMISSIVE for ALL to authenticated using (( SELECT private.is_vel_admin() AS is_vel_admin)) with check (( SELECT private.is_vel_admin() AS is_vel_admin));
create policy vel_user_read_own_role on public.user_roles as PERMISSIVE for SELECT to authenticated using ((user_id = ( SELECT auth.uid() AS uid)));
create policy vel_staff_insert_video_rights_assessments on public.video_rights_assessments as PERMISSIVE for INSERT to authenticated with check ((( SELECT private.is_vel_staff() AS is_vel_staff) AND ((checked_by IS NULL) OR (checked_by = ( SELECT auth.uid() AS uid)))));
create policy vel_staff_read_video_rights_assessments on public.video_rights_assessments as PERMISSIVE for SELECT to authenticated using (( SELECT private.is_vel_staff() AS is_vel_staff));

do $$
declare t text;
begin
  foreach t in array array['clubs','competitions','criterion_scores','matches','observations','player_matches','players','report_versions','rubric_categories','rubric_criteria','rubric_versions','scout_report_sessions','scout_reports','scouting_session_videos','scouting_sessions','seasons','video_access_checks','video_sources','videos']
  loop
    execute format('create policy %I on public.%I as permissive for all to authenticated using ((select private.is_vel_staff())) with check ((select private.is_vel_staff()))', 'vel_staff_manage_'||t, t);
  end loop;
end $$;

grant DELETE, INSERT, SELECT, UPDATE on public.clubs to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.competitions to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.criterion_scores to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.matches to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.observations to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.player_matches to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.players to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.report_versions to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.rubric_categories to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.rubric_criteria to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.rubric_versions to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.scout_report_sessions to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.scout_reports to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.scouting_session_videos to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.scouting_sessions to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.seasons to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.user_roles to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.video_access_checks to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.video_sources to authenticated;
grant DELETE, INSERT, SELECT, UPDATE on public.videos to authenticated;
grant INSERT, SELECT on public.video_rights_assessments to authenticated;
grant SELECT on public.clubs to anon;
grant select (id, full_name, nationality, current_club_id, main_position, secondary_position, preferred_foot, height_cm, profile_status, created_at, updated_at) on public.players to anon;
grant select (id, player_id, report_date, methodology_version, evidence_grade, general_rating, main_role, alternative_roles, strengths, development_areas, final_verdict, report_status, created_at, updated_at) on public.scout_reports to anon;

grant usage on schema private to authenticated;
