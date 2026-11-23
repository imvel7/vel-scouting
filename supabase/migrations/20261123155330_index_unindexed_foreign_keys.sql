-- Covering indexes for foreign keys without a usable leading index (Supabase performance advisor 0001).
-- Additive only; tables are small. Rollback: DROP INDEX IF EXISTS public.<name>; for each index below.
create index if not exists criterion_scores_criterion_version_idx on public.criterion_scores (criterion_id, rubric_version_id);
create index if not exists criterion_scores_session_version_idx on public.criterion_scores (session_id, rubric_version_id);
create index if not exists matches_away_club_id_idx on public.matches (away_club_id);
create index if not exists matches_competition_id_idx on public.matches (competition_id);
create index if not exists matches_home_club_id_idx on public.matches (home_club_id);
create index if not exists matches_season_id_idx on public.matches (season_id);
create index if not exists observations_criterion_rubric_idx on public.observations (criterion_id, rubric_version_id);
create index if not exists observations_session_player_match_idx on public.observations (session_id, player_match_id);
create index if not exists observations_session_rubric_idx on public.observations (session_id, rubric_version_id);
create index if not exists observations_session_video_idx on public.observations (session_video_id, session_id);
create index if not exists player_matches_club_id_idx on public.player_matches (club_id);
create index if not exists players_current_club_id_idx on public.players (current_club_id);
create index if not exists rubric_criteria_category_version_idx on public.rubric_criteria (rubric_category_id, rubric_version_id);
create index if not exists rubric_versions_created_by_idx on public.rubric_versions (created_by);
create index if not exists scout_report_sessions_report_player_idx on public.scout_report_sessions (report_id, player_id);
create index if not exists scout_report_sessions_session_player_idx on public.scout_report_sessions (session_id, player_id);
create index if not exists scout_reports_created_by_idx on public.scout_reports (created_by);
create index if not exists scouting_session_videos_session_match_idx on public.scouting_session_videos (session_id, match_id);
create index if not exists scouting_session_videos_video_match_idx on public.scouting_session_videos (video_id, match_id);
create index if not exists scouting_sessions_player_match_idx on public.scouting_sessions (player_match_id, player_id, match_id);
create index if not exists scouting_sessions_rubric_version_id_idx on public.scouting_sessions (rubric_version_id);
create index if not exists video_access_checks_checked_by_idx on public.video_access_checks (checked_by);
create index if not exists videos_match_id_idx on public.videos (match_id);
