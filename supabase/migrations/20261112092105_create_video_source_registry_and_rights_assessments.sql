-- Vel Scout: reusable source registry and purpose-specific video rights.
-- Existing video rows and legacy rights_status values are preserved.

create table public.video_sources (
  id uuid primary key default gen_random_uuid(),
  source_key text not null unique,
  display_name text not null,
  operator_name text,
  source_type text not null
    check (source_type in (
      'official_archive',
      'official_channel',
      'discovery_index',
      'licensed_provider',
      'research_dataset',
      'other'
    )),
  canonical_url text not null,
  terms_url text,
  officiality_status text not null default 'unknown'
    check (officiality_status in ('official', 'third_party_index', 'unknown')),
  discovery_method text not null default 'manual'
    check (discovery_method in ('manual', 'permitted_api', 'partner_feed', 'other')),
  coverage_notes text,
  review_status text not null default 'candidate'
    check (review_status in ('candidate', 'reviewed', 'inactive')),
  terms_last_checked_at timestamptz,
  created_at timestamptz not null default now(),
  constraint video_sources_source_key_format
    check (source_key ~ '^[a-z0-9][a-z0-9-]{1,62}$')
);

alter table public.videos
  add column video_source_id uuid
  references public.video_sources(id) on delete restrict;

create index idx_videos_video_source_id
  on public.videos(video_source_id);

create table public.video_rights_assessments (
  id uuid primary key default gen_random_uuid(),
  video_id uuid not null
    references public.videos(id) on delete restrict,
  right_type text not null
    check (right_type in (
      'manual_scouting',
      'automated_analysis',
      'commercial_use',
      'download_storage',
      'clip_extraction',
      'redistribution'
    )),
  status text not null default 'unknown'
    check (status in ('granted', 'prohibited', 'unknown', 'not_reviewed')),
  basis_type text not null default 'unknown'
    check (basis_type in (
      'written_permission',
      'contract',
      'provider_terms',
      'open_license',
      'legal_review',
      'unknown'
    )),
  territory_scope text not null default 'unknown'
    check (territory_scope in ('global', 'country', 'unknown')),
  country_code varchar(2),
  evidence_url text,
  evidence_note text,
  checked_by uuid default auth.uid()
    references auth.users(id) on delete set null,
  checked_at timestamptz not null default now(),
  valid_from timestamptz,
  valid_until timestamptz,
  created_at timestamptz not null default now(),
  constraint video_rights_country_code_format
    check (country_code is null or country_code ~ '^[A-Z]{2}$'),
  constraint video_rights_country_scope_consistency
    check (
      (territory_scope = 'country' and country_code is not null)
      or (territory_scope <> 'country' and country_code is null)
    ),
  constraint video_rights_validity_window
    check (valid_until is null or valid_from is null or valid_until >= valid_from)
);

create index idx_video_rights_assessments_video_right_checked
  on public.video_rights_assessments(video_id, right_type, checked_at desc);

create index idx_video_rights_assessments_checked_by
  on public.video_rights_assessments(checked_by);

alter table public.video_sources enable row level security;
alter table public.video_rights_assessments enable row level security;

revoke all on table public.video_sources from public, anon, authenticated;
grant select, insert, update, delete on table public.video_sources to authenticated;

revoke all on table public.video_rights_assessments from public, anon, authenticated;
grant select, insert on table public.video_rights_assessments to authenticated;

create policy vel_staff_manage_video_sources
  on public.video_sources
  for all
  to authenticated
  using ((select private.is_vel_staff()))
  with check ((select private.is_vel_staff()));

create policy vel_staff_read_video_rights_assessments
  on public.video_rights_assessments
  for select
  to authenticated
  using ((select private.is_vel_staff()));

create policy vel_staff_insert_video_rights_assessments
  on public.video_rights_assessments
  for insert
  to authenticated
  with check (
    (select private.is_vel_staff())
    and (checked_by is null or checked_by = (select auth.uid()))
  );

comment on table public.video_sources is
  'Private catalogue of match-video providers and discovery indexes. A source entry does not grant any content-use rights.';

comment on column public.videos.video_source_id is
  'Optional normalized link to video_sources. Existing source_name remains for backward compatibility; no unverified rows are auto-mapped.';

comment on table public.video_rights_assessments is
  'Append-only, staff-only evidence history for each video usage right. Unknown is the default; viewing access is tracked separately in video_access_checks.';

