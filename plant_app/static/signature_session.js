document.addEventListener("DOMContentLoaded", () => {
  const forms = Array.from(document.querySelectorAll("form"));
  if (!forms.length) return;

  const body = document.body;
  const signatureState = {
    initials: (body.dataset.sessionSignatureInitials || "").toUpperCase(),
    data: body.dataset.sessionSignatureData || "",
    signedAt: body.dataset.sessionSignatureSignedAt || "",
  };
  const defaultInitials = (body.dataset.defaultInitials || "").toUpperCase();
  let pendingForm = null;
  let drawing = false;
  let hasStroke = Boolean(signatureState.data);

  const modal = document.createElement("div");
  modal.className = "signature-modal";
  modal.hidden = true;
  modal.innerHTML = `
    <div class="signature-dialog" role="dialog" aria-modal="true" aria-labelledby="signature-title">
      <h3 id="signature-title">Sign Initials</h3>
      <p class="muted signature-copy">Sign once for this login session. The app will reuse these initials until you log out.</p>
      <div class="grid two-up">
        <div>
          <label for="signature-initials-input">Initials</label>
          <input id="signature-initials-input" type="text" maxlength="6" autocomplete="off" spellcheck="false">
        </div>
        <div>
          <label>Signed At</label>
          <input id="signature-signed-at" type="text" readonly>
        </div>
      </div>
      <div class="signature-pad-wrap">
        <label>Draw Initials</label>
        <canvas class="signature-pad" width="900" height="260"></canvas>
      </div>
      <div class="actions">
        <button class="btn ghost" type="button" data-signature-clear>Clear</button>
        <button class="btn ghost" type="button" data-signature-cancel>Cancel</button>
        <button class="btn" type="button" data-signature-save>Save Initials</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  const initialsInput = modal.querySelector("#signature-initials-input");
  const signedAtInput = modal.querySelector("#signature-signed-at");
  const canvas = modal.querySelector(".signature-pad");
  const context = canvas.getContext("2d");

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
    if (!signatureState.data) {
      context.clearRect(0, 0, rect.width, rect.height);
    }
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
    if (field.dataset.signatureReady === "true") return;
    field.dataset.signatureReady = "true";
    field.readOnly = true;
    field.classList.add("signature-trigger");
    if (!field.placeholder) {
      field.placeholder = "Tap to sign initials";
    }
    if (signatureState.initials && !field.value) {
      field.value = signatureState.initials;
    }
    const openForField = (event) => {
      event.preventDefault();
      if (signatureState.initials) {
        field.value = signatureState.initials;
        return;
      }
      pendingForm = field.form || null;
      openModal();
    };
    field.addEventListener("focus", openForField);
    field.addEventListener("click", openForField);
  }

  function decorateAllSignatureFields(root = document) {
    signatureFields(root).forEach(decorateSignatureField);
  }

  function clearPad() {
    const rect = canvas.getBoundingClientRect();
    context.clearRect(0, 0, rect.width, rect.height);
    hasStroke = false;
    signatureState.data = "";
  }

  function openModal() {
    initialsInput.value = signatureState.initials || defaultInitials;
    signedAtInput.value = signatureState.signedAt || nowStamp();
    modal.hidden = false;
    body.classList.add("modal-open");
    resizeCanvas();
    initialsInput.focus();
  }

  function closeModal() {
    modal.hidden = true;
    body.classList.remove("modal-open");
    pendingForm = null;
  }

  function saveSignature() {
    const initials = initialsInput.value.trim().toUpperCase();
    if (!initials) {
      initialsInput.focus();
      return;
    }
    if (!hasStroke) {
      return;
    }
    signatureState.initials = initials;
    signatureState.signedAt = new Date().toISOString();
    signatureState.data = canvas.toDataURL("image/png");
    body.dataset.sessionSignatureInitials = signatureState.initials;
    body.dataset.sessionSignatureSignedAt = signatureState.signedAt;
    body.dataset.sessionSignatureData = signatureState.data;
    decorateAllSignatureFields(document);
    forms.forEach(applySignatureToForm);
    modal.hidden = true;
    body.classList.remove("modal-open");
    if (pendingForm) {
      const formToSubmit = pendingForm;
      pendingForm = null;
      formToSubmit.requestSubmit();
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
    hasStroke = true;
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
    canvas.addEventListener(eventName, () => {
      drawing = false;
    });
  });

  modal.querySelector("[data-signature-clear]").addEventListener("click", () => {
    clearPad();
  });
  modal.querySelector("[data-signature-cancel]").addEventListener("click", () => {
    closeModal();
  });
  modal.querySelector("[data-signature-save]").addEventListener("click", () => {
    saveSignature();
  });
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeModal();
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
    form.addEventListener("submit", (event) => {
      if (form.dataset.signatureSubmitting === "true") {
        delete form.dataset.signatureSubmitting;
        return;
      }
      if (!signatureState.initials) {
        event.preventDefault();
        pendingForm = form;
        openModal();
        return;
      }
      applySignatureToForm(form);
      form.dataset.signatureSubmitting = "true";
    });
  });

  window.addEventListener("resize", () => {
    if (!modal.hidden) {
      resizeCanvas();
    }
  });

  decorateAllSignatureFields(document);
  forms.forEach((form) => {
    if (signatureState.initials) {
      applySignatureToForm(form);
    }
  });
});
