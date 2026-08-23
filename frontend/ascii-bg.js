// ascii-bg.js — Orqa fon: sof CSS asosidagi nozik "glow" effekti (surat yo'q,
// klassik va neytral ko'rinish uchun).
//
// window.AsciiBG.setActive(true/false) — chat.js shu orqali agent javob
// yozayotganda (typing indikatori faol vaqtida) chaqiradi: glow kuchayadi.
//
// Bu skript BARCHA sahifalarda ulangan (index/settings/history/login/register).

(function () {
  "use strict";

  const REDUCE_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let layer;

  function init() {
    layer = document.createElement("div");
    layer.className = "ascii-bg";
    layer.id = "ascii-bg";
    layer.setAttribute("aria-hidden", "true");

    const glow = document.createElement("div");
    glow.className = "ascii-bg__glow";
    layer.appendChild(glow);

    document.body.insertBefore(layer, document.body.firstChild);

    if (REDUCE_MOTION) layer.classList.add("is-static");
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
