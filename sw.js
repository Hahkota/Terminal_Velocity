// Terminal Velocity offline helper. Keeps a copy of the app so it works without internet.
// The page itself is always fetched fresh when online (so updates arrive straight away) and the saved copy is
// used only when offline. Nothing is ever sent anywhere: it only handles requests for this app's own files.
const VERSION = "terminal-velocity-880947951882";
const FILES = ["./", "index.html", "manifest.webmanifest", "icons/icon.svg", "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png", "icons/apple-touch-icon.png", "icons/favicon-32.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  if (req.mode === "navigate") {
    // the page: try the network first, fall back to the saved copy when offline
    event.respondWith(fetch(req).then((res) => {
      const copy = res.clone();
      if (res.ok) caches.open(VERSION).then((cache) => cache.put("index.html", copy));
      return res;
    }).catch(() => caches.match("index.html")));
    return;
  }
  // icons and manifest: the saved copy, or the network if it isn't saved
  event.respondWith(caches.match(req).then((hit) => hit || fetch(req)));
});
