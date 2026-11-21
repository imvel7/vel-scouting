-- Applied to the live project as migration 20261121080628 (dry-run verified, then applied, on 2026-11-21).
-- Vel Scouting: database-level immutability for completed/locked scouting sessions.
--
-- Until now the completed/locked lock lived only in admin.html. Staff could still change a
-- completed or locked session, its criterion scores, observations and video links directly
-- through the Data API. These triggers enforce the lock in the database.
--
-- Rules:
--   * A locked session cannot be updated or deleted.
--   * A completed session cannot be deleted. It can only move to in_review (reopen; only
--     status and completed_at may change) or to locked (only status may change).
--   * criterion_scores, observations and scouting_session_videos of a completed or locked
--     session cannot be inserted, updated or deleted. Reopen the session to in_review first.
--   * Rows with a NULL session_id (legacy observations) are not affected.
--
-- Functions are SECURITY INVOKER with an empty search_path, live in the private schema and
-- are not executable by API roles. Existing migrations are not modified.

CREATE OR REPLACE FUNCTION private.guard_scouting_session_changes()
RETURNS trigger LANGUAGE plpgsql SET search_path = '' AS $fn$
DECLARE
  v_old jsonb;
  v_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status IN ('completed', 'locked') THEN
      RAISE EXCEPTION 'Scouting session % is % and read-only; DELETE is not allowed.', OLD.id, OLD.status
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
  END IF;

  IF OLD.status = 'locked' THEN
    RAISE EXCEPTION 'Scouting session % is locked and read-only; UPDATE is not allowed.', OLD.id
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;

  IF OLD.status = 'completed' THEN
    v_old := to_jsonb(OLD) - 'updated_at';
    v_new := to_jsonb(NEW) - 'updated_at';

    IF NEW.status = 'in_review' THEN
      IF (v_old - 'status' - 'completed_at') IS DISTINCT FROM (v_new - 'status' - 'completed_at') THEN
        RAISE EXCEPTION 'Scouting session % is completed and read-only; reopening may only change status and completed_at.', OLD.id
          USING ERRCODE = 'integrity_constraint_violation';
      END IF;
    ELSIF NEW.status = 'locked' THEN
      IF (v_old - 'status') IS DISTINCT FROM (v_new - 'status') THEN
        RAISE EXCEPTION 'Scouting session % is completed and read-only; locking may only change status.', OLD.id
          USING ERRCODE = 'integrity_constraint_violation';
      END IF;
    ELSE
      RAISE EXCEPTION 'Scouting session % is completed and read-only; it can only move to in_review or locked.', OLD.id
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
  END IF;

  RETURN NEW;
END;
$fn$;

CREATE OR REPLACE FUNCTION private.guard_scouting_session_children()
RETURNS trigger LANGUAGE plpgsql SET search_path = '' AS $fn$
DECLARE
  v_ids uuid[];
  v_id uuid;
  v_status text;
BEGIN
  IF TG_OP = 'INSERT' THEN
    v_ids := ARRAY[NEW.session_id];
  ELSIF TG_OP = 'DELETE' THEN
    v_ids := ARRAY[OLD.session_id];
  ELSE
    v_ids := ARRAY[OLD.session_id, NEW.session_id];
  END IF;

  FOREACH v_id IN ARRAY v_ids LOOP
    CONTINUE WHEN v_id IS NULL;
    SELECT s.status INTO v_status FROM public.scouting_sessions s WHERE s.id = v_id FOR SHARE;
    IF v_status IN ('completed', 'locked') THEN
      RAISE EXCEPTION 'Scouting session % is % and read-only; % on % is not allowed. Reopen the session to in_review first.', v_id, v_status, TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
  END LOOP;

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$fn$;

REVOKE ALL ON FUNCTION private.guard_scouting_session_changes() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION private.guard_scouting_session_children() FROM PUBLIC, anon, authenticated;

CREATE TRIGGER scouting_sessions_guard_immutable
  BEFORE UPDATE OR DELETE ON public.scouting_sessions
  FOR EACH ROW EXECUTE FUNCTION private.guard_scouting_session_changes();
CREATE TRIGGER criterion_scores_guard_session_lock
  BEFORE INSERT OR UPDATE OR DELETE ON public.criterion_scores
  FOR EACH ROW EXECUTE FUNCTION private.guard_scouting_session_children();
CREATE TRIGGER observations_guard_session_lock
  BEFORE INSERT OR UPDATE OR DELETE ON public.observations
  FOR EACH ROW EXECUTE FUNCTION private.guard_scouting_session_children();
CREATE TRIGGER scouting_session_videos_guard_session_lock
  BEFORE INSERT OR UPDATE OR DELETE ON public.scouting_session_videos
  FOR EACH ROW EXECUTE FUNCTION private.guard_scouting_session_children();

-- Rollback:
-- DROP TRIGGER scouting_sessions_guard_immutable ON public.scouting_sessions;
-- DROP TRIGGER criterion_scores_guard_session_lock ON public.criterion_scores;
-- DROP TRIGGER observations_guard_session_lock ON public.observations;
-- DROP TRIGGER scouting_session_videos_guard_session_lock ON public.scouting_session_videos;
-- DROP FUNCTION private.guard_scouting_session_changes();
-- DROP FUNCTION private.guard_scouting_session_children();
