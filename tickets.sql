-- Yes Coach! tickets: bug reports, feature requests and feedback, with a thread per ticket.
-- Run once in Supabase after schema.sql: SQL Editor, New query, paste, Run. Safe to run again.
--
-- Who can do what
--   A signed-in user:  send a ticket (with their first name; their account email is saved with it), read their own tickets and the thread, reply while the ticket is open,
--                      mark their own resolved/declined ticket as seen (the pop-up on entry).
--   The owner:         everything else, through the admin_* functions below. Add yourself once, after you have
--                      created your account in the app:
--                        insert into public.admins (user_id) select id from auth.users where email = 'you@example.com';
--   Nobody else:       status, outcome, notes and links between tickets are never writable by users.

-- Start clean: a policy from an older version of this file, under another name, would still apply next to the new ones.
do $$ declare r record; begin
  for r in select policyname, tablename from pg_policies where schemaname = 'public' and tablename in ('tickets', 'ticket_messages', 'admins') loop
    execute format('drop policy %I on public.%I', r.policyname, r.tablename);
  end loop;
end $$;

-- ---------------------------------------------------------------- the owner list
create table if not exists public.admins (
  user_id uuid primary key references auth.users (id) on delete cascade
);
alter table public.admins enable row level security; -- no policy on purpose: the app never reads this table directly
revoke all on public.admins from anon, authenticated;

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.admins where user_id = auth.uid());
$$;
revoke all on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

-- ---------------------------------------------------------------- tickets
create table if not exists public.tickets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  type text not null check (type in ('bug', 'feature', 'feedback')),
  title text not null check (char_length(title) between 3 and 120),
  body text not null check (char_length(body) between 3 and 4000),
  -- open: received · needs_info: we asked something · planned: we will build it · resolved: done (see outcome) · declined: not going ahead
  status text not null default 'open' check (status in ('open', 'needs_info', 'planned', 'resolved', 'declined')),
  outcome text check (outcome in ('built', 'fixed', 'thanks')),
  resolution_note text check (char_length(resolution_note) <= 2000), -- plain-language message shown to the user
  duplicate_of uuid references public.tickets (id) on delete set null, -- a duplicate mirrors its original
  app_version text check (char_length(app_version) <= 40),
  context jsonb not null default '{}'::jsonb check (octet_length(context::text) <= 2000), -- device and screen, added by the app
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz,
  user_seen_at timestamptz, -- when the user dismissed the pop-up about the final status
  constraint outcome_only_when_resolved check ((status = 'resolved') = (outcome is not null))
);
-- Who sent it, added after the first release (safe to run again). The first name is typed by the user, to be thanked by name.
-- The email is filled in by the database from the account (see tickets_fill below); a user can never set it.
alter table public.tickets add column if not exists first_name text check (char_length(first_name) between 1 and 40);
alter table public.tickets add column if not exists user_email text;
create index if not exists tickets_user_idx on public.tickets (user_id, created_at desc);
create index if not exists tickets_status_idx on public.tickets (status, created_at);
create index if not exists tickets_dup_idx on public.tickets (duplicate_of);

-- Supabase hands new tables to everyone by default; take that back, then give only what is needed.
revoke all on public.tickets from anon, authenticated;
grant select on public.tickets to authenticated;
grant insert (type, title, body, first_name, app_version, context) on public.tickets to authenticated; -- user_id defaults to the caller
grant update (user_seen_at) on public.tickets to authenticated; -- the only column a user may change

alter table public.tickets enable row level security;
create policy "read own or admin" on public.tickets for select to authenticated
  using (user_id = (select auth.uid()) or (select public.is_admin()));
create policy "send own" on public.tickets for insert to authenticated
  with check (user_id = (select auth.uid()));
-- only a finished ticket has a pop-up to dismiss
create policy "mark own seen" on public.tickets for update to authenticated
  using (user_id = (select auth.uid()) and status in ('resolved', 'declined')) with check (user_id = (select auth.uid()));

