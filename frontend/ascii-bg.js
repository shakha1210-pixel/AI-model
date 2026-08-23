// ascii-bg.js — Orqa fon: shaxsiy albomdan (46 surat) haqiqiy fotosurat,
// glow + blur + yumshoq parallaks orqali "parda ortidan chiqib turgan"
// 3D chuqurlik hissi beriladi. (Eslatma: bu yerda ASCII-matn konversiyasi
// yo'q — sinab ko'rilgan, lekin keraksiz murakkablik va sifat yo'qotish
// sabab, oddiy <img> + CSS effektlariga qaytildi.)
//
// Manifest: assets/album-manifest.json — [{id, file, aspect}, ...]
// Haqiqiy suratlar: assets/album/*.jpg (fon uchun, ~1600px)
// Kichik nusxalar: assets/album-thumbs/*.jpg (settings.html tanlov paneli uchun)
//
// Tanlov rejimi sozlamalar sahifasidan boshqariladi (localStorage: bg_mode):
//   "random"     — sessiya davomida bitta tasodifiy surat
//   "sequential" — har yangi sessiyada albomdagi navbatdagi surat
//   "choice"     — foydalanuvchi settings.html'da tanlagan aniq surat
//
// window.AsciiBG.setActive(true/false) — chat.js shu orqali agent javob
// yozayotganda (typing indikatori faol vaqtida) chaqiradi: glow kuchayadi,
// blur pasayadi.
//
// Bu skript BARCHA sahifalarda ulangan (index/settings/history/login/register) —
// shu sabab fon surat chat oynasida ham, sozlamalar menyusida ham bir xil
// tizim orqali, bir xil tanlangan surat bilan ko'rinadi.

(function () {
  "use strict";

  const MANIFEST_URL = "assets/album-manifest.json";
  const REDUCE_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let manifest = null;
  let layer, img;
  let mouseX = 0, mouseY = 0, curX = 0, curY = 0;
  let t = 0;

  // ---------- Tanlov mantiqi ----------
  function getMode() {
    const m = localStorage.getItem("bg_mode") || "random";
    return m === "sequential" ? "sequential" : "random";
  }

  function pickIndex(len) {
    const mode = getMode();

    if (mode === "sequential") {
      let n = parseInt(localStorage.getItem("bg_seq_n") || "0", 10);
      if (Number.isNaN(n)) n = 0;
      const idx = n % len;
      if (!sessionStorage.getItem("bg_seq_consumed")) {
        localStorage.setItem("bg_seq_n", String(n + 1));
        sessionStorage.setItem("bg_seq_consumed", "1");
      }
      return idx;
    }

    let idx = sessionStorage.getItem("bg_random_idx");
    if (idx === null || Number(idx) >= len) {
      idx = Math.floor(Math.random() * len);
      sessionStorage.setItem("bg_random_idx", String(idx));
    }
    return Number(idx);
  }

  // ---------- Yumshoq parallaks + "nafas olish" drift ----------
  function tick() {
    t += 0.0035;
    curX += (mouseX - curX) * 0.03;
    curY += (mouseY - curY) * 0.03;
    const driftX = Math.sin(t) * 10;
    const driftY = Math.cos(t * 0.85) * 6;
    const px = curX * 14 + driftX;
    const py = curY * 9 + driftY;
    img.style.setProperty("--offset-x", px.toFixed(2) + "px");
    img.style.setProperty("--offset-y", py.toFixed(2) + "px");
    requestAnimationFrame(tick);
  }

  function onMouseMove(e) {
    mouseX = (e.clientX / window.innerWidth) * 2 - 1;
    mouseY = (e.clientY / window.innerHeight) * 2 - 1;
  }

  async function init() {
    layer = document.createElement("div");
    layer.className = "ascii-bg";
    layer.id = "ascii-bg";
    layer.setAttribute("aria-hidden", "true");

    img = document.createElement("img");
    img.className = "ascii-bg__img";
    img.alt = "";
    img.decoding = "async";
    layer.appendChild(img);
    document.body.insertBefore(layer, document.body.firstChild);

    try {
      const res = await fetch(MANIFEST_URL, { cache: "force-cache" });
      manifest = await res.json();
    } catch (err) {
      console.warn("Fon albomi ro'yxati yuklanmadi:", err);
      layer.remove();
      return;
    }
    if (!Array.isArray(manifest) || manifest.length === 0) return;

    const idx = pickIndex(manifest.length);
    img.src = manifest[idx].file;

    if (!REDUCE_MOTION) {
      window.addEventListener("mousemove", onMouseMove, { passive: true });
      requestAnimationFrame(tick);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.AsciiBG = {
    setActive(active) {
      if (layer) layer.classList.toggle("is-active", !!active);
    },
  };
})();
