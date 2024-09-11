// Install service worker and cache necessary resources
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open('qr-wallet-cache').then(cache => {
      return cache.addAll([
        '/index.html',
        '/manifest.json',
        '/service-worker.js',
        '/icon-192.png',
        '/icon-512.png',
        'https://unpkg.com/html5-qrcode/minified/html5-qrcode.min.js'
      ]);
    })
  );
  console.log("Service Worker installed and resources cached.");
});

// Fetch resources from cache or network
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      return cachedResponse || fetch(event.request);
    })
  );
});
