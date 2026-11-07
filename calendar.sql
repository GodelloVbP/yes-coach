-- Yes Coach! calendar subscription. Run once in Supabase after schema.sql and connector.sql: SQL Editor, New query, paste, Run.
-- Safe to run again.
--
-- A calendar app (Apple, Google, Outlook) subscribes to a web address and fetches it by itself, every few hours. It can not
-- sign in, so the address carries a long random secret (the token). The app builds the person's planned days as a calendar
-- file and stores it here; the Edge Function "cal" hands that file to anyone who presents the token.
-- Whoever has the address can read the planned days (names, dates, exercise list), nothing else. Reset makes a new address.

create table if not exists public.calendar_feeds (
  user_id uuid primary key default auth.uid() references auth.users (id) on delete cascade,
  token text not null unique,
  ics text not null default '',
  updated_at timestamptz not null default now(),
  constraint calendar_feeds_size check (octet_length(ics) <= 262144)
);

alter table public.calendar_feeds enable row level security;
revoke all on public.calendar_feeds from public, anon;
grant select, insert, update, delete on public.calendar_feeds to authenticated;
drop policy if exists "own feed" on public.calendar_feeds;
create policy "own feed" on public.calendar_feeds for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- The token is a secret; a connected AI app has no business with it.
drop policy if exists "connected apps: no calendar feed" on public.calendar_feeds;
create policy "connected apps: no calendar feed" on public.calendar_feeds as restrictive for all to authenticated
  using (not public.is_oauth_client()) with check (not public.is_oauth_client());

-- Store the calendar file and return the token (made on first use). The app calls this whenever the plan changes.
create or replace function public.calendar_publish(p_ics text) returns text
language plpgsql security invoker set search_path = public as $$
declare t text;
begin
  if auth.uid() is null or public.is_oauth_client() then raise exception 'not allowed' using errcode = '42501'; end if;
  insert into public.calendar_feeds (user_id, token, ics)
    values (auth.uid(), replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', ''), p_ics)
  on conflict (user_id) do update set ics = excluded.ics, updated_at = now()
  returning token into t;
  return t;
end $$;
revoke all on function public.calendar_publish(text) from public, anon;
grant execute on function public.calendar_publish(text) to authenticated;

-- A new address; the old one stops working at once. Use it when the address was shared by mistake.
create or replace function public.calendar_reset() returns text
language plpgsql security invoker set search_path = public as $$
declare t text;
begin
  if auth.uid() is null or public.is_oauth_client() then raise exception 'not allowed' using errcode = '42501'; end if;
  update public.calendar_feeds set token = replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', ''), updated_at = now()
   where user_id = auth.uid() returning token into t;
  return t;
end $$;
revoke all on function public.calendar_reset() from public, anon;
grant execute on function public.calendar_reset() to authenticated;

-- Stop sharing: the address stops working and the stored file is deleted.
create or replace function public.calendar_off() returns void
language plpgsql security invoker set search_path = public as $$
begin
  if auth.uid() is null or public.is_oauth_client() then raise exception 'not allowed' using errcode = '42501'; end if;
  delete from public.calendar_feeds where user_id = auth.uid();
end $$;
revoke all on function public.calendar_off() from public, anon;
grant execute on function public.calendar_off() to authenticated;

-- What the Edge Function "cal" calls with no sign-in: the calendar file for one token, or null. Returns nothing else.
create or replace function public.calendar_feed(p_token text) returns text
language sql stable security definer set search_path = public as $$
  select ics from public.calendar_feeds where token = p_token and length(p_token) >= 32;
$$;
revoke all on function public.calendar_feed(text) from public;
grant execute on function public.calendar_feed(text) to anon, authenticated;
