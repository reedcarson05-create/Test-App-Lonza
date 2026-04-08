document.addEventListener("DOMContentLoaded", () => {
  const forms = Array.from(document.querySelectorAll("form"));
  if (!forms.length) return;

  const body = document.body;
  const sessionBanners = Array.from(document.querySelectorAll("[data-signature-session-banner]"));
  const signatureState = {
    initials: (body.dataset.sessionSignatureInitials || "").toUpperCase(),
    data: body.dataset.sessionSignatureData || "",
    signedAt: body.dataset.sessionSignatureSignedAt || "",
  };
  const defaultInitials = (body.dataset.defaultInitials || "").toUpperCase();
  let pendingForm = null;
  let activeTriggerField = null;
  let suppressTriggerUntil = 0;
  let drawing = false;
  let draftSignatureData = signatureState.data;
  let draftHasStroke = Boolean(signatureState.data);
  let draftSignatureDirty = false;
  let canvasRenderToken = 0;
  let saveInFlight = false;

  const modal = document.createElement("div");
  modal.className = "signature-modal";
  modal.hidden = true;
  modal.style.display = "none";
  modal.innerHTML = `
    <div class="signature-dialog" role="dialog" aria-modal="true" aria-labelledby="signature-title">
      <h3 id="signature-title">Save Handwritten Signature</h3>
      <p class="muted signature-copy">Sign once for this login session. The app will reuse this signature, your initials, and the signed time until you log out.</p>
      <div class="grid two-up">
        <div>
          <label for="signature-initials-input">Initials</label>
          <input id="signature-initials-input" type="text" maxlength="6" autocomplete="off" spellcheck="false">
        </div>
        <div>
          <label>Signed Date / Time</label>
          <input id="signature-signed-at" type="text">
        </div>
      </div>
      <p class="muted signature-copy">Draw your signature on the pad, then keep the auto-filled date and time or edit it before saving.</p>
      <div class="signature-pad-wrap">
        <label>Draw Signature</label>
        <canvas class="signature-pad" width="900" height="260"></canvas>
      </div>
      <div class="actions">
        <button class="btn ghost" type="button" data-signature-clear>Clear</button>
        <button class="btn ghost" type="button" data-signature-cancel>Cancel</button>
        <button class="btn" type="button" data-signature-save>Save Signature</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  const initialsInput = modal.querySelector("#signature-initials-input");
  const signedAtInput = modal.querySelector("#signature-signed-at");
  const canvas = modal.querySelector(".signature-pad");
  const clearButton = modal.querySelector("[data-signature-clear]");
  const cancelButton = modal.querySelector("[data-signature-cancel]");
  const saveButton = modal.querySelector("[data-signature-save]");
  const context = canvas.getContext("2d");

  function elapsedMs(startedAt) {
    const now = window.performance && typeof window.performance.now === "function" ? window.performance.now() : Date.now();
    return Math.round((now - startedAt) * 10) / 10;
  }

  function normalizeDebugDetails(details = {}) {
    const normalized = {};
    Object.entries(details).forEach(([key, value]) => {
      if (value == null || value === "") return;
      if (typeof value === "number" || typeof value === "boolean") {
        normalized[key] = value;
        return;
      }
      normalized[key] = String(value).slice(0, 240);
    });
    return normalized;
  }

  function logSignatureEvent(eventName, details = {}) {
    const payload = {
      event: eventName,
      at: new Date().toISOString(),
      page: window.location.pathname,
      details: normalizeDebugDetails(details),
    };
    try {
      console.info("[signature-debug]", payload);
    } catch (_) {
      // Console access can fail in locked-down desktop shells; keep logging best-effort.
    }
    try {
      const bodyText = JSON.stringify(payload);
      if (navigator.sendBeacon) {
        const blob = new Blob([bodyText], { type: "application/json" });
        navigator.sendBeacon("/signature-debug", blob);
        return;
      }
      void window.fetch("/signature-debug", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "same-origin",
        keepalive: true,
        body: bodyText,
      }).catch(() => {});
    } catch (_) {
      // Logging should never interrupt data entry.
    }
  }

  function describeForm(form) {
    return {
      action: form.getAttribute("action") || window.location.pathname,
      method: (form.getAttribute("method") || "get").toUpperCase(),
    };
  }

  function submitterLabel(submitter) {
    if (!submitter) return "";
    return (
      submitter.dataset.loadingLabel ||
      submitter.textContent ||
      submitter.value ||
      ""
    ).trim().toLowerCase();
  }

  function isExplicitSaveSubmit(form, submitter) {
    const action = (form.getAttribute("action") || window.location.pathname).toLowerCase();
    const label = submitterLabel(submitter);
    if (submitter?.dataset.signatureTrigger === "true") {
      return true;
    }
    if (!submitter) {
      return false;
    }
    return (
      label.includes("save") ||
      label.includes("finalize") ||
      label.includes("confirm") ||
      action.includes("/submit/") ||
      action.includes("/edit/")
    );
  }

  function signatureReady() {
    return Boolean(signatureState.initials && signatureState.data && signatureState.signedAt);
  }

  function signatureBannerText() {
    if (signatureReady()) {
      return `Handwritten signature saved for this login: ${signatureState.initials} at ${signatureState.signedAt}. It will be reused until you log out.`;
    }
    return "Before your first save on this login, sign once by hand and confirm your initials, date, and time. The saved signature will be reused until you log out.";
  }

  function syncSessionBanner() {
    sessionBanners.forEach((banner) => {
      banner.textContent = signatureBannerText();
      banner.classList.toggle("is-saved", signatureReady());
    });
  }

  function renderPad(signatureData = "") {
    const rect = canvas.getBoundingClientRect();
    const requestedData = signatureData || "";
    canvasRenderToken += 1;
    const renderToken = canvasRenderToken;
    context.clearRect(0, 0, rect.width, rect.height);
    if (!requestedData) return;
    const image = new Image();
    image.onload = () => {
      if (renderToken !== canvasRenderToken || requestedData !== draftSignatureData) return;
      const currentRect = canvas.getBoundingClientRect();
      context.clearRect(0, 0, rect.width, rect.height);
      context.drawImage(image, 0, 0, currentRect.width, currentRect.height);
    };
    image.src = requestedData;
  }

  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    canvas.width = Math.max(Math.floor(rect.width * ratio), 1);
    canvas.height = Math.max(Math.floor(rect.height * ratio), 1);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.lineCap = "round";
    context.lineJoin = "round";
    context.lineWidth = 2.5;
    context.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--text").trim() || "#17202a";
    renderPad(draftSignatureData);
  }

  function nowStamp() {
    return new Date().toLocaleString();
  }

  function ensureHiddenField(form, name) {
    let input = form.querySelector(`input[name="${name}"]`);
    if (!input) {
      input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      form.appendChild(input);
    }
    return input;
  }

  function signatureFields(root = document) {
    return Array.from(root.querySelectorAll("input[name], textarea[name]")).filter((field) => {
      if (field.disabled) return false;
      if ((field.type || "").toLowerCase() === "hidden") return false;
      if ((field.name || "").startsWith("__")) return false;
      if (field.classList.contains("change-initials")) return false;
      return field.name.toLowerCase().includes("initials");
    });
  }

  function applySignatureToForm(form) {
    ensureHiddenField(form, "__session_signature_initials").value = signatureState.initials;
    ensureHiddenField(form, "__session_signature_data").value = signatureState.data;
    ensureHiddenField(form, "__session_signature_signed_at").value = signatureState.signedAt;
    signatureFields(form).forEach((field) => {
      if (!field.value || field.classList.contains("change-initials") || field.name === "operator_initials" || field.name === "final_edit_initials") {
        field.value = signatureState.initials;
      }
    });
  }

  function decorateSignatureField(field) {
    if (field.dataset.signatureReady === "true") {
      if (signatureReady() && (!field.value || field.name === "operator_initials" || field.name === "final_edit_initials")) {
        field.value = signatureState.initials;
      }
      return;
    }
    field.dataset.signatureReady = "true";
    field.readOnly = false;
    field.classList.remove("signature-trigger");
    if (field.placeholder === "Tap to save signature") {
      field.placeholder = "";
    }
    if (signatureReady() && (!field.value || field.name === "operator_initials" || field.name === "final_edit_initials")) {
      field.value = signatureState.initials;
    }
  }

  function decorateAllSignatureFields(root = document) {
    signatureFields(root).forEach(decorateSignatureField);
  }

  function clearPad() {
    draftSignatureData = "";
    draftHasStroke = false;
    draftSignatureDirty = true;
    canvasRenderToken += 1;
    const rect = canvas.getBoundingClientRect();
    context.clearRect(0, 0, rect.width, rect.height);
  }

  function openModal(reason = "manual", triggerField = null) {
    activeTriggerField = triggerField;
    if (typeof window.hidePlantLoading === "function") {
      window.hidePlantLoading();
    }
    logSignatureEvent("modal-open", {
      reason,
      pending_action: pendingForm ? describeForm(pendingForm).action : "",
      signature_ready: signatureReady(),
      has_saved_signature: Boolean(signatureState.data),
    });
    draftSignatureData = signatureState.data;
    draftHasStroke = Boolean(signatureState.data);
    draftSignatureDirty = false;
    initialsInput.value = signatureState.initials || defaultInitials;
    signedAtInput.value = signatureState.signedAt || nowStamp();
    modal.hidden = false;
    modal.style.display = "flex";
    body.classList.add("modal-open");
    resizeCanvas();
    initialsInput.focus();
  }

  function closeModal(reason = "close") {
    const pendingAction = pendingForm ? describeForm(pendingForm).action : "";
    if (typeof window.hidePlantLoading === "function") {
      window.hidePlantLoading();
    }
    if (modal.contains(document.activeElement) && typeof document.activeElement.blur === "function") {
      document.activeElement.blur();
    }
    logSignatureEvent("modal-close", {
      reason,
      pending_action: pendingAction,
      signature_ready: signatureReady(),
    });
    modal.hidden = true;
    modal.style.display = "none";
    body.classList.remove("modal-open");
    suppressTriggerUntil = Date.now() + 250;
    if (activeTriggerField) {
      activeTriggerField.blur();
    }
    activeTriggerField = null;
    pendingForm = null;
  }

  async function persistSignature(initials, signatureData, signedAt) {
    const timeoutMs = 15000;
    const startedAt = window.performance && typeof window.performance.now === "function" ? window.performance.now() : Date.now();
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    let timeoutId = null;
    logSignatureEvent("signature-persist-start", {
      initials,
      signed_at: signedAt,
      signature_length: signatureData.length,
      timeout_ms: timeoutMs,
    });
    try {
      if (controller) {
        timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
      }
      const response = await window.fetch("/signature-session", {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
        },
        credentials: "same-origin",
        signal: controller ? controller.signal : undefined,
        body: JSON.stringify({
          initials,
          signature_data: signatureData,
          signed_at: signedAt,
        }),
      });

      let payload = {};
      try {
        payload = await response.json();
      } catch (_) {
        payload = {};
      }

      logSignatureEvent("signature-persist-response", {
        status: response.status,
        ok: response.ok,
        duration_ms: elapsedMs(startedAt),
      });
      if (!response.ok) {
        logSignatureEvent("signature-persist-failed", {
          status: response.status,
          error: payload.error || "",
          duration_ms: elapsedMs(startedAt),
        });
        throw new Error(payload.error || `The signature could not be saved (${response.status}).`);
      }

      logSignatureEvent("signature-persist-ok", {
        duration_ms: elapsedMs(startedAt),
        returned_signature_length: (payload.signature_data || "").length,
      });
      return payload;
    } catch (error) {
      const timedOut = Boolean(controller && controller.signal.aborted);
      const message = error instanceof Error ? error.message : `${error}`;
      logSignatureEvent("signature-persist-error", {
        error: message,
        timed_out: timedOut,
        duration_ms: elapsedMs(startedAt),
      });
      if (timedOut) {
        throw new Error("Saving the signature timed out after 15 seconds. Check runtime/signature_debug.log, then try again.");
      }
      throw error;
    } finally {
      if (timeoutId != null) {
        window.clearTimeout(timeoutId);
      }
    }
  }

  async function saveSignature() {
    if (saveInFlight) return;

    try {
      logSignatureEvent("modal-save-click", {
        has_stroke: draftHasStroke,
        dirty_signature: draftSignatureDirty,
      });
      const initials = initialsInput.value.trim().toUpperCase();
      const signedAt = signedAtInput.value.trim();
      if (!initials) {
        initialsInput.focus();
        return;
      }
      if (!signedAt) {
        signedAtInput.focus();
        return;
      }
      if (!draftHasStroke) {
        window.alert("Please draw your handwritten signature before saving.");
        return;
      }

      let signaturePayload = draftSignatureData;
      if (draftSignatureDirty) {
        const exportStartedAt = window.performance && typeof window.performance.now === "function" ? window.performance.now() : Date.now();
        logSignatureEvent("canvas-export-start", {
          width: canvas.width,
          height: canvas.height,
        });
        signaturePayload = canvas.toDataURL("image/png");
        logSignatureEvent("canvas-export-finish", {
          duration_ms: elapsedMs(exportStartedAt),
          signature_length: signaturePayload.length,
        });
      } else {
        logSignatureEvent("canvas-export-skip", {
          signature_length: signaturePayload.length,
        });
      }
      const originalLabel = saveButton.textContent;
      saveInFlight = true;
      saveButton.disabled = true;
      saveButton.textContent = "Saving...";

      const savedSignature = await persistSignature(initials, signaturePayload, signedAt);
      signatureState.initials = (savedSignature.initials || initials).toUpperCase();
      signatureState.signedAt = savedSignature.signed_at || signedAt;
      signatureState.data = savedSignature.signature_data || signaturePayload;
      draftSignatureData = signatureState.data;
      draftHasStroke = true;
      draftSignatureDirty = false;
      body.dataset.sessionSignatureInitials = signatureState.initials;
      body.dataset.sessionSignatureSignedAt = signatureState.signedAt;
      body.dataset.sessionSignatureData = signatureState.data;
      decorateAllSignatureFields(document);
      forms.forEach(applySignatureToForm);
      logSignatureEvent("modal-save-success", {
        signature_ready: signatureReady(),
        signature_length: signatureState.data.length,
      });
      closeModal("save-success");
      syncSessionBanner();
      saveButton.textContent = originalLabel;
    } catch (error) {
      logSignatureEvent("modal-save-error", {
        error: error instanceof Error ? error.message : `${error}`,
      });
      window.alert(error instanceof Error ? error.message : `Could not save signature: ${error}`);
    } finally {
      saveInFlight = false;
      saveButton.disabled = false;
      saveButton.textContent = "Save Signature";
    }
  }

  function pointerPosition(event) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
  }

  canvas.addEventListener("pointerdown", (event) => {
    drawing = true;
    draftHasStroke = true;
    draftSignatureDirty = true;
    draftSignatureData = "";
    canvasRenderToken += 1;
    const point = pointerPosition(event);
    context.beginPath();
    context.moveTo(point.x, point.y);
    canvas.setPointerCapture(event.pointerId);
  });

  canvas.addEventListener("pointermove", (event) => {
    if (!drawing) return;
    const point = pointerPosition(event);
    context.lineTo(point.x, point.y);
    context.stroke();
  });

  ["pointerup", "pointerleave", "pointercancel"].forEach((eventName) => {
    canvas.addEventListener(eventName, (event) => {
      drawing = false;
      try {
        if (event.pointerId != null && canvas.hasPointerCapture(event.pointerId)) {
          canvas.releasePointerCapture(event.pointerId);
        }
      } catch (_) {
        // Some browsers may already have released capture.
      }
    });
  });

  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeModal("backdrop");
    }
  });

  clearButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    logSignatureEvent("modal-clear-click", {
      had_stroke: draftHasStroke,
    });
    clearPad();
  });

  cancelButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    logSignatureEvent("modal-cancel-click");
    closeModal("cancel-button");
  });

  saveButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    void saveSignature();
  });

  initialsInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void saveSignature();
    }
  });

  signedAtInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void saveSignature();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) {
      event.preventDefault();
      closeModal("escape");
    }
  });

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType === Node.ELEMENT_NODE) {
          decorateAllSignatureFields(node);
        }
      });
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });

  forms.forEach((form) => {
    form.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target instanceof HTMLTextAreaElement) return;
      if (target instanceof HTMLButtonElement) return;
      if (target instanceof HTMLInputElement) {
        const inputType = (target.type || "").toLowerCase();
        if (inputType === "submit" || inputType === "button" || inputType === "checkbox" || inputType === "radio") {
          return;
        }
      }
      if (!signatureReady() && modal.hidden) {
        event.preventDefault();
        if (typeof window.hidePlantLoading === "function") {
          window.hidePlantLoading();
        }
        logSignatureEvent("enter-submit-blocked-before-signature", {
          field_name: target.getAttribute("name") || target.getAttribute("id") || target.tagName,
          ...describeForm(form),
        });
      }
    });

    form.addEventListener("submit", (event) => {
      const submitter = event.submitter instanceof HTMLElement ? event.submitter : null;
      if (form.dataset.signatureSubmitting === "true") {
        delete form.dataset.signatureSubmitting;
        logSignatureEvent("form-submit-pass-through", {
          ...describeForm(form),
          submitter_label: submitterLabel(submitter),
        });
        return;
      }
      if (!signatureReady()) {
        event.preventDefault();
        if (!isExplicitSaveSubmit(form, submitter)) {
          if (typeof window.hidePlantLoading === "function") {
            window.hidePlantLoading();
          }
          logSignatureEvent("form-submit-blocked-non-save", {
            ...describeForm(form),
            submitter_label: submitterLabel(submitter),
          });
          return;
        }
        pendingForm = form;
        if (typeof window.hidePlantLoading === "function") {
          window.hidePlantLoading();
        }
        logSignatureEvent("form-submit-blocked-missing-signature", {
          ...describeForm(form),
          submitter_label: submitterLabel(submitter),
        });
        openModal("submit-blocked");
        return;
      }
      applySignatureToForm(form);
      form.dataset.signatureSubmitting = "true";
      logSignatureEvent("form-submit-ready", {
        ...describeForm(form),
        submitter_label: submitterLabel(submitter),
      });
    });
  });

  window.addEventListener("resize", () => {
    if (!modal.hidden) {
      resizeCanvas();
    }
  });

  decorateAllSignatureFields(document);
  syncSessionBanner();
  logSignatureEvent("page-init", {
    forms: forms.length,
    signature_ready: signatureReady(),
    has_saved_signature: Boolean(signatureState.data),
  });
  forms.forEach((form) => {
    if (signatureReady()) {
      applySignatureToForm(form);
    }
  });
});
