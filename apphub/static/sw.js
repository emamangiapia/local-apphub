/* Local AppHub: caches only public static assets. Private API responses are never stored. */
"use strict";

const CACHE_NAME = "local-apphub-static-v0.5.0";
const CACHE_PREFIX = "local-apphub-static-";
const OFFLINE_PAGE = "/offline.html";
const PUBLIC_ASSETS = new Set([
  OFFLINE_PAGE, "/favicon.svg", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png",
  "/offline.css", "/style.css", "/pixel.css", "/liquid.css", "/theme-init.js", "/app.js", "/mascot.svg",
  "/manifest.webmanifest",
]);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll([OFFLINE_PAGE, "/offline.css", "/favicon.svg", "/icon-192.png"]))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
        .map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    // Never cache the authenticated dashboard, credentials or private user content.
    event.respondWith(fetch(request).catch(async () => (await caches.match(OFFLINE_PAGE)) || Response.error()));
    return;
  }

  if (!PUBLIC_ASSETS.has(url.pathname)) return;
  event.respondWith(fetch(request).then((response) => {
    if (response.ok) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.put(request, copy)));
    }
    return response;
  }).catch(async () => (await caches.match(request)) || Response.error()));
});
