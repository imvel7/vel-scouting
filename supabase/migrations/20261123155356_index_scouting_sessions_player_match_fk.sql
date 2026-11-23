-- The earlier migration skipped this one: an index named scouting_sessions_player_match_idx (player_match_id only) already existed.
-- Rollback: DROP INDEX IF EXISTS public.scouting_sessions_player_match_fk_idx;
create index if not exists scouting_sessions_player_match_fk_idx on public.scouting_sessions (player_match_id, player_id, match_id);
