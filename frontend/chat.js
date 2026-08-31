// chat.js — Frontend chat mantiqi (sessiyalar, vazifa (task) tanlash
// oqimi, fayl biriktirish, kod bloklarini render qilish bilan)

const API_URL = "/chat";

const chatEl = document.getElementById("chat");
const messagesEl = document.getElementById("messages");
const landingCardsEl = document.getElementById("landing-cards");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const statusEl = document.getElementById("status");
const sendButton = document.getElementById("send-button");
const thinkingButton = document.getElementById("thinking-button");
const sessionListEl = document.getElementById("session-list");
const rateLimitBadge = document.getElementById("rate-limit-badge");
const fileInput = document.getElementById("file-input");
const attachButton = document.getElementById("attach-button");
const attachedFilesEl = document.getElementById("attached-files");
const limitModal = document.getElementById("limit-modal");
const limitModalMessage = document.getElementById("limit-modal-message");

let pendingFiles = []; // { name, content }
let filesEnabled = false;

function showLimitModal(message) {
  if (!limitModal) {
    alert(message); // eslint-disable-line no-alert -- modal DOM topilmasa ham xabar yo'qolmasin
    return;
  }
  limitModalMessage.textContent = message;
  limitModal.hidden = false;
}
document.getElementById("limit-modal-close")?.addEventListener("click", () => {
  limitModal.hidden = true;
});

/* ---------------------------------------------------------------------
   URL parametrlari: ?session=<id> — loyiha/tarix sahifasidan aniq
   suhbatga o'tish; ?project=<id> — loyiha ichidan "yangi suhbat"
   boshlash (keyingi haqiqiy so'rovga shu loyiha biriktiriladi).
   --------------------------------------------------------------------- */
let pendingProjectId = null;
(function readUrlParams() {
  const params = new URLSearchParams(window.location.search);
  const sessionParam = params.get("session");
  const projectParam = params.get("project");
  if (sessionParam) {
    localStorage.setItem("session_id", sessionParam);
  } else if (projectParam) {
    localStorage.removeItem("session_id");
    pendingProjectId = projectParam;
  }
  if (sessionParam || projectParam) {
    window.history.replaceState({}, "", "index.html");
  }
})();

/* ---------------------------------------------------------------------
   Avtorizatsiya — token bo'lsa har bir so'rovga qo'shamiz
   --------------------------------------------------------------------- */

