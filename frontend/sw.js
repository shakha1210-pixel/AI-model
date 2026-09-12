// sw.js — Apeiron uchun oddiy PWA service worker.
//
// MAQSAD: bu birinchi navbatda "o'rnatiladigan ilova" mezonini
// qanoatlantirish uchun kerak (Chrome/Android PWA/TWA talab qiladi),
// haqiqiy offline-suhbat imkoniyati emas — chunki chat/AI javoblari
// tabiatan doim jonli serverga bog'liq.
//
// STRATEGIYA: tarmoq-birinchi (network-first). Onlayn bo'lganda foydalanuvchi
// HAR DOIM eng yangi faylni oladi (eski keshlangan JS/CSS qolib ketishi —
// bu loyihada avval haqiqiy muammo bo'lgan!). Faqat tarmoq butunlay
// ishlamay qolganda (masalan signal yo'q joyda) keshdagi nusxaga
// murojaat qilinadi. /chat, /auth va h.k. kabi API so'rovlari HECH
// QACHON keshlanmaydi — ular doim jonli bo'lishi shart.

const CACHE_NAME = "apeiron-static-v1";

const API_PATH_RE = /^\/(chat|auth|history|sessions|files|projects|google-docs|rate-limit|health)(\/|$)/;

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (API_PATH_RE.test(url.pathname)) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response && response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});
