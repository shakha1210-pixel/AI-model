// auth-fetch.js — Himoyalangan (auth talab qiluvchi) so'rovlar uchun
// umumiy yordamchi. Server 401 qaytarganda (token yo'q, eskirgan yoki
// yaroqsiz — JWT 24 soatdan keyin tugaydi) eskirgan tokenni tozalab,
// foydalanuvchini avtomatik login.html'ga qaytaradi — aks holda
// foydalanuvchi hech narsa ishlamaydigan, tushunarsiz holatda qolib
// ketardi (masalan "Mehmon" bo'lib ko'rinib, hech qanday tugma
// javob bermasligi).
//
// Barcha himoyalangan sahifalarda (index/settings/projects/history)
// ulanadi.

(function () {
  "use strict";

  function authHeaders(extra) {
    const headers = { ...(extra || {}) };
    const token = localStorage.getItem("access_token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return headers;
  }

  function goToLogin() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_name");
    localStorage.removeItem("user_email");
    window.location.href = "login.html";
  }

  async function authFetch(path, options) {
    const opts = { ...(options || {}) };
    opts.headers = authHeaders(opts.headers);
    const res = await fetch(path, opts);
    if (res.status === 401) {
      goToLogin();
      // Sahifa allaqachon boshqa manzilga ketmoqda — chaqiruvchi kod
      // javobni qayta ishlashga urinib xato chiqarmasin uchun promise
      // ataylab hech qachon hal qilinmaydi.
      return new Promise(() => {});
    }
    return res;
  }

  window.AuthFetch = { authHeaders, authFetch, goToLogin };
})();