function authHeaders(extra) {
  const headers = { ...(extra || {}) };
  const token = localStorage.getItem("access_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

/* ---------------------------------------------------------------------
   Sessiya boshqaruvi
   --------------------------------------------------------------------- */

function getSessionId() {
  return localStorage.getItem("session_id");
}

function setSessionId(sessionId) {
  localStorage.setItem("session_id", sessionId);
  const tag = document.getElementById("session-tag");
  if (tag) tag.textContent = "sessiya: " + sessionId.slice(0, 8);
  loadSessions();
}

async function loadHistory() {
  const sessionId = getSessionId();
  if (!sessionId) return;
  try {
    const res = await fetch(`/history/${encodeURIComponent(sessionId)}`, { headers: authHeaders() });
    if (!res.ok) throw new Error();
    const data = await res.json();
    for (const m of data.messages || []) {
      addMessage(m.role, m.content, undefined, m.image_url);
    }
  } catch {
    /* sessiya topilmasa yoki server bilan bog'lanib bo'lmasa, bo'sh chat bilan davom etamiz */
  }
}

async function loadSessions() {
  if (!sessionListEl) return;
  try {
    const res = await fetch("/sessions", { headers: authHeaders() });
    if (!res.ok) throw new Error();
    const data = await res.json();
    renderSessions(data.sessions || []);
  } catch {
    sessionListEl.innerHTML = '<p class="sidebar__sessions-empty">yuklab bo\'lmadi</p>';
  }
}

function renderSessions(sessions) {
  const activeId = getSessionId();
  if (sessions.length === 0) {
    sessionListEl.innerHTML = '<p class="sidebar__sessions-empty">hali suhbat yo\'q</p>';
    return;
  }
  sessionListEl.innerHTML = "";
  for (const s of sessions) {
    const item = document.createElement("div");
    item.className = "session-item" + (s.id === activeId ? " is-active" : "");

    const text = document.createElement("button");
    text.type = "button";
    text.className = "session-item__text";
    text.title = s.preview;

    const preview = document.createElement("span");
    preview.className = "session-item__preview";
    preview.textContent = s.preview || "Bo'sh suhbat";
    text.appendChild(preview);

    if (s.project_name) {
      const tag = document.createElement("span");
      tag.className = "session-item__project-tag";
      tag.textContent = s.project_name;
      text.appendChild(tag);
    }

    text.addEventListener("click", () => {
      localStorage.setItem("session_id", s.id);
      window.location.reload();
    });

    const del = document.createElement("button");
    del.type = "button";
    del.className = "session-item__del";
    del.setAttribute("aria-label", "Sessiyani o'chirish");
    del.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14z"/></svg>';
    del.addEventListener("click", async (e) => {
      e.stopPropagation();
      try {
        await fetch(`/sessions/${encodeURIComponent(s.id)}`, {
          method: "DELETE",
          headers: authHeaders(),
        });
      } catch {
        /* server javob bermasa ham UI'dan olib tashlaymiz */
      }
      if (s.id === activeId) localStorage.removeItem("session_id");
      loadSessions();
      if (s.id === activeId) window.location.reload();
    });

    item.appendChild(text);
    item.appendChild(del);
    sessionListEl.appendChild(item);
  }
}

/* ---------------------------------------------------------------------
   "Chuqur o'ylash" rejimi (input yonidagi alohida tugma)
   --------------------------------------------------------------------- */

if (thinkingButton) {
  const applyThinkingUI = () => {
    thinkingButton.classList.toggle("is-active", localStorage.getItem("thinking_mode") === "true");
  };
  applyThinkingUI();
  thinkingButton.addEventListener("click", () => {
    const next = localStorage.getItem("thinking_mode") !== "true";
    localStorage.setItem("thinking_mode", next ? "true" : "false");
    applyThinkingUI();
  });
}

/* ---------------------------------------------------------------------
   Boshlang'ich (landing) holat: aniq vazifa tanlash oqimi
   --------------------------------------------------------------------- */

// Har bir domenning sarlavha/tanishtiruv matnlari i18n.js lug'atidan
// ("landing.card.<domen>.title"/".intro") o'qiladi — interfeys tiliga qarab
// avtomatik moslashadi.
const DOMAIN_KEYS = ["code", "idea", "image", "research"];
function domainTitle(domain) {
  return window.I18N ? I18N.t(`landing.card.${domain}.title`) : domain;
}
function domainIntro(domain) {
  return window.I18N ? I18N.t(`landing.card.${domain}.intro`) : "";
}

let currentMode = localStorage.getItem("chat_mode") || "auto";
let taskInitialText = null; // markazlashgan maydonga aniq bo'lim tanlanmasdan yozilgan matn

function exitLanding() {
  chatEl?.classList.remove("is-landing");
}

// Foydalanuvchi vazifa kartasini bosganda: bo'lim darhol aniq bo'ladi,
// agent (haqiqiy so'rovsiz) qisqa tanishtiruv va aniqlashtiruvchi savol
// beradi, keyingi xabar esa to'g'ridan-to'g'ri haqiqiy agentga boradi.
function startWithDomain(domain) {
  currentMode = domain;
  localStorage.setItem("chat_mode", currentMode);
  exitLanding();
  addMessage("assistant", domainIntro(domain));
  inputEl.focus();
}

// Foydalanuvchi bo'lim tanlamasdan to'g'ridan-to'g'ri matn yozib
// yuborsa: matnni saqlab qo'yamiz va qaysi bo'limga tegishli ekanini
// tez tugmalar orqali so'raymiz — javob kelgach haqiqiy so'rov ketadi.
function startWithTypedText(text) {
  taskInitialText = text;
  exitLanding();
  const bubble = addMessage("assistant", window.I18N ? I18N.t("landing.typeTextPrompt") : "");
  const chipsWrap = document.createElement("div");
  chipsWrap.className = "domain-chips";
  DOMAIN_KEYS.forEach((key) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "domain-chip";
    chip.textContent = domainTitle(key);
    chip.addEventListener("click", () => {
      chipsWrap.remove();
      currentMode = key;
      localStorage.setItem("chat_mode", currentMode);
      const savedText = taskInitialText;
      taskInitialText = null;
      sendMessage(savedText);
    });
    chipsWrap.appendChild(chip);
  });
  bubble.appendChild(chipsWrap);
}

landingCardsEl?.querySelectorAll(".landing-card").forEach((card) => {
  card.addEventListener("click", () => startWithDomain(card.dataset.domain));
});

/* ---------------------------------------------------------------------
   Cheklov (rate limit) ko'rsatkichi
   --------------------------------------------------------------------- */

async function refreshRateLimit() {
  if (!rateLimitBadge) return;
  try {
    const res = await fetch("/rate-limit/status", { headers: authHeaders() });
    if (!res.ok) {
      rateLimitBadge.hidden = true;
      return;
    }
    const data = await res.json();
    rateLimitBadge.hidden = false;
    rateLimitBadge.textContent = `${data.remaining}/${data.max_requests} so'rov`;
    rateLimitBadge.classList.toggle("is-low", data.remaining <= Math.ceil(data.max_requests * 0.2));
  } catch {
    rateLimitBadge.hidden = true;
  }
}

/* ---------------------------------------------------------------------
   Fayl biriktirish (faqat matn/kod fayllari, kichik hajm)
   --------------------------------------------------------------------- */

const ALLOWED_EXT = [
  ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md",
  ".txt", ".csv", ".yml", ".yaml", ".sql", ".sh", ".java", ".c", ".cpp",
  ".go", ".rs", ".rb", ".php", ".xml", ".docx", ".xlsx",
];
// .docx/.xlsx matn emas — backend (/files/extract) orqali o'qiladi
const SERVER_EXTRACT_EXT = [".docx", ".xlsx"];
const UNSUPPORTED_HINTS = {
  ".doc": "Eskirgan .doc formati qo'llab-quvvatlanmaydi — Word'da \".docx\" sifatida qayta saqlab yuklang.",
  ".xls": "Eskirgan .xls formati qo'llab-quvvatlanmaydi — Excel'da \".xlsx\" sifatida qayta saqlab yuklang.",
};
const MAX_FILE_SIZE = 256 * 1024; // matnli fayllar uchun
const MAX_BINARY_FILE_SIZE = 5 * 1024 * 1024; // .docx/.xlsx uchun

async function probeFilesEnabled() {
  if (!attachButton) return;
  try {
    const res = await fetch("/files/_probe");
    filesEnabled = res.status !== 404;
  } catch {
    filesEnabled = false;
  }
  attachButton.hidden = !filesEnabled;
}

function renderAttachedFiles() {
  if (!attachedFilesEl) return;
  attachedFilesEl.innerHTML = "";
  attachedFilesEl.hidden = pendingFiles.length === 0;
  pendingFiles.forEach((f, idx) => {
    const chip = document.createElement("span");
    chip.className = "file-chip";
    chip.innerHTML = `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg> ${f.name}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", "Faylni olib tashlash");
    remove.addEventListener("click", () => {
      pendingFiles.splice(idx, 1);
      renderAttachedFiles();
    });
    chip.appendChild(remove);
    attachedFilesEl.appendChild(chip);
  });
}

async function extractServerSide(file) {
  const form = new FormData();
  form.append("file", file, file.name);
  const res = await fetch("/files/extract", { method: "POST", headers: authHeaders(), body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Faylni o'qib bo'lmadi.");
  }
  const data = await res.json();
  return data.content;
}

if (attachButton && fileInput) {
  attachButton.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    for (const file of Array.from(fileInput.files || [])) {
      const ext = "." + file.name.split(".").pop().toLowerCase();

      if (UNSUPPORTED_HINTS[ext]) {
        addMessage("system", `"${file.name}": ${UNSUPPORTED_HINTS[ext]}`);
        continue;
      }
      if (!ALLOWED_EXT.includes(ext)) {
        addMessage("system", `"${file.name}" turi qo'llab-quvvatlanmaydi.`);
        continue;
      }

      if (SERVER_EXTRACT_EXT.includes(ext)) {
        if (file.size > MAX_BINARY_FILE_SIZE) {
          addMessage("system", `"${file.name}" juda katta (maksimal 5 MB).`);
          continue;
        }
        try {
          const content = await extractServerSide(file);
          pendingFiles.push({ name: file.name, content });
        } catch (err) {
          addMessage("system", `"${file.name}": ${err.message}`);
        }
        continue;
      }

      if (file.size > MAX_FILE_SIZE) {
        addMessage("system", `"${file.name}" juda katta (maksimal 256 KB).`);
        continue;
      }
      const content = await file.text();
      pendingFiles.push({ name: file.name, content });
    }
    fileInput.value = "";
    renderAttachedFiles();
  });
}