-- Save the email of the account with the ticket, so the owner knows who they are talking to. It comes from the account, not from the form.
create or replace function public.tickets_fill() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  new.user_email := (select email from auth.users where id = new.user_id);
  return new;
end $$;
revoke all on function public.tickets_fill() from public, anon, authenticated;
drop trigger if exists tickets_fill on public.tickets;
create trigger tickets_fill before insert on public.tickets for each row execute function public.tickets_fill();
update public.tickets t set user_email = u.email from auth.users u where u.id = t.user_id and t.user_email is null; -- tickets sent before this existed

-- At most 5 tickets per user per day (the owner is exempt).
create or replace function public.tickets_limit() returns trigger
language plpgsql set search_path = public as $$
begin
  perform pg_advisory_xact_lock(hashtext('tickets:' || new.user_id::text)); -- parallel requests wait for each other, so the count below is true
  if not public.is_admin()
     and (select count(*) from public.tickets where user_id = new.user_id and created_at > now() - interval '24 hours') >= 5 then
    raise exception 'too_many_tickets';
  end if;
  return new;
end $$;
drop trigger if exists tickets_limit on public.tickets;
create trigger tickets_limit before insert on public.tickets for each row execute function public.tickets_limit();

-- ---------------------------------------------------------------- thread
create table if not exists public.ticket_messages (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references public.tickets (id) on delete cascade,
  author text not null check (author in ('user', 'admin')),
  body text not null check (char_length(body) between 1 and 2000),
  created_at timestamptz not null default now()
);
create index if not exists ticket_messages_idx on public.ticket_messages (ticket_id, created_at);

revoke all on public.ticket_messages from anon, authenticated;
grant select on public.ticket_messages to authenticated;
grant insert (ticket_id, author, body) on public.ticket_messages to authenticated;

alter table public.ticket_messages enable row level security;
create policy "read own or admin" on public.ticket_messages for select to authenticated
  using ((select public.is_admin()) or exists (select 1 from public.tickets t where t.id = ticket_messages.ticket_id and t.user_id = (select auth.uid())));
-- A user writes as 'user', on their own ticket, while it is still open.
create policy "reply own" on public.ticket_messages for insert to authenticated
  with check (author = 'user' and exists (
    select 1 from public.tickets t
     where t.id = ticket_messages.ticket_id and t.user_id = (select auth.uid()) and t.status not in ('resolved', 'declined')));

-- At most 30 replies per user per day.
create or replace function public.ticket_messages_limit() returns trigger
language plpgsql set search_path = public as $$
begin
  if new.author = 'user' then
    perform pg_advisory_xact_lock(hashtext('messages:' || auth.uid()::text));
    if (select count(*) from public.ticket_messages m join public.tickets t on t.id = m.ticket_id
         where t.user_id = auth.uid() and m.author = 'user' and m.created_at > now() - interval '24 hours') >= 30 then
      raise exception 'too_many_messages';
    end if;
  end if;
  return new;
end $$;
drop trigger if exists ticket_messages_limit on public.ticket_messages;
create trigger ticket_messages_limit before insert on public.ticket_messages for each row execute function public.ticket_messages_limit();

-- When a user answers a question from us, the ticket goes back to "open" for the owner's queue.
create or replace function public.ticket_messages_reopen() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if new.author = 'user' then
    update public.tickets set status = 'open', updated_at = now() where id = new.ticket_id and status = 'needs_info';
  end if;
  return null;
end $$;
drop trigger if exists ticket_messages_reopen on public.ticket_messages;
create trigger ticket_messages_reopen after insert on public.ticket_messages for each row execute function public.ticket_messages_reopen();

-- If an original is deleted (by the owner, or because its author deleted their account), its duplicates stop mirroring.
-- Finished ones keep their result; the others go back to "open" so they show up in the owner's queue again.
create or replace function public.tickets_orphan() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  update public.tickets set duplicate_of = null, updated_at = now(),
         status = case when status in ('resolved', 'declined') then status else 'open' end
   where duplicate_of = old.id;
  return old;
