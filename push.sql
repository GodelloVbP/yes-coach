-- Yes Coach! rest alerts: a notification when the rest timer ends while the app is in the background.
-- Run once in Supabase: SQL Editor, New query, paste, Run. Safe to run again. Needs schema.sql first (is_oauth_client).
--
--   push_subs    one row per device that allowed notifications: the push service address and its keys. Own rows only.
--   rest_alerts  one pending alert per person while a rest runs; the rest-push function deletes it when it has sent or when the
--                app cancels it. Own rows only.
-- A connected AI app can not touch either table.

create table if not exists public.push_subs (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  endpoint text not null,
  p256dh text not null default '',
  auth text not null default '',
  created_at timestamptz not null default now(),
  primary key (user_id, endpoint),
  constraint push_subs_endpoint_len check (char_length(endpoint) <= 1000)
);
create table if not exists public.rest_alerts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  fire_at timestamptz not null default now()
);
create index if not exists rest_alerts_user on public.rest_alerts (user_id);

grant select, insert, update, delete on public.push_subs to authenticated;
grant select, insert, update, delete on public.rest_alerts to authenticated;
alter table public.push_subs enable row level security;
alter table public.rest_alerts enable row level security;

drop policy if exists "own push subs" on public.push_subs;
create policy "own push subs" on public.push_subs for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "no connected apps: push subs" on public.push_subs;
create policy "no connected apps: push subs" on public.push_subs as restrictive for all to authenticated
  using (not public.is_oauth_client()) with check (not public.is_oauth_client());

drop policy if exists "own rest alerts" on public.rest_alerts;
create policy "own rest alerts" on public.rest_alerts for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "no connected apps: rest alerts" on public.rest_alerts;
create policy "no connected apps: rest alerts" on public.rest_alerts as restrictive for all to authenticated
  using (not public.is_oauth_client()) with check (not public.is_oauth_client());

-- no more than 10 devices per person
create or replace function public.push_subs_limit() returns trigger
language plpgsql set search_path = public as $$
begin
  if (select count(*) from public.push_subs where user_id = new.user_id) >= 10 and not exists (select 1 from public.push_subs where user_id = new.user_id and endpoint = new.endpoint) then
    raise exception 'too_many_devices' using errcode = 'check_violation';
  end if;
  return new;
end $$;
drop trigger if exists push_subs_limit on public.push_subs;
create trigger push_subs_limit before insert on public.push_subs for each row execute function public.push_subs_limit();
