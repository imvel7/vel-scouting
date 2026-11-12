-- Reuse the established report-bundle workflow and retire the temporary duplicate RPC.
-- The existing function's staff check and RLS policies provide authorization under invoker rights.

alter function public.create_scout_report_bundle(
  uuid, date, text, text, text[], text, text, text, text, boolean, uuid[], jsonb
) security invoker;

revoke all on function public.create_scout_report_bundle(
  uuid, date, text, text, text[], text, text, text, text, boolean, uuid[], jsonb
) from public, anon;
grant execute on function public.create_scout_report_bundle(
  uuid, date, text, text, text[], text, text, text, text, boolean, uuid[], jsonb
) to authenticated;

drop function public.create_multi_match_scout_report(
  uuid, uuid, uuid[], date, numeric, text, text, text[], text, text, text, jsonb
);