end $$;
revoke all on function public.tickets_orphan() from public, anon, authenticated;
drop trigger if exists tickets_orphan on public.tickets;
create trigger tickets_orphan before delete on public.tickets for each row execute function public.tickets_orphan();

-- ---------------------------------------------------------------- owner functions
-- Set status, outcome, note and duplicate link in one go. A duplicate always mirrors its original:
-- link it and it takes the original's status and note; change the original and every duplicate follows.
-- The "your request was built" pop-up is armed (user_seen_at cleared) only when a ticket newly reaches resolved or declined.
create or replace function public.admin_set_ticket(
  p_id uuid, p_status text, p_outcome text default null, p_note text default null, p_duplicate_of uuid default null
) returns public.tickets
language plpgsql security definer set search_path = public as $$
declare t public.tickets; o public.tickets;
begin
  if not public.is_admin() then raise exception 'not allowed' using errcode = '42501'; end if;
  if p_duplicate_of is not null then
    if p_duplicate_of = p_id then raise exception 'a ticket cannot be a duplicate of itself'; end if;
    select * into o from public.tickets where id = p_duplicate_of;
    if not found then raise exception 'original not found' using errcode = 'P0002'; end if;
    if o.duplicate_of is not null then raise exception 'link to the original, not to a duplicate'; end if;
    if exists (select 1 from public.tickets where duplicate_of = p_id) then raise exception 'this ticket already has duplicates of its own'; end if;
    p_status := case when o.status = 'needs_info' then 'open' else o.status end; -- a question to the original's author is not a question to this one
    p_outcome := o.outcome; p_note := o.resolution_note;
  end if;

  update public.tickets set
    status = p_status,
    outcome = case when p_status = 'resolved' then p_outcome end,
    resolution_note = nullif(trim(coalesce(p_note, '')), ''),
    duplicate_of = p_duplicate_of,
    updated_at = now(),
    resolved_at = case when p_status in ('resolved', 'declined') then coalesce(resolved_at, now()) end,
    user_seen_at = case when p_status in ('resolved', 'declined') and (status, outcome) is distinct from (p_status, case when p_status = 'resolved' then p_outcome end)
                        then null else user_seen_at end
   where id = p_id returning * into t;
  if not found then raise exception 'not found' using errcode = 'P0002'; end if;

  update public.tickets set
    status = case when t.status = 'needs_info' then 'open' else t.status end,
    outcome = t.outcome, resolution_note = t.resolution_note, resolved_at = t.resolved_at, updated_at = now(),
    user_seen_at = case when t.status in ('resolved', 'declined') and (status, outcome) is distinct from (t.status, t.outcome)
                        then null else user_seen_at end
   where duplicate_of = t.id;
  return t;
end $$;

-- Write to the user in the ticket thread; ask = true also sets the ticket to "needs_info".
create or replace function public.admin_reply(p_ticket uuid, p_body text, p_ask boolean default false) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'not allowed' using errcode = '42501'; end if;
  insert into public.ticket_messages (ticket_id, author, body) values (p_ticket, 'admin', left(trim(p_body), 2000));
  if p_ask then
    update public.tickets set status = 'needs_info', updated_at = now() where id = p_ticket and status in ('open', 'needs_info');
  end if;
end $$;

-- Remove spam or junk for good.
create or replace function public.admin_delete_ticket(p_id uuid) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'not allowed' using errcode = '42501'; end if;
  delete from public.tickets where id = p_id;
end $$;

revoke all on function public.admin_set_ticket(uuid, text, text, text, uuid) from public, anon;
revoke all on function public.admin_reply(uuid, text, boolean) from public, anon;
revoke all on function public.admin_delete_ticket(uuid) from public, anon;
grant execute on function public.admin_set_ticket(uuid, text, text, text, uuid) to authenticated;
grant execute on function public.admin_reply(uuid, text, boolean) to authenticated;
grant execute on function public.admin_delete_ticket(uuid) to authenticated;