async function uploadFiles(sessionId, files) {
  if (!filesEnabled || !files || files.length === 0) return;
  for (const f of files) {
    try {
      const form = new FormData();
      form.append("file", new Blob([f.content], { type: "text/plain" }), f.name);
      await fetch(`/files/${encodeURIComponent(sessionId)}`, {
        method: "POST",
        headers: authHeaders(),
        body: form,
      });
    } catch {
      /* saqlanmasa ham suhbat davom etadi — fayl mazmuni xabarga qo'shilgan */
    }
  }
}

function buildMessageWithFiles(message, files) {
  if (!files || files.length === 0) return message;
  const attachments = files
    .map((f) => `[Biriktirilgan fayl: ${f.name}]\n\`\`\`\n${f.content.slice(0, 6000)}\n\`\`\``)
    .join("\n\n");
  return `${attachments}\n\n${message}`;
}

/* ---------------------------------------------------------------------
   Xabarlarni chizish + kod bloklari (sintaksis rangi, nusxalash, ishga
   tushirish)
   --------------------------------------------------------------------- */

function renderMessageContent(container, text) {
  const codeFenceRe = /```(\w*)\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;
  let hasCode = false;

  while ((match = codeFenceRe.exec(text)) !== null) {
    hasCode = true;
    if (match.index > lastIndex) {
      renderMarkdownBlock(container, text.slice(lastIndex, match.index));
    }
    container.appendChild(buildCodeBlock(match[1] || "plaintext", match[2]));
    lastIndex = codeFenceRe.lastIndex;
  }
  if (!hasCode) {
    renderMarkdownBlock(container, text);
    return;
  }
  if (lastIndex < text.length) {
    renderMarkdownBlock(container, text.slice(lastIndex));
  }
}

// Kod bloklaridan tashqarida qolgan matnni sodda markdown sifatida chizadi:
// sarlavhalar (# ## ###), **qalin**, *kursiv*, `inline kod`, ro'yxatlar
// (tartibli/tartibsiz) va jadvallar (| ... |). HAR DOIM DOM elementlari
// orqali quriladi (innerHTML bilan xom matn EMAS) — XSS xavfsizligi shu
// tarzda saqlanadi.
function renderMarkdownBlock(container, text) {
  const lines = text.split("\n");
  let i = 0;
  let paragraphBuffer = [];

  function flushParagraph() {
    if (paragraphBuffer.length === 0) return;
    const p = document.createElement("p");
    p.appendChild(parseInlineToFragment(paragraphBuffer.join(" ")));
    container.appendChild(p);
    paragraphBuffer = [];
  }

  while (i < lines.length) {
    const trimmed = lines[i].trim();

    if (trimmed === "") {
      flushParagraph();
      i++;
      continue;
    }

    const headerMatch = trimmed.match(/^(#{1,3})\s+(.*)$/);
    if (headerMatch) {
      flushParagraph();
      const h = document.createElement(`h${headerMatch[1].length}`);
      h.appendChild(parseInlineToFragment(headerMatch[2]));
      container.appendChild(h);
      i++;
      continue;
    }

    // Jadval: "| ... |" qatori, keyingi qatorda "|---|---|" ajratkichi
    if (trimmed.startsWith("|") && lines[i + 1] && /^\|?[\s:|-]+\|?$/.test(lines[i + 1].trim())) {
      flushParagraph();
      const tableLines = [lines[i]];
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      container.appendChild(buildMarkdownTable(tableLines));
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      flushParagraph();
      const ul = document.createElement("ul");
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        const li = document.createElement("li");
        li.appendChild(parseInlineToFragment(lines[i].trim().replace(/^[-*]\s+/, "")));
        ul.appendChild(li);
        i++;
      }
      container.appendChild(ul);
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      flushParagraph();
      const ol = document.createElement("ol");
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        const li = document.createElement("li");
        li.appendChild(parseInlineToFragment(lines[i].trim().replace(/^\d+\.\s+/, "")));
        ol.appendChild(li);
        i++;
      }
      container.appendChild(ol);
      continue;
    }

    paragraphBuffer.push(trimmed);
    i++;
  }
  flushParagraph();
}

function buildMarkdownTable(tableLines) {
  const wrap = document.createElement("div");
  wrap.className = "md-table-wrap";
  const table = document.createElement("table");
  table.className = "md-table";

  const splitRow = (line) =>
    line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  splitRow(tableLines[0]).forEach((cell) => {
    const th = document.createElement("th");
    th.appendChild(parseInlineToFragment(cell));
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (let r = 1; r < tableLines.length; r++) {
    const tr = document.createElement("tr");
    splitRow(tableLines[r]).forEach((cell) => {
      const td = document.createElement("td");
      td.appendChild(parseInlineToFragment(cell));
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);
  return wrap;
}

// **qalin**, *kursiv*, `inline kod` — DOM elementlari orqali (innerHTML'siz)
function parseInlineToFragment(text) {
  const frag = document.createDocumentFragment();
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let lastIndex = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIndex) frag.appendChild(document.createTextNode(text.slice(lastIndex, m.index)));
    const token = m[0];
    if (token.startsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = token.slice(2, -2);
      frag.appendChild(strong);
    } else if (token.startsWith("`")) {
      const code = document.createElement("code");
      code.className = "md-inline-code";
      code.textContent = token.slice(1, -1);
      frag.appendChild(code);
    } else {
      const em = document.createElement("em");
      em.textContent = token.slice(1, -1);
      frag.appendChild(em);
    }
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) frag.appendChild(document.createTextNode(text.slice(lastIndex)));
  return frag;
}

