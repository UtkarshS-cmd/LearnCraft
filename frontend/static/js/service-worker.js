const CACHE_NAME = 'learncraft-shell-v3';
const APP_ASSETS = [
  '/offline',
  '/static/manifest.webmanifest',
  '/static/css/design-system.css',
  '/static/css/app.css',
  '/static/js/app.js',
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
  '/static/sandbox-games/physics/js/storage.js'
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
          return key !== CACHE_NAME;
        }).map(function (key) {
          return caches.delete(key);
        })
      );
    }).then(function () {
      return self.clients.claim();
    })
  );
});

self.addEventListener('fetch', function (event) {
  var request = event.request;
  var url = new URL(request.url);

  // Only handle same-origin GET requests
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

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
  // serve that same interface from the shell cache when offline.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).then(function (response) {
        if (response && response.status === 200) {
          var copy = response.clone();
          caches.open(CACHE_NAME).then(function (cache) {
            cache.put(request, copy);
          });
        }
        return response;
      }).catch(function () {
        return caches.match(request).then(function (cachedPage) {
          if (cachedPage) return cachedPage;
          return caches.match('/home').then(function (homePage) {
            return caches.match('/offline').then(function (fallback) {
              return homePage || fallback || new Response(
                '<!DOCTYPE html><html><head><title>Offline</title></head><body><h1>Offline</h1><p>LearnCraft offline shell is active.</p><a href="/offline">Offline dashboard</a></body></html>',
                { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
              );
            });
          });
        });
      })
    );
  }
});
