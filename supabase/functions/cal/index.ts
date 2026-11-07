// Yes Coach! calendar feed: serves one person's planned training days as a calendar file (iCalendar) so Apple Calendar,
// Google Calendar and Outlook can subscribe to it. Deploy it as the Supabase Edge Function "cal" with "Verify JWT" switched off:
// calendar apps can not sign in, the long random token in the address is the key (see calendar.sql and README, "Calendar").
//
// GET /functions/v1/cal/<token>.ics  ->  text/calendar. Unknown token: 404 with no detail. The function holds no admin key;
// it asks the database function calendar_feed(token), which returns the file for that token and nothing else.

declare const Deno: any;

type Env = { url: string; anonKey: string };

const NOT_FOUND = { status: 404, headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } };

export const createHandler = (env: Env, f: typeof fetch = fetch) => async (req: Request): Promise<Response> => {
  if (req.method !== 'GET' && req.method !== 'HEAD') return new Response('Method not allowed', { status: 405, headers: { allow: 'GET, HEAD' } });
  const last = new URL(req.url).pathname.split('/').filter(Boolean).pop() || '';
  const token = last.replace(/\.ics$/i, '');
  if (!/^[0-9a-f]{32,64}$/.test(token)) return new Response('Not found', NOT_FOUND);
  let ics: unknown;
  try {
    const r = await f(env.url + '/rest/v1/rpc/calendar_feed', {
      method: 'POST',
      headers: { apikey: env.anonKey, authorization: 'Bearer ' + env.anonKey, 'content-type': 'application/json' },
      body: JSON.stringify({ p_token: token }),
    });
    if (!r.ok) return new Response('Try again later', { status: 502, headers: { 'cache-control': 'no-store' } });
    ics = await r.json();
  } catch (e) {
    return new Response('Try again later', { status: 502, headers: { 'cache-control': 'no-store' } });
  }
  if (typeof ics !== 'string' || !ics) return new Response('Not found', NOT_FOUND);
  return new Response(req.method === 'HEAD' ? null : ics, {
    status: 200,
    headers: {
      'content-type': 'text/calendar; charset=utf-8',
      'content-disposition': 'inline; filename="yes-coach.ics"',
      'cache-control': 'private, max-age=300',
      'x-robots-tag': 'noindex',
    },
  });
};

if (typeof Deno !== 'undefined' && Deno.serve) {
  Deno.serve(createHandler({ url: Deno.env.get('SUPABASE_URL') as string, anonKey: (Deno.env.get('YC_ANON_KEY') || Deno.env.get('SUPABASE_ANON_KEY')) as string }));
}
