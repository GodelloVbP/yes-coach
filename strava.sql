-- Yes Coach! Strava connection: where the strava function keeps the sign-in tokens of people who connected their Strava account.
-- Run once in Supabase: SQL Editor, New query, paste, Run. Safe to run again.
--
-- Row-level security is on and there is NO policy, and the app's roles are revoked: the browser, and a connected AI app, can never
-- read or write these rows. Only the strava Edge Function does, with the project's service key, after checking who is asking.

create table if not exists public.strava_links (
  user_id uuid primary key references auth.users (id) on delete cascade,
  athlete_id bigint,
  access_token text not null,
  refresh_token text not null,
  expires_at timestamptz not null,
  scope text not null default '',
  created_at timestamptz not null default now()
);
alter table public.strava_links enable row level security;
revoke all on public.strava_links from anon, authenticated;
