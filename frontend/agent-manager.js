// agent-manager.js — tenant-scoped Agent Builder UI.
(function () {
  "use strict";

  const form = document.getElementById("agent-form");
  if (!form || !window.AuthFetch) return;

  const authFetch = window.AuthFetch.authFetch;
  const connectionSelect = document.getElementById("agent-connection");
  const agentList = document.getElementById("agent-list");
  const saveButton = document.getElementById("agent-save-btn");
  const cancelButton = document.getElementById("agent-cancel-btn");
  const statusEl = document.getElementById("agent-form-status");
  const refreshButton = document.getElementById("agent-refresh-btn");
  const t = (key) => window.I18N ? window.I18N.t(key) : key;
  const agentsPath = "/api/workspace/agents";
  const connectionsPath = "/api/workspace/connections";
  const fields = {
    name: document.getElementById("agent-name"),
    description: document.getElementById("agent-description"),
    model: document.getElementById("agent-model"),
    prompt: document.getElementById("agent-prompt"),
    temperature: document.getElementById("agent-temperature"),
    maxTokens: document.getElementById("agent-max-tokens"),
    active: document.getElementById("agent-active"),
  };
  const permissionInputs = Array.from(
    form.querySelectorAll(".agent-builder__permissions input[type=checkbox]")
  );
  const agentsById = new Map();
  let editingId = null;

  function setStatus(element, message, kind) {
    element.textContent = message || "";
    element.dataset.state = kind || "";
  }

  async function readError(response) {
    const data = await response.json().catch(() => ({}));
    if (typeof data.detail === "string") return data.detail;
    if (data.detail && typeof data.detail.message === "string") return data.detail.message;
    return t("settings.agents.requestFailed");
  }

  function selectedPermissions() {
    return permissionInputs.filter((input) => input.checked).map((input) => input.value);
  }

  function resetForm() {
    editingId = null;
    form.reset();
    fields.temperature.value = "0.7";
    fields.maxTokens.value = "2048";
    fields.active.checked = true;
    permissionInputs.forEach((input) => { input.checked = false; });
    saveButton.textContent = t("settings.agents.create");
    cancelButton.hidden = true;
    setStatus(statusEl, "", "");
  }

  function renderAgents(agents) {
    agentsById.clear();
    agentList.replaceChildren();
    if (!agents.length) {
      const empty = document.createElement("p");
      empty.className = "auth-note";
      empty.textContent = t("settings.agents.empty");
      agentList.appendChild(empty);
      return;
    }

    agents.forEach((agent) => {
      agentsById.set(agent.id, agent);
      const card = document.createElement("article");
      card.className = "agent-card";

      const top = document.createElement("div");
      top.className = "agent-card__top";
      const identity = document.createElement("div");
      identity.className = "agent-card__identity";
      const name = document.createElement("strong");
      name.textContent = agent.name;
      const meta = document.createElement("span");
      meta.className = "agent-card__meta";
      meta.textContent = agent.provider_name + " · " + agent.model_id +
        " · " + (agent.is_active ? t("settings.agents.active") : t("settings.agents.inactive"));
      identity.append(name, meta);
      top.appendChild(identity);

      const description = document.createElement("p");
      description.className = "agent-card__description";
      description.textContent = agent.description || "—";

      const prompt = document.createElement("p");
      prompt.className = "agent-card__prompt";
      prompt.textContent = agent.system_prompt;

      const permissions = document.createElement("div");
      permissions.className = "agent-card__permissions";
      (agent.permissions || []).forEach((permission) => {
        const chip = document.createElement("span");
        chip.textContent = permission;
        permissions.appendChild(chip);
      });
      if (!agent.permissions || !agent.permissions.length) {
        const chip = document.createElement("span");
        chip.textContent = t("settings.agents.noPermissions");
        permissions.appendChild(chip);
      }

      const actions = document.createElement("div");
      actions.className = "agent-card__actions";
      const edit = document.createElement("button");
      edit.type = "button";
      edit.className = "btn btn--ghost btn--small";
      edit.textContent = t("settings.agents.edit");
      edit.dataset.editAgent = agent.id;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "btn btn--danger btn--small";
      remove.textContent = t("settings.agents.delete");
      remove.dataset.deleteAgent = agent.id;
      actions.append(edit, remove);
      const runPanel = document.createElement("div");
      runPanel.className = "agent-card__run";
      const runInput = document.createElement("textarea");
      runInput.rows = 2;
      runInput.maxLength = 12000;
      runInput.placeholder = t("settings.agents.runPlaceholder");
      runInput.setAttribute("aria-label", t("settings.agents.runPlaceholder"));
      const runButton = document.createElement("button");
      runButton.type = "button";
      runButton.className = "btn btn--primary btn--small";
      runButton.textContent = t("settings.agents.run");
      runButton.dataset.runAgent = agent.id;
      const runStatus = document.createElement("p");
      runStatus.className = "agent-card__status";
      runStatus.setAttribute("role", "status");
      runStatus.setAttribute("aria-live", "polite");
      const runOutput = document.createElement("pre");
      runOutput.className = "agent-card__output";
      runOutput.hidden = true;
      runPanel.append(runInput, runButton, runStatus, runOutput);

      card.append(top, description, prompt, permissions, runPanel, actions);
      agentList.appendChild(card);
    });
  }

  async function loadConnections() {
    const previous = connectionSelect.value;
    const response = await authFetch(connectionsPath);
    if (!response.ok) throw new Error(await readError(response));
    const data = await response.json();
    connectionSelect.replaceChildren();
    const connections = Array.isArray(data.connections) ? data.connections : [];
    connections.forEach((connection) => {
      const option = document.createElement("option");
      option.value = connection.id;
      option.textContent = connection.display_name + " · " + connection.provider_name;
      connectionSelect.appendChild(option);
    });
    if (connections.some((item) => item.id === previous)) connectionSelect.value = previous;
    saveButton.disabled = connections.length === 0;
    if (!connections.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = t("settings.agents.noConnections");
      connectionSelect.appendChild(option);
    }
  }

  async function loadAgents() {
    agentList.textContent = t("settings.agents.loading");
    try {
      const response = await authFetch(agentsPath);
      if (!response.ok) throw new Error(await readError(response));
      const data = await response.json();
      renderAgents(Array.isArray(data.agents) ? data.agents : []);
    } catch (error) {
      const message = document.createElement("p");
      message.className = "auth-note";
      message.textContent = error.message || t("settings.agents.loadFailed");
      agentList.replaceChildren(message);
    }
  }

  function beginEdit(agent) {
    editingId = agent.id;
    fields.name.value = agent.name;
    fields.description.value = agent.description || "";
    fields.prompt.value = agent.system_prompt;
    fields.model.value = agent.model_id;
    fields.temperature.value = String(agent.temperature);
    fields.maxTokens.value = String(agent.max_tokens);
    fields.active.checked = Boolean(agent.is_active);
    connectionSelect.value = agent.provider_connection_id;
    permissionInputs.forEach((input) => {
      input.checked = (agent.permissions || []).includes(input.value);
    });
    saveButton.textContent = t("settings.agents.update");
    cancelButton.hidden = false;
    setStatus(statusEl, "", "");
    fields.name.focus();
    form.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setStatus(statusEl, "", "");
    saveButton.disabled = true;
    const payload = {
      name: fields.name.value.trim(),
      description: fields.description.value.trim(),
      system_prompt: fields.prompt.value.trim(),
      provider_connection_id: connectionSelect.value,
      model_id: fields.model.value.trim(),
      temperature: Number(fields.temperature.value),
      max_tokens: Number(fields.maxTokens.value),
      permissions: selectedPermissions(),
      is_active: fields.active.checked,
    };
    try {
      const response = await authFetch(
        editingId ? agentsPath + "/" + encodeURIComponent(editingId) : agentsPath,
        {
          method: editingId ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      if (!response.ok) throw new Error(await readError(response));
      resetForm();
      setStatus(statusEl, t("settings.agents.saved"), "success");
      await loadAgents();
    } catch (error) {
      setStatus(statusEl, error.message || t("settings.agents.saveFailed"), "error");
    } finally {
      saveButton.disabled = !connectionSelect.value;
    }
  });

  agentList.addEventListener("click", async (event) => {
    const runButton = event.target.closest("[data-run-agent]");
    const editButton = event.target.closest("[data-edit-agent]");
    const deleteButton = event.target.closest("[data-delete-agent]");
    if (runButton) {
      const card = runButton.closest(".agent-card");
      const runInput = card.querySelector(".agent-card__run textarea");
      const runStatus = card.querySelector(".agent-card__status");
      const runOutput = card.querySelector(".agent-card__output");
      const message = runInput.value.trim();
      if (!message) {
        setStatus(runStatus, t("settings.agents.runMessageRequired"), "error");
        runInput.focus();
        return;
      }
      runButton.disabled = true;
      runOutput.hidden = true;
      setStatus(runStatus, t("settings.agents.running"), "");
      try {
        const response = await authFetch(
          agentsPath + "/" + encodeURIComponent(runButton.dataset.runAgent) + "/run",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
          }
        );
        if (!response.ok) throw new Error(await readError(response));
        const data = await response.json();
        runOutput.textContent = data.text || "";
        runOutput.hidden = false;
        const total = data.usage && data.usage.total_tokens;
        setStatus(
          runStatus,
          data.provider + " · " + data.model + (total ? " · " + total + " tokens" : ""),
          "success"
        );
      } catch (error) {
        setStatus(runStatus, error.message || t("settings.agents.runFailed"), "error");
      } finally {
        runButton.disabled = false;
      }
      return;
    }
    if (!editButton && !deleteButton) return;
    const id = (editButton || deleteButton).dataset.editAgent ||
      (editButton || deleteButton).dataset.deleteAgent;
    if (editButton) {
      const cached = agentsById.get(id);
      if (cached) beginEdit(cached);
      return;
    }
    if (!window.confirm(t("settings.agents.deleteConfirm"))) return;
    deleteButton.disabled = true;
    try {
      const response = await authFetch(agentsPath + "/" + encodeURIComponent(id), {
        method: "DELETE",
      });
      if (!response.ok) throw new Error(await readError(response));
      if (editingId === id) resetForm();
      await loadAgents();
    } catch (error) {
      deleteButton.disabled = false;
      const message = document.createElement("p");
      message.className = "agent-card__status";
      message.textContent = error.message || t("settings.agents.deleteFailed");
      deleteButton.closest(".agent-card").appendChild(message);
    }
  });

  cancelButton.addEventListener("click", resetForm);
  refreshButton.addEventListener("click", async () => {
    try {
      await loadConnections();
      await loadAgents();
    } catch (error) {
      setStatus(statusEl, error.message || t("settings.agents.loadFailed"), "error");
    }
  });

  (async function init() {
    try {
      await loadConnections();
      await loadAgents();
    } catch (error) {
      setStatus(statusEl, error.message || t("settings.agents.loadFailed"), "error");
    }
  })();
})();
