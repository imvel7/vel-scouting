-- VEL SCOUTING: access policies for the existing 10-table database.
-- ASCII-only file to avoid hidden direction marks during mobile copy/paste.
-- Run this once in Supabase SQL Editor AFTER replacing the UID placeholder below.

begin;

create table if not exists public.user_roles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('admin', 'editor')),
  created_at timestamptz not null default now()
);

alter table public.user_roles enable row level security;

create or replace function public.is_vel_staff()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.user_roles
    where user_id = (select auth.uid())
      and role in ('admin', 'editor')
  );
$$;

create or replace function public.is_vel_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.user_roles
    where user_id = (select auth.uid())
      and role = 'admin'
  );
$$;

revoke all on function public.is_vel_staff() from public;
revoke all on function public.is_vel_admin() from public;
grant execute on function public.is_vel_staff() to authenticated;
grant execute on function public.is_vel_admin() to authenticated;

grant usage on schema public to anon, authenticated;
grant select on table public.players, public.clubs, public.scout_reports to anon, authenticated;
grant select, insert, update, delete on table
  public.players,
  public.clubs,
  public.competitions,
  public.seasons,
  public.matches,
  public.player_matches,
  public.videos,
  public.observations,
  public.scout_reports,
  public.report_versions,
  public.user_roles
  to authenticated;

-- Remove policies with these names first so this script can be safely re-run.
drop policy if exists "vel_public_read_published_players" on public.players;
drop policy if exists "vel_staff_manage_players" on public.players;
drop policy if exists "vel_public_read_linked_clubs" on public.clubs;
drop policy if exists "vel_staff_manage_clubs" on public.clubs;
drop policy if exists "vel_public_read_published_reports" on public.scout_reports;
drop policy if exists "vel_staff_manage_scout_reports" on public.scout_reports;
drop policy if exists "vel_user_read_own_role" on public.user_roles;
drop policy if exists "vel_admin_manage_roles" on public.user_roles;

create policy "vel_public_read_published_players"
on public.players for select to anon, authenticated
using (profile_status = 'published');

create policy "vel_staff_manage_players"
on public.players for all to authenticated
using ((select public.is_vel_staff()))
with check ((select public.is_vel_staff()));

create policy "vel_public_read_linked_clubs"
on public.clubs for select to anon, authenticated
using (
  exists (
    select 1 from public.players p
    where p.current_club_id = clubs.id
      and p.profile_status = 'published'
  )
);

create policy "vel_staff_manage_clubs"
on public.clubs for all to authenticated
using ((select public.is_vel_staff()))
with check ((select public.is_vel_staff()));

create policy "vel_public_read_published_reports"
on public.scout_reports for select to anon, authenticated
using (
  report_status = 'published'
  and exists (
    select 1 from public.players p
    where p.id = scout_reports.player_id
      and p.profile_status = 'published'
  )
);

create policy "vel_staff_manage_scout_reports"
on public.scout_reports for all to authenticated
using ((select public.is_vel_staff()))
with check ((select public.is_vel_staff()));

create policy "vel_user_read_own_role"
on public.user_roles for select to authenticated
using (user_id = (select auth.uid()));

create policy "vel_admin_manage_roles"
on public.user_roles for all to authenticated
using ((select public.is_vel_admin()))
with check ((select public.is_vel_admin()));

-- Staff-only policies for the remaining private scouting tables.
drop policy if exists "vel_staff_manage_competitions" on public.competitions;
create policy "vel_staff_manage_competitions"
on public.competitions for all to authenticated
using ((select public.is_vel_staff())) with check ((select public.is_vel_staff()));

drop policy if exists "vel_staff_manage_seasons" on public.seasons;
create policy "vel_staff_manage_seasons"
on public.seasons for all to authenticated
using ((select public.is_vel_staff())) with check ((select public.is_vel_staff()));

drop policy if exists "vel_staff_manage_matches" on public.matches;
create policy "vel_staff_manage_matches"
on public.matches for all to authenticated
using ((select public.is_vel_staff())) with check ((select public.is_vel_staff()));

drop policy if exists "vel_staff_manage_player_matches" on public.player_matches;
create policy "vel_staff_manage_player_matches"
on public.player_matches for all to authenticated
using ((select public.is_vel_staff())) with check ((select public.is_vel_staff()));

drop policy if exists "vel_staff_manage_videos" on public.videos;
create policy "vel_staff_manage_videos"
on public.videos for all to authenticated
using ((select public.is_vel_staff())) with check ((select public.is_vel_staff()));

drop policy if exists "vel_staff_manage_observations" on public.observations;
create policy "vel_staff_manage_observations"
on public.observations for all to authenticated
using ((select public.is_vel_staff())) with check ((select public.is_vel_staff()));

drop policy if exists "vel_staff_manage_report_versions" on public.report_versions;
create policy "vel_staff_manage_report_versions"
on public.report_versions for all to authenticated
using ((select public.is_vel_staff())) with check ((select public.is_vel_staff()));

-- IMPORTANT: replace the text below with your own Auth user UUID from
-- Supabase > Authentication > Users. Keep the single quotes.
insert into public.user_roles (user_id, role)
values ('PASTE_YOUR_AUTH_USER_UUID_HERE', 'admin')
on conflict (user_id) do update set role = 'admin';

commit;
