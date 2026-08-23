// theme.js — Ko'rinish sozlamalari boshqaruvi (barcha sahifalar uchun umumiy)
//
// theme-init.js (inline, <head> ichida) sahifa chizilishidan oldin barcha
// data-* atributlarni o'rnatadi (flash bo'lmasligi uchun). Bu fayl esa
// Sozlamalar sahifasidagi tugmalarni ishga tushiradi va o'zgarishlarni
// saqlaydi: tema (dark/light), aksent rang, shrift, matritsa uslubi.

(function () {
  const KEYS = { theme: "theme", accent: "accent", font: "font" };

  function apply(attr, value, storageKey) {
    document.documentElement.setAttribute(attr, value);
    if (storageKey) localStorage.setItem(storageKey, value);
  }

  function syncHljsTheme(theme) {
    const link = document.getElementById("hljs-theme");
    if (!link) return;
    link.href =
      theme === "light"
        ? "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-light.min.css"
        : "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/base16/tomorrow-night.min.css";
  }

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") || "dark";
  }

  function syncActivePills() {
    const theme = document.documentElement.getAttribute("data-theme");
    const accent = document.documentElement.getAttribute("data-accent") || "teal";
    const font = document.documentElement.getAttribute("data-font") || "sans";
    const themeStored = localStorage.getItem(KEYS.theme);

    document.querySelectorAll("[data-theme-pill]").forEach((el) =>
      el.classList.toggle(
        "is-active",
        themeStored ? el.dataset.themePill === theme : el.dataset.themePill === "system"
      )
    );
    document.querySelectorAll("[data-accent-pill]").forEach((el) =>
      el.classList.toggle("is-active", el.dataset.accentPill === accent)
    );
    document.querySelectorAll("[data-font-pill]").forEach((el) =>
      el.classList.toggle("is-active", el.dataset.fontPill === font)
    );
    document
      .querySelectorAll("[data-theme-toggle]")
      .forEach((el) => el.setAttribute("aria-checked", theme === "light" ? "true" : "false"));
  }

  document.addEventListener("DOMContentLoaded", () => {
    syncHljsTheme(currentTheme());
    syncActivePills();

    // Dark/Light tez almashtirish tugmasi (masalan auth sahifalarida)
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const next = currentTheme() === "dark" ? "light" : "dark";
        apply("data-theme", next, KEYS.theme);
        syncHljsTheme(next);
        syncActivePills();
      });
    });

    // Sozlamalar: tema (dark/light/tizim)
    document.querySelectorAll("[data-theme-pill]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const choice = btn.dataset.themePill;
        if (choice === "system") {
          localStorage.removeItem(KEYS.theme);
          const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
          document.documentElement.setAttribute("data-theme", prefersLight ? "light" : "dark");
        } else {
          apply("data-theme", choice, KEYS.theme);
        }
        syncHljsTheme(currentTheme());
        syncActivePills();
      });
    });

    // Sozlamalar: aksent rang
    document.querySelectorAll("[data-accent-pill]").forEach((btn) => {
      btn.addEventListener("click", () => {
        apply("data-accent", btn.dataset.accentPill, KEYS.accent);
        syncActivePills();
      });
    });

    // Sozlamalar: shrift
    document.querySelectorAll("[data-font-pill]").forEach((btn) => {
      btn.addEventListener("click", () => {
        apply("data-font", btn.dataset.fontPill, KEYS.font);
        syncActivePills();
      });
    });

    // Hisob popover (yon panel pastida)
    const accountBtn = document.getElementById("account-btn");
    const accountPopover = document.getElementById("account-popover");
    if (accountBtn && accountPopover) {
      accountBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        accountPopover.classList.toggle("is-open");
      });
      document.addEventListener("click", (e) => {
        if (!accountPopover.contains(e.target) && e.target !== accountBtn) {
          accountPopover.classList.remove("is-open");
        }
      });
    }
  });
})();
