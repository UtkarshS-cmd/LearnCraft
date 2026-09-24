const CACHE_NAME = 'learncraft-shell-v4';
const PRIVATE_CACHE = 'learncraft-private-v1';
const APP_ASSETS = [
  '/offline',
  '/static/manifest.webmanifest',
  '/static/css/design-system.css',
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/external-links.js',
  '/static/js/sandbox-engine.js',
  '/static/js/offline-store.js',
  '/static/sandbox-games/math/index.html',
  '/static/sandbox-games/math/css/style.css',
  '/static/sandbox-games/math/js/game.js',
  '/static/sandbox-games/curriculum/index.html',
  '/static/sandbox-games/physics/index.html',
  '/static/sandbox-games/physics/css/style.css',
  '/static/sandbox-games/physics/js/app.js',
  '/static/sandbox-games/physics/js/games.js',
  '/static/sandbox-games/physics/js/physics.js',
  '/static/sandbox-games/physics/js/simulations.js',
  '/static/sandbox-games/physics/js/storage.js',
  '/static/sandbox-games/circuits/index.html',
  '/static/sandbox-games/circuits/css/style.css',
  '/static/sandbox-games/circuits/js/circuit.js',
  '/static/sandbox-games/coding/index.html',
  '/static/sandbox-games/coding/css/style.css',
  '/static/sandbox-games/coding/js/game.js'
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function (cache) {
        return Promise.all(
          APP_ASSETS.map(function (url) {
            return fetch(url, { cache: 'no-cache' })
              .then(function (response) {
                if (response.ok) {
                  return cache.put(url, response);
                }
              })
              .catch(function () {
                // Individual asset failure should not block entire SW installation
              });
          })
        );
      })
      .then(function () {
        return self.skipWaiting();
      })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (key) {
          return key !== CACHE_NAME && key !== PRIVATE_CACHE;
        }).map(function (key) {
          return caches.delete(key);
        })
      );
    }).then(function () {
      return self.clients.claim();
    })
  );
});

function isAuthPage(path) {
  return path === '/login' || path === '/register' || path.indexOf('/auth/') === 0;
}

self.addEventListener('fetch', function (event) {
  var request = event.request;
  var url = new URL(request.url);

  // Logout round-trips purge the private page cache so a signed-out device can
  // never replay another account's authenticated HTML from the service worker.
  if (request.method === 'POST' && url.origin === self.location.origin &&
      (url.pathname === '/logout' || url.pathname === '/auth/logout')) {
    event.respondWith(
      fetch(request).then(function (response) {
        return caches.delete(PRIVATE_CACHE).then(function () {
          return response;
        });
      })
    );
    return;
  }

  // Only handle same-origin GET requests
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // Auth pages must never be cached: they render before sign-in.
  if (isAuthPage(url.pathname)) return;

  // Never cache authenticated/private API responses
  if (url.pathname.indexOf('/api/') === 0 || url.pathname.indexOf('/auth/') === 0) {
    return;
  }

  // Static assets: cache-first with network revalidation
  if (url.pathname.indexOf('/static/') === 0) {
    event.respondWith(
      caches.match(request).then(function (cached) {
        var fetchPromise = fetch(request).then(function (response) {
          if (response && response.status === 200) {
            var copy = response.clone();
            caches.open(CACHE_NAME).then(function (cache) {
              cache.put(request, copy);
            });
          }
          return response;
        }).catch(function () {
          return cached;
        });

        return cached || fetchPromise;
      })
    );
    return;
  }

  // Navigation requests: refresh the last visited interface when online, then
  // serve that same interface from the private page cache when offline.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).then(function (response) {
        if (response && response.status === 200) {
          var finalPath = response.url ? new URL(response.url).pathname : url.pathname;
          // Private page HTML lives in its own cache (never the shared asset
          // cache) so that a sign-out can purge every stored page at once.
          if (!isAuthPage(finalPath)) {
            var copy = response.clone();
            caches.open(PRIVATE_CACHE).then(function (cache) {
              cache.put(request, copy);
            });
          }
        }
        return response;
      }).catch(function () {
        return caches.match(request).then(function (cachedPage) {
          if (cachedPage) return cachedPage;
          return caches.match('/offline').then(function (fallback) {
            return fallback || new Response(
              '<!DOCTYPE html><html><head><title>Offline</title></head><body><h1>Offline</h1><p>LearnCraft offline shell is active.</p><a href="/offline">Offline dashboard</a></body></html>',
              { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
            );
          });
        });
      })
    );
  }
});
