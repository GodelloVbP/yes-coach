-- Yes Coach! connector: keeps a connected AI app inside its bounds, in the database itself.
-- Supabase gives an OAuth token the same database access as the user unless policies say otherwise (scopes limit nothing).
-- With this file, a connected app can READ the user's own data and WRITE only the plan (root settings, exercises,
-- training days), notes, food entries (one document per day, yc/food/<date>) and the person's own foods and saved meals
-- (yc/myfoods/<id>, yc/meals/<id>) and the log (yc/sessions/<id>: adding sets and flagging sets as removed). It can not write
-- anything else, delete a document, touch tickets, act as the owner, or delete the account (see delete_me and is_admin).
-- Removing a food entry or a set is an update of that day's document, not a delete. Whatever the app tries, the database says no.
-- Run after schema.sql and tickets.sql (both define is_oauth_client and the checks that use it). Safe to run again.

drop policy if exists "connected apps: plan writes only (insert)" on public.docs;
create policy "connected apps: plan writes only (insert)" on public.docs as restrictive for insert to authenticated
  with check (not public.is_oauth_client() or path = 'yc' or path like 'yc/exercises/%' or path like 'yc/templates/%' or path like 'yc/notes/%' or path like 'yc/food/%' or path like 'yc/myfoods/%' or path like 'yc/meals/%' or path like 'yc/sessions/%');

drop policy if exists "connected apps: plan writes only (update)" on public.docs;
create policy "connected apps: plan writes only (update)" on public.docs as restrictive for update to authenticated
  using (not public.is_oauth_client() or path = 'yc' or path like 'yc/exercises/%' or path like 'yc/templates/%' or path like 'yc/notes/%' or path like 'yc/food/%' or path like 'yc/myfoods/%' or path like 'yc/meals/%' or path like 'yc/sessions/%')
  with check (not public.is_oauth_client() or path = 'yc' or path like 'yc/exercises/%' or path like 'yc/templates/%' or path like 'yc/notes/%' or path like 'yc/food/%' or path like 'yc/myfoods/%' or path like 'yc/meals/%' or path like 'yc/sessions/%');

drop policy if exists "connected apps: no deletes" on public.docs;
create policy "connected apps: no deletes" on public.docs as restrictive for delete to authenticated
  using (not public.is_oauth_client());

-- Tickets are between the user and the owner; a connected app has no part in them.
drop policy if exists "connected apps: no tickets" on public.tickets;
create policy "connected apps: no tickets" on public.tickets as restrictive for all to authenticated
  using (not public.is_oauth_client()) with check (not public.is_oauth_client());

drop policy if exists "connected apps: no ticket messages" on public.ticket_messages;
create policy "connected apps: no ticket messages" on public.ticket_messages as restrictive for all to authenticated
  using (not public.is_oauth_client()) with check (not public.is_oauth_client());
