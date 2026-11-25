-- Yes Coach! calendar link: your planned workouts as a calendar that Apple Calendar, Google Calendar and Outlook subscribe to.
-- Run once in Supabase: SQL Editor, New query, paste, Run. Safe to run again. Needs schema.sql first (is_oauth_client).
--
--   calendar_feeds  one row per person who switched the link on: a long random token, the calendar text the app built from their plan
--                   (the next 8 weeks, rebuilt by the app whenever the plan changes) and the time and length they picked. Own row only.
--   calendar_feed(token)  hands the calendar text to anyone who holds the token. The calendar function calls it with the public key,
--                   so no admin key is stored anywhere. Without the token nothing can be read; a wrong token returns nothing.
-- A connected AI app can not touch the table.

create table if not exists public.calendar_feeds (
  user_id uuid primary key default auth.uid() references auth.users (id) on delete cascade,
  token text not null,
  ics text not null default '',
  prefs jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  constraint calendar_feeds_token check (token ~ '^[a-f0-9]{48}$'),
  constraint calendar_feeds_size check (octet_length(ics) <= 200000)
);
create unique index if not exists calendar_feeds_token on public.calendar_feeds (token);

grant select, insert, update, delete on public.calendar_feeds to authenticated;
alter table public.calendar_feeds enable row level security;

drop policy if exists "own calendar feed" on public.calendar_feeds;
create policy "own calendar feed" on public.calendar_feeds for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "no connected apps: calendar feed" on public.calendar_feeds;
create policy "no connected apps: calendar feed" on public.calendar_feeds as restrictive for all to authenticated
  using (not public.is_oauth_client()) with check (not public.is_oauth_client());

create or replace function public.calendar_feed(tok text) returns text
language sql stable security definer set search_path = public as $$
  select ics from public.calendar_feeds where token = tok and tok ~ '^[a-f0-9]{48}$'
$$;
revoke all on function public.calendar_feed(text) from public;
grant execute on function public.calendar_feed(text) to anon, authenticated;
