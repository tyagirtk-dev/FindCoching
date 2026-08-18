/*
 * LocalTutor service worker
 * Strategy:
 *  - App shell / static assets: cache-first (fast repeat loads, offline support)
 *  - HTML navigations: network-first, falling back to cache, then an offline page
 *  - Everything else (API calls, form POSTs, auth): always network — never cached,
 *    so payments, login, and all business logic behave exactly as before.
 */
const CACHE_VERSION = "localtutor-v1";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const PAGES_CACHE = `${CACHE_VERSION}-pages`;

const APP_SHELL = [
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/offline",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key.startsWith("localtutor-") && key !== STATIC_CACHE && key !== PAGES_CACHE)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

function isStaticAsset(url) {
  return (
    url.pathname.startsWith("/static/css/") ||
    url.pathname.startsWith("/static/js/") ||
    url.pathname.startsWith("/static/icons/") ||
    url.pathname === "/static/manifest.json"
  );
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return; // never intercept POST/PUT (payments, forms, auth)

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // let CDN requests pass through untouched

  // Never cache dynamic app data
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/static/uploads/")) {
    return;
  }

  if (isStaticAsset(url)) {
    event.respondWith(
      caches.open(STATIC_CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        const network = fetch(request)
          .then((res) => {
            if (res && res.ok) cache.put(request, res.clone());
            return res;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((res) => {
          caches.open(PAGES_CACHE).then((cache) => cache.put(request, res.clone()));
          return res;
        })
        .catch(async () => {
          const cache = await caches.open(PAGES_CACHE);
          const cached = await cache.match(request);
          return cached || caches.match("/offline");
        })
    );
  }
});
