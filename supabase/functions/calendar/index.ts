// Yes Coach! calendar link: serves a person's planned workouts as an iCalendar feed that Apple Calendar, Google Calendar and Outlook
// subscribe to. One file, no dependencies. Deploy as the Supabase Edge Function "calendar" with "Verify JWT" switched off (a calendar app
// sends no sign-in; the long random token in the address is the key):
//   supabase functions deploy calendar --project-ref <project> --no-verify-jwt
// Address: https://<project>.supabase.co/functions/v1/calendar/<48 hex characters>.ics
// The text itself is built by the app and stored by calendar.sql (table calendar_feeds). This function only looks it up through the
// calendar_feed() database function with the public key: no admin key is used here.

declare const Deno: any;

type Env = { url: string; anonKey: string };

const TOKEN = /([a-f0-9]{48})(?:\.ics)?\/?$/;
const HEAD = { 'access-control-allow-origin': '*', 'cache-control': 'public, max-age=300' };
const plain = (text: string, status: number) => new Response(text, { status, headers: { ...HEAD, 'content-type': 'text/plain; charset=utf-8' } });

export const createHandler = (env: Env, f: typeof fetch = fetch) => async (req: Request): Promise<Response> => {
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: { ...HEAD, 'access-control-allow-methods': 'GET, HEAD, OPTIONS' } });
  if (req.method !== 'GET' && req.method !== 'HEAD') return plain('GET only', 405);
  const u = new URL(req.url);
  const token = (u.searchParams.get('t') || '').toLowerCase().match(/^[a-f0-9]{48}$/)?.[0] || (u.pathname.match(TOKEN) || [])[1];
  if (!token) return plain('Not found', 404);
  let text = '';
  try {
    const r = await f(env.url + '/rest/v1/rpc/calendar_feed', { method: 'POST', headers: { apikey: env.anonKey, authorization: 'Bearer ' + env.anonKey, 'content-type': 'application/json' }, body: JSON.stringify({ tok: token }) });
    if (!r.ok) return plain('Not now', 502);
    const body = await r.json().catch(() => null);
    text = typeof body === 'string' ? body : '';
  } catch (e) { return plain('Not now', 502); }
  if (!text) return plain('Not found', 404);
  return new Response(req.method === 'HEAD' ? null : text, { status: 200, headers: { ...HEAD, 'content-type': 'text/calendar; charset=utf-8', 'content-disposition': 'inline; filename="yes-coach.ics"' } });
};

// Supabase runs the file as a server; tests import createHandler instead
if (typeof Deno !== 'undefined' && Deno.serve && Deno.env) {
  const get = (k: string) => Deno.env.get(k) || '';
  Deno.serve(createHandler({ url: get('SUPABASE_URL'), anonKey: get('YC_ANON_KEY') || get('SUPABASE_ANON_KEY') }));
}
