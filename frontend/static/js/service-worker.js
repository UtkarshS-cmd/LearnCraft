const CACHE_NAME = 'learncraft-shell-v1';
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
      .then(function (cache) { return cache.addAll(APP_ASSETS); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (key) {
        return key !== CACHE_NAME;
      }).map(function (key) {
        return caches.delete(key);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  var request = event.request;
  var url = new URL(request.url);

  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  if (url.pathname.indexOf('/static/') === 0) {
    event.respondWith(
      caches.match(request).then(function (cached) {
        return cached || fetch(request).then(function (response) {
          if (response.ok) {
            var copy = response.clone();
            caches.open(CACHE_NAME).then(function (cache) { cache.put(request, copy); });
          }
          return response;
        });
      })
    );
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(function () {
        return caches.match('/offline');
      })
    );
  }
});