function buildCodeBlock(lang, code) {
  const wrap = document.createElement("div");
  wrap.className = "code-block";

  const header = document.createElement("div");
  header.className = "code-block__header";

  const langLabel = document.createElement("span");
  langLabel.textContent = lang || "code";
  header.appendChild(langLabel);

  const actions = document.createElement("div");
  actions.className = "code-block__actions";

  const outputEl = document.createElement("div");
  outputEl.className = "code-block__output mono";
  outputEl.hidden = true;

  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.textContent = "Nusxalash";
  copyBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(code).then(() => {
      copyBtn.textContent = "✓ Nusxalandi";
      setTimeout(() => (copyBtn.textContent = "Nusxalash"), 1400);
    });
  });
  actions.appendChild(copyBtn);

  if (lang.toLowerCase() === "javascript" || lang.toLowerCase() === "js") {
    const runBtn = document.createElement("button");
    runBtn.type = "button";
    runBtn.textContent = "▶ Ishga tushirish";
    runBtn.title = "Brauzerning xavfsiz (sandboxed) muhitida ishga tushiriladi";
    runBtn.addEventListener("click", () => runJsSandboxed(code, outputEl));
    actions.appendChild(runBtn);
  }

  header.appendChild(actions);
  wrap.appendChild(header);

  const pre = document.createElement("pre");
  const codeEl = document.createElement("code");
  if (lang) codeEl.className = `language-${lang}`;
  codeEl.textContent = code;
  pre.appendChild(codeEl);
  wrap.appendChild(pre);
  wrap.appendChild(outputEl);

  if (window.hljs) {
    try {
      window.hljs.highlightElement(codeEl);
    } catch {
      /* noma'lum til bo'lsa, oddiy matn sifatida qoladi */
    }
  }

  return wrap;
}