create or replace function private.seed_default_video_rights_assessments()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $function$
begin
  insert into public.video_rights_assessments (
    video_id,
    right_type,
    status,
    basis_type,
    territory_scope,
    evidence_note
  )
  select
    new.id,
    rights.right_type,
    'unknown',
    'unknown',
    'unknown',
    'No item-specific usage-rights evidence has been reviewed yet.'
  from unnest(array[
    'manual_scouting',
    'automated_analysis',
    'commercial_use',
    'download_storage',
    'clip_extraction',
    'redistribution'
  ]::text[]) as rights(right_type);

  return new;
end;
$function$;

revoke all on function private.seed_default_video_rights_assessments() from public, anon, authenticated;

create trigger trg_seed_default_video_rights_assessments
  after insert on public.videos
  for each row
  execute function private.seed_default_video_rights_assessments();

-- Seed known discovery candidates. All remain candidates until reviewed in the admin workflow.
insert into public.video_sources (
  source_key, display_name, operator_name, source_type, canonical_url,
  terms_url, officiality_status, discovery_method, coverage_notes, review_status
)
values
  (
    'fifa-plus', 'FIFA+', 'FIFA', 'official_archive',
    'https://www.plus.fifa.com/en/catalogue/archive',
    null, 'official', 'manual',
    'International FIFA competitions and selected full-match archive items; match-level availability and regional playback must be checked.',
    'candidate'
  ),
  (
    'uefa-tv-reruns', 'UEFA.tv Re-Runs', 'UEFA', 'official_archive',
    'https://www.uefa.tv/section/Re-Runs',
    'https://www.uefa.com/uefatvtermsconditions/',
    'official', 'manual',
    'Selected UEFA match re-runs and other competitions; account, territory, completeness and processing rights are separate checks.',
    'candidate'
  ),
  (
    'premier-league-archive', 'Premier League Archive', 'Premier League', 'official_archive',
    'https://www.premierleague.com/en/welcome/the-archive/content-format-all/2025-26',
    null, 'official', 'manual',
    'Official league archive; availability is season- and match-specific and does not itself grant automated or commercial processing rights.',
    'candidate'
  ),
  (
    'tff-youtube', 'TFF Official YouTube', 'Turkish Football Federation', 'official_channel',
    'https://www.youtube.com/@TFF',
    null, 'official', 'manual',
    'Federation channel for selected national-team and development/competition content; not a complete all-match archive.',
    'candidate'
  ),
  (
    'football-archive', 'Football Archive — Full Matches', 'Football Archive', 'discovery_index',
    'https://footballarchive.org/stats/full-matches/',
    null, 'third_party_index', 'manual',
    'Discovery index that points to external video pages; it is not treated as the video host or rights holder.',
    'candidate'
  ),
  (
    'hudl-wyscout', 'Hudl Wyscout', 'Hudl', 'licensed_provider',
    'https://www.hudl.com/products/wyscout',
    null, 'official', 'manual',
    'Professional licensed video/data provider; no free/public access or AI-processing licence is assumed.',
    'candidate'
  ),
  (
    'soccernet-dataset', 'SoccerNet Dataset', 'SoccerNet', 'research_dataset',
    'https://www.soccer-net.org/',
    null, 'official', 'manual',
    'Research video/anotation datasets for permitted research and benchmarking; dataset terms must be checked before each use.',
    'candidate'
  ),
  (
    'metrica-sample-data', 'Metrica Sports Sample Data', 'Metrica Sports', 'research_dataset',
    'https://github.com/metrica-sports/sample-data',
    null, 'official', 'manual',
    'Small anonymized sample tracking/event/video dataset for pipeline prototyping, not named-player scouting coverage.',
    'candidate'
  )
on conflict (source_key) do nothing;

-- Backfill every existing video with six explicit unknown rights states.
insert into public.video_rights_assessments (
  video_id, right_type, status, basis_type, territory_scope, evidence_note
)
select
  v.id,
  rights.right_type,
  'unknown',
  'unknown',
  'unknown',
  'Baseline record: no item-specific evidence for this usage right was verified during source-registry setup.'
from public.videos v
cross join unnest(array[
  'manual_scouting',
  'automated_analysis',
  'commercial_use',
  'download_storage',
  'clip_extraction',
  'redistribution'
]::text[]) as rights(right_type);
