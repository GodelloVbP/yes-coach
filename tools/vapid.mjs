// Makes the key pair for rest alerts (Web Push, VAPID). Run it on your own computer:  node tools/vapid.mjs [your@email]
// The public key goes into config.js (it is meant to be public). The private key goes into Supabase as a secret and nowhere else:
// do not commit it, paste it into a chat or put it in a file of this repository.
import { generateKeyPairSync } from 'node:crypto';
const b64u = (buf) => Buffer.from(buf).toString('base64url');
const { privateKey, publicKey } = generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
const jwk = privateKey.export({ format: 'jwk' });
const pub = Buffer.concat([Buffer.from([4]), Buffer.from(jwk.x, 'base64url'), Buffer.from(jwk.y, 'base64url')]);
const email = process.argv[2] || 'you@example.com';
console.log('1. In config.js, add this line inside YC_CONFIG:\n');
console.log("   vapidPublicKey: '" + b64u(pub) + "',\n");
console.log('2. Store the private key in Supabase (run in your terminal, with the Supabase CLI logged in):\n');
console.log('   supabase secrets set --project-ref qazvzhhoalkyyasakphs VAPID_PUBLIC_KEY=' + b64u(pub) + ' VAPID_PRIVATE_KEY=' + jwk.d + ' VAPID_SUBJECT=mailto:' + email + '\n');
console.log('Keep the private key (the long value after VAPID_PRIVATE_KEY=) to yourself.');