// JS kodini asosiy sahifadan butunlay izolyatsiyalangan (sandboxed) iframe
// ichida ishga tushiradi — serverga hech qanday so'rov yuborilmaydi va
// asosiy sahifa DOM/cookie/localStorage'iga kira olmaydi.
function runJsSandboxed(code, outputEl) {
  outputEl.hidden = false;
  outputEl.textContent = "Ishga tushirilmoqda...";

  const iframe = document.createElement("iframe");
  iframe.sandbox = "allow-scripts";
  iframe.style.display = "none";

  const listener = (event) => {
    if (event.source !== iframe.contentWindow) return;
    outputEl.textContent = (event.data.logs || []).join("\n") || "(chiqish yo'q)";
    if (event.data.error) {
      outputEl.textContent += `\nXato: ${event.data.error}`;
    }
    window.removeEventListener("message", listener);
    iframe.remove();
  };
  window.addEventListener("message", listener);

  const srcdoc = `
    <script>
      const logs = [];
      console.log = (...args) => logs.push(args.map(String).join(" "));
      let error = null;
      try {
        ${code}
      } catch (e) {
        error = e.message;
      }
      parent.postMessage({ logs, error }, "*");
    <\/script>
  `;
  iframe.srcdoc = srcdoc;
  document.body.appendChild(iframe);

  setTimeout(() => {
    if (iframe.isConnected) {
      outputEl.textContent = "Vaqt chegarasidan oshdi (cheksiz tsikl bo'lishi mumkin).";
      iframe.remove();
    }
  }, 3000);
}

