-- Preserve the rights history as append-only evidence records.
-- A granted permission must always name a basis and attach a note or evidence URL.
alter table public.video_rights_assessments
  add constraint video_rights_granted_requires_evidence
  check (
    status <> 'granted'
    or (
      basis_type <> 'unknown'
      and (
        nullif(btrim(evidence_url), '') is not null
        or nullif(btrim(evidence_note), '') is not null
      )
    )
  );

-- Add the official TRT Spor page as a candidate source.
-- The page title alone does not verify that the playback is currently available or complete.
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
  review_status
)
values (
  'trt-spor',
  'TRT Spor — Maçın Tamamı',
  'Türkiye Radyo Televizyon Kurumu (TRT)',
  'official_channel',
  'https://www.trtspor.com.tr/videolar/macin-tamami-or-galatasaray-juventus-5-2-sampiyonlar-ligi-son-16-play-off-turu-29850144',
  null,
  'official',
  'manual',
  'Official TRT Spor page for Galatasaray 5–2 Juventus. The page title describes a full-match replay, but playback, duration, continuity, account/territory access and any separate reuse or automated-analysis rights remain unverified.',
  'candidate'
)
on conflict (source_key) do nothing;

-- Link only exact, already-known source rows. No fuzzy name matching or rights assumptions.
update public.videos v
set video_source_id = s.id
from public.video_sources s
where v.video_source_id is null
  and s.source_key = 'uefa-tv-reruns'
  and v.source_name = 'UEFA.tv Re-Runs'
  and v.video_url = 'https://www.uefa.tv/section/Re-Runs';

update public.videos v
set video_source_id = s.id
from public.video_sources s
where v.video_source_id is null
  and s.source_key = 'trt-spor'
  and v.source_name = 'TRT Spor — Maçın Tamamı'
  and v.video_url = 'https://www.trtspor.com.tr/videolar/macin-tamami-or-galatasaray-juventus-5-2-sampiyonlar-ligi-son-16-play-off-turu-29850144';
