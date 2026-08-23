// chat.js — Frontend chat mantiqi (sessiyalar, model tanlovi, fayl
// biriktirish, kod bloklarini render qilish bilan)

const API_URL = "/chat";

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const statusEl = document.getElementById("status");
const sendButton = document.getElementById("send-button");
const modelButton = document.getElementById("model-button");
const modelButtonLabel = document.getElementById("model-button-label");
const modelPopover = document.getElementById("model-popover");
const thinkingToggle = document.getElementById("thinking-toggle");
const sessionListEl = document.getElementById("session-list");
const rateLimitBadge = document.getElementById("rate-limit-badge");
const fileInput = document.getElementById("file-input");
const attachButton = document.getElementById("attach-button");
const attachedFilesEl = document.getElementById("attached-files");

let pendingFiles = []; // { name, content }
let filesEnabled = false;

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
      addMessage(m.role, m.content);
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
    sessionListEl.innerHTML = '<p class="sidebar__sessions-empty mono">yuklab bo\'lmadi</p>';
  }
}

function renderSessions(sessions) {
  const activeId = getSessionId();
  if (sessions.length === 0) {
    sessionListEl.innerHTML = '<p class="sidebar__sessions-empty mono">hali suhbat yo\'q</p>';
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
    text.textContent = s.preview || "Bo'sh suhbat";
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
   Model picker (input ichida) + "Chuqur o'ylash" rejimi
   --------------------------------------------------------------------- */

const MODE_LABELS = {
  auto: "avto",
  code: "claude",
  idea: "gemini",
  image: "leonardo",
  research: "gemini pro",
};
let currentMode = localStorage.getItem("chat_mode") || "auto";

function applyModeUI() {
  if (modelButtonLabel) modelButtonLabel.textContent = MODE_LABELS[currentMode] || "avto";
  document.querySelectorAll(".model-popover__option").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.mode === currentMode);
  });
}

if (modelButton && modelPopover) {
  modelButton.addEventListener("click", (e) => {
    e.stopPropagation();
    const willOpen = modelPopover.hidden;
    modelPopover.hidden = !willOpen;
    modelButton.classList.toggle("is-open", willOpen);
  });

  document.querySelectorAll(".model-popover__option").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentMode = btn.dataset.mode;
      localStorage.setItem("chat_mode", currentMode);
      applyModeUI();
      modelPopover.hidden = true;
      modelButton.classList.remove("is-open");
    });
  });

  document.addEventListener("click", (e) => {
    if (!modelPopover.hidden && !modelPopover.contains(e.target) && e.target !== modelButton) {
      modelPopover.hidden = true;
      modelButton.classList.remove("is-open");
    }
  });

  applyModeUI();
}

if (thinkingToggle) {
  thinkingToggle.checked = localStorage.getItem("thinking_mode") === "true";
  thinkingToggle.addEventListener("change", () => {
    localStorage.setItem("thinking_mode", thinkingToggle.checked ? "true" : "false");
  });
  // Popover ichidagi bosishlar tashqi "yopish" listeneriga tegmasin
  thinkingToggle.closest(".model-popover__toggle")?.addEventListener("click", (e) => e.stopPropagation());
}

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
  ".go", ".rs", ".rb", ".php", ".xml",
];
const MAX_FILE_SIZE = 256 * 1024;

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
    chip.className = "file-chip mono";
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

if (attachButton && fileInput) {
  attachButton.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    for (const file of Array.from(fileInput.files || [])) {
      const ext = "." + file.name.split(".").pop().toLowerCase();
      if (!ALLOWED_EXT.includes(ext)) {
        addMessage("system", `"${file.name}" turi qo'llab-quvvatlanmaydi (faqat matn/kod fayllari).`);
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
  header.className = "code-block__header mono";

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

const INTENT_BADGE_LABELS = {
  code: "● claude — kod",
  idea: "● gemini — g'oya",
  image: "● leonardo — rasm",
  research: "● gemini pro — qidiruv",
};

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
    const img = document.createElement("img");
    img.src = imageUrl;
    img.alt = "Leonardo AI tomonidan generatsiya qilingan rasm";
    img.className = "message__image";
    bubble.appendChild(img);
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
  statusEl.textContent = isLoading ? "> agent javob yozmoqda..." : "";
  window.AsciiBG?.setActive(isLoading);
}

async function sendMessage(rawMessage) {
  addMessage("user", rawMessage);
  setLoading(true);
  const typingBubble = addTypingIndicator();

  const filesToSend = [...pendingFiles];
  const messageWithFiles = buildMessageWithFiles(rawMessage, filesToSend);
  const thinking = thinkingToggle ? thinkingToggle.checked : false;
  pendingFiles = [];
  renderAttachedFiles();

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        message: messageWithFiles,
        session_id: getSessionId(),
        mode: currentMode,
        thinking,
      }),
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      throw new Error(errorBody.detail || `Server xatosi: ${response.status}`);
    }

    const data = await response.json();
    setSessionId(data.session_id);
    uploadFiles(data.session_id, filesToSend);
    removeTypingIndicator();
    addMessage("assistant", data.reply, data.intent, data.image_url);
    refreshRateLimit();

    if (window.speakText && localStorage.getItem("voice_enabled") === "true") {
      window.speakText(data.reply);
    }
  } catch (error) {
    console.error(error);
    removeTypingIndicator();
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
loadHistory();
loadSessions();
refreshRateLimit();
probeFilesEnabled();