async function downloadImage(url) {
  try {
    const res = await fetch(url);
    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = "rasm.jpg";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(blobUrl);
  } catch {
    // CORS yoki tarmoq muammosi bo'lsa, kamida yangi tabda ochib beramiz
    window.open(url, "_blank");
  }
}

const INTENT_BADGE_LABELS = {
  code: "● Claude — kod",
  idea: "● Gemini — g'oya",
  image: "● Leonardo — rasm",
  research: "● Gemini Pro — qidiruv",
};

const TOOL_LABELS = {
  run_python_code: "Python kodi ishga tushirilmoqda",
};

function toolHintLabel(name) {
  if (TOOL_LABELS[name]) return TOOL_LABELS[name];
  if (name.startsWith("github_")) return "GitHub bilan ishlamoqda";
  if (name.startsWith("google_docs_")) return "Google Docs bilan ishlamoqda";
  return `"${name}" ishlatilmoqda`;
}

// Oqim (streaming) davomida bo'sh assistent pufakchasini yaratadi — matn
// hali xom holatda (markdown/kod bloklari yo'q, faqat pre-wrap), yakunda
// finalizeStreamingMessage() to'liq render qiladi.
function addStreamingMessage() {
  const bubble = document.createElement("div");
  bubble.className = "message message--assistant is-streaming";

  const contentEl = document.createElement("div");
  contentEl.className = "message__content message__content--raw";
  bubble.appendChild(contentEl);

  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return bubble;
}

