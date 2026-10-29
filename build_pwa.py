#!/usr/bin/env python3
"""Build the Terminal Velocity installable web app from FLT.html.

Usage: python3 build_pwa.py FLT.html OUTPUT_FOLDER [ICONS_FOLDER]

Produces, in OUTPUT_FOLDER:
  index.html            FLT.html plus app tags, a strict content security policy and offline support
  manifest.webmanifest  app name, icons and colours (what makes it installable)
  sw.js                 offline helper; its version changes with every build so updates are picked up
  icons/                app icons (copied from ICONS_FOLDER if given)
  .nojekyll             tells GitHub Pages to serve the files exactly as they are
"""
import base64, hashlib, json, pathlib, re, shutil, sys

src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
icons = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else None
out.mkdir(parents=True, exist_ok=True)
html = src.read_text(encoding="utf-8")

# 1. app tags in <head>: description, keep out of search engines, no referrer, colours, manifest and icons
head_tags = """<meta name="description" content="Terminal Velocity: a touch-typing trainer for English, Ukrainian and Russian.">
<meta name="robots" content="noindex, nofollow">
<meta name="referrer" content="no-referrer">
<meta name="theme-color" content="#000000">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icons/icon.svg" type="image/svg+xml">
<link rel="icon" href="icons/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
"""
assert html.count("<title>") == 1
html = html.replace("<title>", head_tags + "<title>", 1)

# 2. offline helper: registered only when served from a web address (not when opened as a local file)
register = ('\nif ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) '
            'navigator.serviceWorker.register("sw.js");\n')
assert html.count("</body>") == 1
html = html.replace("</body>", "<script>" + register + "</script>\n</body>", 1)

# 3. strict content security policy: only this page's own scripts and styles may run (pinned by hash),
#    nothing may be loaded from anywhere else, and the page may not send data anywhere
def sha(text):
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode() + "'"
scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
styles = re.findall(r"<style>(.*?)</style>", html, re.S)
assert "style=\"" not in html.split("<body>", 1)[1].split("<script>", 1)[0], "inline style attributes would need 'unsafe-inline'"
csp = ("default-src 'none'; "
       "script-src " + " ".join(sha(s) for s in scripts) + "; "
       "style-src " + " ".join(sha(s) for s in styles) + "; "
       "font-src data:; img-src 'self' data:; manifest-src 'self'; worker-src 'self'; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'")
html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="' + csp + '">', 1)
(out / "index.html").write_text(html, encoding="utf-8")

# 4. manifest
manifest = {
    "name": "Terminal Velocity", "short_name": "Terminal Velocity",
    "description": "A touch-typing trainer for English, Ukrainian and Russian.",
    "id": "./", "start_url": "./", "scope": "./", "display": "standalone",
    "background_color": "#000000", "theme_color": "#000000", "lang": "en", "categories": ["education", "productivity"],
    "icons": [
        {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        {"src": "icons/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
    ],
}
(out / "manifest.webmanifest").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

# 5. icons
if icons:
    (out / "icons").mkdir(exist_ok=True)
    for f in ["icon.svg", "icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png", "favicon-32.png"]:
        shutil.copy(icons / f, out / "icons" / f)

# 6. offline helper; its version is a fingerprint of the files, so every new build replaces the old copy
files = ["./", "index.html", "manifest.webmanifest", "icons/icon.svg", "icons/icon-192.png", "icons/icon-512.png",
         "icons/icon-maskable-512.png", "icons/apple-touch-icon.png", "icons/favicon-32.png"]
fingerprint = hashlib.sha256()
for f in files[1:]:
    fingerprint.update((out / f).read_bytes())
version = "terminal-velocity-" + fingerprint.hexdigest()[:12]
sw = """// Terminal Velocity offline helper. Keeps a copy of the app so it works without internet.
// The page itself is always fetched fresh when online (so updates arrive straight away) and the saved copy is
// used only when offline. Nothing is ever sent anywhere: it only handles requests for this app's own files.
const VERSION = "%s";
const FILES = %s;

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
""" % (version, json.dumps(files))
(out / "sw.js").write_text(sw, encoding="utf-8")
(out / ".nojekyll").write_text("", encoding="utf-8")
print("built", out, "| version", version, "| scripts pinned:", len(scripts), "| styles pinned:", len(styles))
