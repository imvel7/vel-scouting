create table public.clubs (
  id uuid default gen_random_uuid() not null,
  name text not null,
  country text,
  city text,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null
);

create table public.competitions (
  id uuid default gen_random_uuid() not null,
  name text not null,
  country text,
  competition_type text,
  created_at timestamp with time zone default now() not null
);

create table public.criterion_scores (
  id uuid default gen_random_uuid() not null,
  session_id uuid not null,
  rubric_version_id uuid not null,
  criterion_id uuid not null,
  score smallint,
  applicability text not null,
  rationale text,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null
);

create table public.matches (
  id uuid default gen_random_uuid() not null,
  home_club_id uuid,
  away_club_id uuid,
  competition_id uuid,
  season_id uuid,
  match_date timestamp with time zone,
  home_score smallint,
  away_score smallint,
  age_category text,
  match_duration smallint,
  match_status text default 'scheduled'::text not null,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null
);

create table public.observations (
  id uuid default gen_random_uuid() not null,
  player_match_id uuid not null,
  minute smallint,
  category text not null,
  criterion text not null,
  situation text,
  observation text not null,
  evaluation text,
  evidence_level text default 'medium'::text not null,
  created_at timestamp with time zone default now() not null,
  session_id uuid,
  session_video_id uuid,
  rubric_version_id uuid,
  criterion_id uuid,
  video_offset_seconds integer,
  match_clock_seconds integer,
  period_code text
);

create table public.player_matches (
  id uuid default gen_random_uuid() not null,
  player_id uuid not null,
  match_id uuid not null,
  club_id uuid,
  position_played text,
  role_played text,
  minutes_played smallint,
  created_at timestamp with time zone default now() not null
);

create table public.players (
  id uuid default gen_random_uuid() not null,
  full_name text not null,
  date_of_birth date,
  nationality text,
  current_club_id uuid,
  main_position text,
  secondary_position text,
  preferred_foot text,
  height_cm smallint,
  profile_status text default 'draft'::text not null,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null
);

create table public.report_versions (
  id uuid default gen_random_uuid() not null,
  report_id uuid not null,
  version_number integer not null,
  report_snapshot jsonb not null,
  created_at timestamp with time zone default now() not null
);

create table public.rubric_categories (
  id uuid default gen_random_uuid() not null,
  rubric_version_id uuid not null,
  category_code text not null,
  category_name text not null,
  category_weight_percent smallint not null,
  sort_order smallint not null,
  created_at timestamp with time zone default now() not null
);

create table public.rubric_criteria (
  id uuid default gen_random_uuid() not null,
  rubric_version_id uuid not null,
  rubric_category_id uuid not null,
  criterion_code text not null,
  criterion_name text not null,
  weight_percent smallint not null,
  score_anchors jsonb not null,
  sort_order smallint not null,
  created_at timestamp with time zone default now() not null
);

create table public.rubric_versions (
  id uuid default gen_random_uuid() not null,
  version_code text not null,
  position_group text not null,
  methodology_version text not null,
  scoring_anchors_version text not null,
  score_min smallint default 1 not null,
  score_max smallint default 10 not null,
  status text default 'draft'::text not null,
  source_document text not null,
  change_summary text,
  created_by uuid,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null,
  published_at timestamp with time zone
);

create table public.scout_report_sessions (
  id uuid default gen_random_uuid() not null,
  report_id uuid not null,
  session_id uuid not null,
  player_id uuid not null,
  contribution_note text,
  created_at timestamp with time zone default now() not null
);

create table public.scout_reports (
  id uuid default gen_random_uuid() not null,
  player_id uuid not null,
  report_date date default CURRENT_DATE not null,
  methodology_version text default '0.8'::text not null,
  evidence_grade text,
  general_rating numeric(4,2),
  main_role text,
  alternative_roles text[],
  strengths text,
  development_areas text,
  final_verdict text,
  report_status text default 'draft'::text not null,
  created_by uuid,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null
);

create table public.scouting_session_videos (
  id uuid default gen_random_uuid() not null,
  session_id uuid not null,
  match_id uuid not null,
  video_id uuid not null,
  is_primary boolean default false not null,
  usage_note text,
  created_at timestamp with time zone default now() not null
);

create table public.scouting_sessions (
  id uuid default gen_random_uuid() not null,
  player_id uuid not null,
  player_match_id uuid not null,
  match_id uuid not null,
  rubric_version_id uuid not null,
  evaluator_user_id uuid default auth.uid() not null,
  status text default 'draft'::text not null,
  private_notes text,
  started_at timestamp with time zone,
  completed_at timestamp with time zone,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null
);

create table public.seasons (
  id uuid default gen_random_uuid() not null,
  name text not null,
  start_date date,
  end_date date,
  created_at timestamp with time zone default now() not null
);

create table public.user_roles (
  user_id uuid not null,
  role text not null,
  created_at timestamp with time zone default now() not null
);

create table public.video_access_checks (
  id uuid default gen_random_uuid() not null,
  video_id uuid not null,
  country_code character varying(2) not null,
  checked_by uuid,
  checked_at timestamp with time zone default now() not null,
  access_result text not null,
  account_requirement text not null,
  price_status text not null,
  coverage_status text not null,
  notes text,
  created_at timestamp with time zone default now() not null
);

create table public.video_rights_assessments (
  id uuid default gen_random_uuid() not null,
  video_id uuid not null,
  right_type text not null,
  status text default 'unknown'::text not null,
  basis_type text default 'unknown'::text not null,
  territory_scope text default 'unknown'::text not null,
  country_code character varying(2),
  evidence_url text,
  evidence_note text,
  checked_by uuid default auth.uid(),
  checked_at timestamp with time zone default now() not null,
  valid_from timestamp with time zone,
  valid_until timestamp with time zone,
  created_at timestamp with time zone default now() not null
);

create table public.video_sources (
  id uuid default gen_random_uuid() not null,
  source_key text not null,
  display_name text not null,
  operator_name text,
  source_type text not null,
  canonical_url text not null,
  terms_url text,
  officiality_status text default 'unknown'::text not null,
  discovery_method text default 'manual'::text not null,
  coverage_notes text,
  review_status text default 'candidate'::text not null,
  terms_last_checked_at timestamp with time zone,
  created_at timestamp with time zone default now() not null
);

create table public.videos (
  id uuid default gen_random_uuid() not null,
  match_id uuid not null,
  source_name text not null,
  video_url text not null,
  video_type text default 'full_match'::text not null,
  duration_minutes smallint,
  access_status text default 'unknown'::text not null,
  rights_status text default 'link_only'::text not null,
  last_checked_at timestamp with time zone,
  notes text,
  created_at timestamp with time zone default now() not null,
  video_source_id uuid
);
