// Yes Coach! service worker. It does one thing: shows the "Rest is over" notification when a push arrives.
// It caches nothing and answers no requests, so the app itself is never served from here.
const STORE = 'yc-push-text';
const read = async () => {
  try { const r = await (await caches.open(STORE)).match(new Request('text')); return r ? await r.json() : null; } catch (e) { return null; }
};
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
// the app sends the words in the person's language; they are kept here for the next push
self.addEventListener('message', (e) => {
  const d = e.data;
  if (d && d.type === 'text' && typeof d.title === 'string' && typeof d.body === 'string') {
    e.waitUntil(caches.open(STORE).then((c) => c.put(new Request('text'), new Response(JSON.stringify({ title: d.title.slice(0, 80), body: d.body.slice(0, 160) })))));
  }
});
self.addEventListener('push', (e) => {
  e.waitUntil((async () => {
    const t = (await read()) || {};
    await self.registration.showNotification(t.title || 'Rest is over', { body: t.body || 'Time for the next set.', tag: 'yc-rest', renotify: true, icon: 'icon-192.png' });
  })());
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cs) => (cs.length ? cs[0].focus() : self.clients.openWindow('./'))));
});
