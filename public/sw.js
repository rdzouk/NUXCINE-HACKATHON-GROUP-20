/**
 * Service worker.
 *
 * Deliberately small and deliberately conservative about what it caches.
 *
 * **The app shell is cached, the API never is.** A ride's status, a driver's
 * position and a fare are worthless a minute later, and serving a stale one
 * would be worse than an honest error: a passenger seeing a cached "driver is
 * two minutes away" from ten minutes ago has been actively misled. So every
 * /api/ request goes to the network, and only the shell falls back to cache.
 *
 * That still buys the thing that matters here. On a dropped connection the app
 * opens instead of showing the browser's offline page, and can say what is
 * wrong in its own words.
 */

const VERSION = 'vora-v1';
const SHELL = `${VERSION}-shell`;

// The minimum to render something. Hashed assets are picked up at runtime.
const SHELL_URLS = ['/', '/index.html', '/manifest.webmanifest', '/favicon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      // addAll rejects the whole install if any single URL 404s, which would
      // leave the app with no worker at all. Failing soft per URL is better.
      .then((cache) => Promise.allSettled(SHELL_URLS.map((u) => cache.add(u))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Never cache the API or the sockets. See the note at the top: a stale ride
  // is a lie, not a convenience.
  if (url.pathname.startsWith('/api/')) return;

  // Cross-origin (map tiles, fonts) goes straight to the network.
  if (url.origin !== self.location.origin) return;

  // Navigations: network first so a deploy is picked up immediately, cache as
  // the fallback so a dropped connection still opens the app.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(SHELL).then((c) => c.put('/index.html', copy));
          return response;
        })
        .catch(() =>
          caches.match('/index.html').then((cached) => cached ?? Response.error()),
        ),
    );
    return;
  }

  // Static assets are content-hashed by the build, so a cache hit can never be
  // stale: a changed file has a different name.
  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ??
        fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(SHELL).then((c) => c.put(request, copy));
          }
          return response;
        }),
    ),
  );
});
