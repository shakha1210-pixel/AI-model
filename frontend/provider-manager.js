// provider-manager.js — authenticated provider connection UI.
// API keys stay in the password input only until the request completes;
// this file never writes credentials to localStorage/sessionStorage.
(function () {
  "use strict";

  const form = document.getElementById("provider-connection-form");
  if (!form || !window.AuthFetch) return;

  const authFetch = window.AuthFetch.authFetch;
  const providerSelect = document.getElementById("provider-id");
  const displayNameInput = document.getElementById("provider-display-name");
  const apiKeyInput = document.getElementById("provider-api-key");
  const baseUrlWrap = document.getElementById("provider-base-url-wrap");
  const baseUrlInput = document.getElementById("provider-base-url");
  const saveButton = document.getElementById("provider-save-btn");
  const formStatus = document.getElementById("provider-form-status");
  const list = document.getElementById("provider-connection-list");
  const refreshButton = document.getElementById("provider-refresh-btn");

  const t = (key) => window.I18N ? window.I18N.t(key) : key;
  const apiPath = "/api/workspace/connections";
  const providerDefaults = {
    openai: "gpt-4.1-mini",
    anthropic: "claude-3-5-haiku-latest",
    google: "gemini-2.5-flash",
    openrouter: "openai/gpt-4.1-mini",
    custom_openai: "",
  };

  function setStatus(element, message, kind) {
    element.textContent = message || "";
    element.dataset.state = kind || "";
  }

  async function readError(response) {
    const data = await response.json().catch(() => ({}));
    if (typeof data.detail === "string") return data.detail;
    if (data.detail && typeof data.detail.message === "string") return data.detail.message;
    return t("settings.providers.requestFailed");
  }

  function updateBaseUrlVisibility() {
    const isCustom = providerSelect.value === "custom_openai";
    baseUrlWrap.hidden = !isCustom;
    baseUrlInput.required = isCustom;
  }

  function makeActionButton(label, className, action, connectionId) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.dataset[action] = connectionId;
    return button;
  }

  function renderConnections(connections) {
    list.replaceChildren();
    if (!connections.length) {
      const empty = document.createElement("p");
      empty.className = "auth-note";
      empty.textContent = t("settings.providers.empty");
      list.appendChild(empty);
      return;
    }

    connections.forEach((connection) => {
      const card = document.createElement("article");
      card.className = "provider-connection-card";

      const top = document.createElement("div");
      top.className = "provider-connection-card__top";
      const identity = document.createElement("div");
      identity.className = "provider-connection-card__identity";

      const name = document.createElement("strong");
      name.textContent = connection.display_name;
      const provider = document.createElement("span");
      provider.textContent = connection.provider_name + " · " + connection.provider_id;
      identity.append(name, provider);
      top.appendChild(identity);

      if (connection.base_url) {
        const url = document.createElement("code");
        url.className = "provider-connection-card__url";
        url.textContent = connection.base_url;
        top.appendChild(url);
      }

      const controls = document.createElement("div");
      controls.className = "provider-connection-card__controls";
      const modelLabel = document.createElement("label");
      modelLabel.className = "provider-manager__model-field";
      const modelText = document.createElement("span");
      modelText.textContent = t("settings.providers.model");
      const modelInput = document.createElement("input");
      modelInput.type = "text";
      modelInput.autocomplete = "off";
      modelInput.placeholder = t("settings.providers.modelPlaceholder");
      modelInput.value = providerDefaults[connection.provider_id] || "";
      modelInput.dataset.modelId = "";
      modelLabel.append(modelText, modelInput);

      const actions = document.createElement("div");
      actions.className = "provider-connection-card__actions";
      actions.append(
        makeActionButton(t("settings.providers.test"), "btn btn--ghost btn--small", "testConnection", connection.id),
        makeActionButton(t("settings.providers.delete"), "btn btn--danger btn--small", "deleteConnection", connection.id)
      );

      const status = document.createElement("p");
      status.className = "provider-connection-card__status";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");

      controls.append(modelLabel, actions);
      card.append(top, controls, status);
      list.appendChild(card);
    });
  }

  async function loadConnections() {
    list.textContent = t("settings.providers.loading");
    try {
      const response = await authFetch(apiPath);
      if (response.status === 404 || response.status === 503) {
        throw new Error(t("settings.providers.serverDisabled"));
      }
      if (!response.ok) throw new Error(await readError(response));
      const data = await response.json();
      renderConnections(Array.isArray(data.connections) ? data.connections : []);
    } catch (error) {
      const message = document.createElement("p");
      message.className = "auth-note";
      message.textContent = error.message || t("settings.providers.loadFailed");
      list.replaceChildren(message);
    }
  }

  providerSelect.addEventListener("change", updateBaseUrlVisibility);
  updateBaseUrlVisibility();
  displayNameInput.value = providerSelect.options[providerSelect.selectedIndex].text;

  providerSelect.addEventListener("change", () => {
    const option = providerSelect.options[providerSelect.selectedIndex];
    if (!displayNameInput.value.trim()) displayNameInput.value = option.text;
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setStatus(formStatus, "", "");
    saveButton.disabled = true;

    const payload = {
      provider_id: providerSelect.value,
      display_name: displayNameInput.value.trim(),
      api_key: apiKeyInput.value,
    };
    if (providerSelect.value === "custom_openai") {
      payload.base_url = baseUrlInput.value.trim();
    }

    try {
      const response = await authFetch(apiPath, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await readError(response));
      apiKeyInput.value = "";
      baseUrlInput.value = "";
      setStatus(formStatus, t("settings.providers.savedMessage"), "success");
      await loadConnections();
    } catch (error) {
      setStatus(formStatus, error.message || t("settings.providers.saveFailed"), "error");
    } finally {
      apiKeyInput.value = "";
      saveButton.disabled = false;
    }
  });

  list.addEventListener("click", async (event) => {
    const testButton = event.target.closest("[data-test-connection]");
    const deleteButton = event.target.closest("[data-delete-connection]");
    if (!testButton && !deleteButton) return;

    const button = testButton || deleteButton;
    const connectionId = button.dataset.testConnection || button.dataset.deleteConnection;
    const card = button.closest(".provider-connection-card");
    const status = card.querySelector(".provider-connection-card__status");

    if (deleteButton) {
      if (!window.confirm(t("settings.providers.deleteConfirm"))) return;
      deleteButton.disabled = true;
      setStatus(status, "", "");
      try {
        const response = await authFetch(apiPath + "/" + encodeURIComponent(connectionId), {
          method: "DELETE",
        });
        if (!response.ok) throw new Error(await readError(response));
        await loadConnections();
      } catch (error) {
        setStatus(status, error.message || t("settings.providers.deleteFailed"), "error");
        deleteButton.disabled = false;
      }
      return;
    }

    const modelInput = card.querySelector("[data-model-id]");
    const model = modelInput.value.trim();
    if (!model) {
      setStatus(status, t("settings.providers.modelRequired"), "error");
      modelInput.focus();
      return;
    }

    testButton.disabled = true;
    setStatus(status, t("settings.providers.testing"), "");
    try {
      const response = await authFetch(
        apiPath + "/" + encodeURIComponent(connectionId) + "/test",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model }),
        }
      );
      if (!response.ok) throw new Error(await readError(response));
      setStatus(status, t("settings.providers.testSuccess"), "success");
    } catch (error) {
      setStatus(status, error.message || t("settings.providers.testFailed"), "error");
    } finally {
      testButton.disabled = false;
    }
  });

  refreshButton.addEventListener("click", loadConnections);
  loadConnections();
})();
