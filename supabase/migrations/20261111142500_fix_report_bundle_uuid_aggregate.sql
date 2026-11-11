-- PostgreSQL has no min(uuid) aggregate; cast the UUID to text for the single-version MIN.

do $migration$
declare
  v_definition text;
begin
  select pg_get_functiondef(
    'public.create_scout_report_bundle(uuid, date, text, text, text[], text, text, text, text, boolean, uuid[], jsonb)'::regprocedure
  ) into v_definition;

  if position('min(s.rubric_version_id)' in v_definition)=0 then
    raise exception 'Expected UUID MIN expression was not found; aborting migration.';
  end if;

  v_definition := replace(
    v_definition,
    'min(s.rubric_version_id)',
    'min(s.rubric_version_id::text)::uuid'
  );

  execute v_definition;
end;
$migration$;
