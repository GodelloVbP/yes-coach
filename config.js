// Filled in once from Supabase: Project Settings, API. The anon key is meant to be public;
// row-level security in schema.sql is what keeps each user's data private.
window.YC_CONFIG = {
  supabaseUrl: 'https://qazvzhhoalkyyasakphs.supabase.co',
  supabaseAnonKey: 'sb_publishable_xm8P_yz9T-96YfcI2doESw_FOhLtALt',
  appUrl: 'https://godellovbp.github.io/yes-coach/',
  turnstileKey: '0x4AAAAAAF0wHRoRqdBkO_As', // Cloudflare Turnstile site key (public); the secret lives in Supabase
  userCounterMin: 100, // the sign-in page shows how many people train here only from this number up
  vapidPublicKey: 'BENmNEVipXAXFW4j4FK_MGZZUoidxwnY9nn4NMnz9JRJMIj9-3kUdZ-qZGTUeqpaxbvrTWBa99Nc-6BG7Y7IWps', // rest alerts: the public key from `node tools/vapid.mjs` (the private one lives in Supabase). Empty keeps the feature hidden.
  contactEmail: 'stijesiebelink@gmail.com', // shown on the privacy page
};
