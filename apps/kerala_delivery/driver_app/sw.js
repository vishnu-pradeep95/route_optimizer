/**
 * Service Worker for Kerala LPG Delivery Driver App
 *
 * Why a service worker?
 * Kerala mobile data is patchy — drivers move through areas with no signal.
 * The app MUST work offline once the route is loaded. This service worker:
 * 1. Caches the app shell (HTML/CSS/JS) on install so it loads without network
 * 2. Caches Leaflet map library so the map view works offline
 * 3. Uses a cache-first strategy for static assets, network-first for API calls
 *
 * Offline design:
 * - Route data is cached in localStorage by the app JS (not here)
 * - Status updates (delivered/failed) are queued in localStorage and replayed
 *   when connectivity returns
 * - Map tiles won't load offline (too large to pre-cache), but the list view
 *   and navigation buttons still work
 *
 * See: https://web.dev/articles/service-worker-lifecycle
 */

// Bump this version string to force re-caching after a deploy.
// The browser detects the byte-level change in sw.js and triggers the
// install event, which re-caches everything.
const CACHE_VERSION = 'v4';
const CACHE_NAME = `lpg-driver-${CACHE_VERSION}`;

// App shell: files needed for the app to render without network.
// These are pre-cached during the install event.
const APP_SHELL = [
    './',
    './index.html',
    './manifest.json',
    './icon-192.png',
    './icon-512.png',
    // Leaflet library — pinned version to avoid CDN dependency at runtime
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
    // Google Fonts CSS — pre-cache the stylesheet so font-face declarations
    // are available offline. The actual .woff2 files are fetched lazily and
    // cached by the network-first strategy below. If fonts fail to load,
    // the CSS font stack falls back to system fonts (Outfit → system sans,
    // JetBrains Mono → Courier New).
    'https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap',
];

// ============================================================
// Install: pre-cache the app shell
// ============================================================
self.addEventListener('install', (event) => {
    // skipWaiting() activates new SW immediately instead of waiting for
    // all tabs to close. Acceptable here because the app is a single page
    // and route data is in localStorage, not in the SW cache.
    self.skipWaiting();

    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] Pre-caching app shell');
            // Cache each resource individually so a single CDN failure
            // (e.g., unpkg down) doesn't prevent the entire SW from installing.
            // Local files (index.html, manifest.json) will always succeed;
            // Leaflet CDN files cache opportunistically.
            return Promise.allSettled(
                APP_SHELL.map((url) => cache.add(url).catch((err) => {
                    console.warn('[SW] Failed to cache:', url, err.message);
                }))
            );
        })
    );
});

// ============================================================
// Activate: clean up old caches from previous versions
// ============================================================
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys
                    .filter((key) => key.startsWith('lpg-driver-') && key !== CACHE_NAME)
                    .map((key) => {
                        console.log('[SW] Removing old cache:', key);
                        return caches.delete(key);
                    })
            );
        }).then(() => {
            // Claim all open clients immediately so the new SW controls
            // pages that were loaded before the update.
            return self.clients.claim();
        })
    );
});

// ============================================================
// Fetch: intercept network requests
// ============================================================
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // API calls: network-first with no cache fallback.
    // Route data is cached in localStorage by the app JS, not here.
    // Status updates are queued in localStorage when offline.
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request).catch(() => {
                // Return a simple offline indicator for API calls.
                // The app JS handles offline logic (localStorage queue).
                return new Response(
                    JSON.stringify({ error: 'offline', message: 'No network connection' }),
                    {
                        status: 503,
                        headers: { 'Content-Type': 'application/json' },
                    }
                );
            })
        );
        return;
    }

    // Map tiles: network-first, cache successful responses for future offline use.
    // We can't pre-cache all tiles (too many), but once the driver views the map
    // for their route area, those tiles become available offline.
    if (url.hostname.includes('tile.openstreetmap.org')) {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    // Clone the response — one for cache, one for the browser
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                    return response;
                })
                .catch(() => caches.match(event.request))
        );
        return;
    }

    // Everything else (app shell, Leaflet CDN): cache-first.
    // Falls back to network if not cached (shouldn't happen after install).
    event.respondWith(
        caches.match(event.request).then((cached) => {
            return cached || fetch(event.request).then((response) => {
                // Opportunistically cache new static resources
                const clone = response.clone();
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                return response;
            });
        })
    );
});
