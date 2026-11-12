-- Idempotent catalog seed for the CV validation dataset.
-- This is reference metadata only; it does not create a match/video row or grant usage rights.
insert into public.video_sources (
  source_key,
  display_name,
  operator_name,
  source_type,
  canonical_url,
  terms_url,
  officiality_status,
  discovery_method,
  coverage_notes,
  review_status,
  terms_last_checked_at
)
values (
  'soccertrack-v2',
  'SoccerTrack v2',
  'SoccerTrack v2 research team',
  'research_dataset',
  'https://atomscott.github.io/SoccerTrack-v2/',
  'https://github.com/AtomScott/SoccerTrack-v2/blob/main/LICENSE-DATA',
  'official',
  'manual',
  '10 full-length panoramic 4K university-level amateur matches (~900 minutes). Per-frame GSR coordinates/track IDs/jersey numbers/roles/team side and 12-class BAS action timestamps. Dataset license: CC BY 4.0 with attribution; upstream reports university ethics approval and informed participant consent, and no player names in the released records. Technical CV validation only; not a named-player scouting archive. ACCESS GATE: Hugging Face dataset is gated and requires authentication plus dataset-owner approval. CC BY 4.0 does not bypass this gate. Do not download/process until access is approved. Raw data must not be uploaded to public site or Supabase Storage.',
  'reviewed',
  '2026-11-12 14:17:19.054841+00'
)
on conflict (source_key) do nothing;