function finalizeStreamingMessage(bubble, text, intent, imageUrl) {
  bubble.classList.remove("is-streaming");
  bubble.innerHTML = "";

  if (intent) {
    const badge = document.createElement("span");
    badge.className = `message__badge is-${intent}`;
    badge.textContent = INTENT_BADGE_LABELS[intent] || `● ${intent}`;
    bubble.appendChild(badge);
    bubble.appendChild(document.createElement("br"));
    bubble.dataset.intent = intent;
  }

  const contentEl = document.createElement("div");
  contentEl.className = "message__content";
  renderMessageContent(contentEl, text);
  bubble.appendChild(contentEl);

  if (imageUrl) {
    const imageWrap = document.createElement("div");
    imageWrap.className = "message__image-wrap";

    const img = document.createElement("img");
    img.src = imageUrl;
    img.alt = "Leonardo AI tomonidan generatsiya qilingan rasm";
    img.className = "message__image";
    imageWrap.appendChild(img);

    const downloadBtn = document.createElement("button");
    downloadBtn.type = "button";
    downloadBtn.className = "message__image-download";
    downloadBtn.title = "Rasmni yuklab olish";
    downloadBtn.setAttribute("aria-label", "Rasmni yuklab olish");
    downloadBtn.innerHTML =
      '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
    downloadBtn.addEventListener("click", () => downloadImage(imageUrl));
    imageWrap.appendChild(downloadBtn);

    bubble.appendChild(imageWrap);
  }

  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addMessage(role, text, intent, imageUrl) {
  const bubble = document.createElement("div");
  bubble.className = `message message--${role}`;

  if (role === "assistant" && intent) {
    const badge = document.createElement("span");
    badge.className = `message__badge is-${intent}`;
    badge.textContent = INTENT_BADGE_LABELS[intent] || `● ${intent}`;
    bubble.appendChild(badge);
    bubble.appendChild(document.createElement("br"));
    bubble.dataset.intent = intent;
  }

  const contentEl = document.createElement("div");
  contentEl.className = "message__content";
  renderMessageContent(contentEl, text);
  bubble.appendChild(contentEl);

  if (imageUrl) {
    const imageWrap = document.createElement("div");
    imageWrap.className = "message__image-wrap";

    const img = document.createElement("img");
    img.src = imageUrl;
    img.alt = "Leonardo AI tomonidan generatsiya qilingan rasm";
    img.className = "message__image";
    imageWrap.appendChild(img);

    const downloadBtn = document.createElement("button");
    downloadBtn.type = "button";
    downloadBtn.className = "message__image-download";
    downloadBtn.title = "Rasmni yuklab olish";
    downloadBtn.setAttribute("aria-label", "Rasmni yuklab olish");
    downloadBtn.innerHTML =
      '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
    downloadBtn.addEventListener("click", () => downloadImage(imageUrl));
    imageWrap.appendChild(downloadBtn);

    bubble.appendChild(imageWrap);
  }

  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return bubble;
}

function addTypingIndicator() {
  const bubble = document.createElement("div");
  bubble.className = "message message--assistant";
  bubble.id = "typing-indicator";
  bubble.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return bubble;
}

function removeTypingIndicator() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

function setLoading(isLoading) {
  sendButton.disabled = isLoading;
  inputEl.disabled = isLoading;
  statusEl.textContent = isLoading ? "agent javob yozmoqda..." : "";
  window.AsciiBG?.setActive(isLoading);
}

async function sendMessage(rawMessage) {
  addMessage("user", rawMessage);
  setLoading(true);
  const typingBubble = addTypingIndicator();

  const filesToSend = [...pendingFiles];
  const messageWithFiles = buildMessageWithFiles(rawMessage, filesToSend);
  const thinking = localStorage.getItem("thinking_mode") === "true";
  pendingFiles = [];
  renderAttachedFiles();

  let assistantBubble = null;
  let rawText = "";
  let toolHintEl = null;

  function ensureBubble() {
    if (assistantBubble) return;
    removeTypingIndicator();
    assistantBubble = addStreamingMessage();
  }

  function renderRawText() {
    const contentEl = assistantBubble.querySelector(".message__content--raw");
    contentEl.textContent = rawText;
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function showToolHint(name) {
    ensureBubble();
    if (!toolHintEl) {
      toolHintEl = document.createElement("div");
      toolHintEl.className = "tool-hint";
      assistantBubble.insertBefore(toolHintEl, assistantBubble.firstChild);
    }
    toolHintEl.textContent = `🔧 ${toolHintLabel(name)}...`;
  }

  try {
    const response = await fetch("/chat/stream", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        message: messageWithFiles,
        session_id: getSessionId(),
        mode: currentMode,
        thinking,
        project_id: pendingProjectId,
      }),
    });
    pendingProjectId = null; // faqat sessiya YANGI ochilganda ishlatiladi, bir marta yetarli

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const detail = errorBody.detail;
      if (detail && typeof detail === "object" && detail.message) {
        showLimitModal(detail.message);
        throw new Error(detail.message);
      }
      throw new Error(detail || `Server xatosi: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalData = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const rawEvent of events) {
        const line = rawEvent.trim();
        if (!line.startsWith("data:")) continue;
        let evt;
        try {
          evt = JSON.parse(line.slice(5).trim());
        } catch {
          continue;
        }

        if (evt.error) {
          throw new Error(evt.error);
        } else if (evt.tool) {
          showToolHint(evt.tool);
        } else if (typeof evt.delta === "string") {
          ensureBubble();
          if (toolHintEl) {
            toolHintEl.remove();
            toolHintEl = null;
          }
          rawText += evt.delta;
          renderRawText();
        } else if (evt.blocked) {
          ensureBubble();
          if (toolHintEl) {
            toolHintEl.remove();
            toolHintEl = null;
          }
          rawText = evt.reply;
          renderRawText();
        } else if (evt.done) {
          finalData = evt;
        }
      }
    }

    if (!finalData) throw new Error("Server javobni yakunlamadi.");

    setSessionId(finalData.session_id);
    uploadFiles(finalData.session_id, filesToSend);
    removeTypingIndicator();

    if (assistantBubble) {
      finalizeStreamingMessage(assistantBubble, rawText, finalData.intent, finalData.image_url);
    } else {
      addMessage("assistant", rawText, finalData.intent, finalData.image_url);
    }
    refreshRateLimit();

    if (window.speakText && localStorage.getItem("voice_enabled") === "true" && rawText) {
      window.speakText(rawText);
    }
  } catch (error) {
    console.error(error);
    removeTypingIndicator();
    assistantBubble?.remove?.();
    addMessage(
      "system",
      error.message || "Server bilan bog'lanib bo'lmadi. Backend ishga tushirilganiga ishonch hosil qiling."
    );
  } finally {
    setLoading(false);
    typingBubble?.remove?.();
  }
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;
  inputEl.value = "";
  inputEl.style.height = "auto";

  // Landing holatida (hali aniq bo'lim tanlanmagan) to'g'ridan-to'g'ri
  // yozilgan matn: haqiqiy so'rov o'rniga avval bo'limni aniqlaymiz.
  if (chatEl?.classList.contains("is-landing")) {
    startWithTypedText(message);
    return;
  }
  sendMessage(message);
});

inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});

inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = `${inputEl.scrollHeight}px`;
});

// Ishga tushirish
// Sessiya mavjud bo'lsa (qaytgan foydalanuvchi), landing holatini darhol
// yashiramiz — aks holda tarix yuklangunga qadar bir lahza "yangi vazifa"
// ekrani ko'rinib ketishi mumkin. Tarix bo'sh chiqsa, landing'ga qaytamiz.
if (getSessionId()) exitLanding();
loadHistory().then(() => {
  if (messagesEl.children.length === 0) {
    chatEl?.classList.add("is-landing");
  } else {
    exitLanding();
  }
});
loadSessions();
refreshRateLimit();
probeFilesEnabled();
