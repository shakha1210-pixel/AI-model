// register-sw.js — PWA service worker'ni ro'yxatdan o'tkazadi (barcha
// sahifalarda ulangan). Eski brauzerlarda serviceWorker mavjud
// bo'lmasligi mumkin — shu holatda jimgina o'tkazib yuboriladi.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
