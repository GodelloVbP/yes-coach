-- Yes Coach! database. Run once in Supabase: SQL Editor, New query, paste, Run.
-- One table holds every user's documents (root, exercises, training days, sessions, notes, weeks) as JSON.
-- Row-level security: a signed-in user can only ever see and change their own rows.

create table if not exists public.docs (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  path text not null,
  data jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, path)
);

-- Signed-in users may use the table; the policy below limits them to their own rows.
grant usage on schema public to authenticated;
grant select, insert, update, delete on public.docs to authenticated;

alter table public.docs enable row level security;
drop policy if exists "own docs" on public.docs;
create policy "own docs" on public.docs for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Nested objects merge; anything else is replaced. The app relies on this for partial updates.
create or replace function public.jsonb_deep_merge(a jsonb, b jsonb) returns jsonb
language sql immutable as $$
  select case
    when jsonb_typeof(a) = 'object' and jsonb_typeof(b) = 'object' then coalesce((
      select jsonb_object_agg(k, case when a ? k and b ? k then public.jsonb_deep_merge(a -> k, b -> k)
                                      when b ? k then b -> k else a -> k end)
      from (select jsonb_object_keys(a) as k union select jsonb_object_keys(b)) keys), '{}'::jsonb)
    else b end
$$;

-- Merge a patch into one existing document; fails when the document does not exist.
create or replace function public.yc_update(p_path text, p_patch jsonb) returns jsonb
language plpgsql security invoker set search_path = public as $$
declare r jsonb;
begin
  update public.docs set data = public.jsonb_deep_merge(data, p_patch), updated_at = now()
   where user_id = auth.uid() and path = p_path
   returning data into r;
  if not found then raise exception 'not found' using errcode = 'P0002'; end if;
  return r;
end $$;

-- A user deletes their own account; their documents go with it (on delete cascade).
create or replace function public.delete_me() returns void
language sql security definer set search_path = public as $$
  delete from auth.users where id = auth.uid();
$$;
revoke all on function public.delete_me() from public, anon;
grant execute on function public.delete_me() to authenticated;
grant execute on function public.yc_update(text, jsonb) to authenticated;

-- Live sync between a user's devices.
do $$ begin
  alter publication supabase_realtime add table public.docs;
exception when duplicate_object then null; end $$;

-- The number of accounts, for the Home page ("N people train with Yes Coach!"). Returns a count only, no emails.
create or replace function public.user_count() returns integer
language sql security definer set search_path = public as $$
  select count(*)::int from auth.users;
$$;
revoke all on function public.user_count() from public;
grant execute on function public.user_count() to anon, authenticated;
