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

-- Limits, so one account cannot fill the database: 256 KB per document and 20,000 documents per account.
do $$ begin
  alter table public.docs add constraint docs_size check (octet_length(data::text) <= 262144) not valid;
exception when duplicate_object then null; end $$;
create or replace function public.docs_limit() returns trigger
language plpgsql set search_path = public as $$
begin
  -- a save of a document that already exists (an upsert fires this trigger too) is never a new document
  if not exists (select 1 from public.docs where user_id = new.user_id and path = new.path)
     and (select count(*) from public.docs where user_id = new.user_id) >= 20000 then
    raise exception 'too many documents' using errcode = '54000';
  end if;
  return new;
end $$;
drop trigger if exists docs_limit on public.docs;
create trigger docs_limit before insert on public.docs for each row execute function public.docs_limit();

-- Nested objects merge; anything else is replaced. The app relies on this for partial updates.
create or replace function public.jsonb_deep_merge(a jsonb, b jsonb) returns jsonb
language sql immutable set search_path = public as $$
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

-- True when the request comes from an AI app the user connected (an OAuth token), not from the user's own sign-in.
-- Supabase puts the app's id in the token as client_id. connector.sql uses this to keep connected apps in bounds.
create or replace function public.is_oauth_client() returns boolean
language sql stable set search_path = public as $$
  select coalesce(auth.jwt() ->> 'client_id', '') <> '';
$$;
grant execute on function public.is_oauth_client() to authenticated;

-- A user deletes their own account; their documents go with it (on delete cascade). A connected AI app cannot.
create or replace function public.delete_me() returns void
language plpgsql security definer set search_path = public as $$
begin
  if public.is_oauth_client() then raise exception 'not allowed' using errcode = '42501'; end if;
  delete from auth.users where id = auth.uid();
end $$;
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
revoke all on function public.user_count() from public, anon;
grant execute on function public.user_count() to authenticated;
