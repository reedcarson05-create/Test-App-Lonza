// Shared data-entry helpers for production sheets.
document.addEventListener("DOMContentLoaded", () => {
  const two = (value) => String(value).padStart(2, "0");
  const todayValue = () => {
    const now = new Date();
    return `${now.getFullYear()}-${two(now.getMonth() + 1)}-${two(now.getDate())}`;
  };
  const nowValue = () => {
    const now = new Date();
    return `${two(now.getHours())}:${two(now.getMinutes())}`;
  };

  const textForField = (field) => {
    const label = field.closest("div, td")?.querySelector("label")?.textContent || "";
    return `${field.name || ""} ${label}`.toLowerCase();
  };

  const shouldUseNumericKeyboard = (field) => {
    if (!["text", "search", "tel", ""].includes(field.type || "")) return false;
    const text = textForField(field);
    if (/(initial|operator|comment|note|photo|path|method|status|bed|vessel|name|lot|location|flavor|odor)/.test(text)) {
      return false;
    }
    return /(number|no\.|#|ri|temp|pressure|rate|speed|load|volume|total|weight|density|target|gallon|gal|lb|ppm|ntu|gpm|rpm|psi|vac|level|color|turbidity|scale|inch|effect|condenser|condensor)/.test(text);
  };

  const isDateField = (field) => {
    const name = (field.name || "").toLowerCase();
    return field.type === "date" || name.endsWith("_date") || name === "date";
  };

  const isTimeField = (field) => {
    const name = (field.name || "").toLowerCase();
    return field.type === "time" || name.endsWith("_time") || name === "time" || /(^|_)time$/.test(name);
  };

  const fillDateTime = (field) => {
    if (!field || field.disabled || field.readOnly || field.value) return;
    if (isDateField(field)) {
      field.value = todayValue();
    } else if (isTimeField(field)) {
      field.value = nowValue();
    }
  };

  const setupField = (field) => {
    if (!field || field.dataset.entryHelpersReady === "true") return;
    field.dataset.entryHelpersReady = "true";
    field.setAttribute("autocomplete", "off");
    field.setAttribute("autocorrect", "off");
    field.setAttribute("autocapitalize", "off");
    if (field.tagName === "INPUT") {
      field.setAttribute("spellcheck", "false");
    }
    if (shouldUseNumericKeyboard(field)) {
      field.setAttribute("inputmode", "decimal");
    }
  };

  document.querySelectorAll("form").forEach((form) => {
    form.setAttribute("autocomplete", "off");
    if (form.dataset.lockSavedValues === "true") {
      form.querySelectorAll("input[name], select[name], textarea[name]").forEach((field) => {
        const fieldName = (field.name || "").toLowerCase();
        if (field.tagName === "TEXTAREA" || /^(notes|comments|photo_path)$/.test(fieldName)) return;
        if (!field.value || field.type === "hidden" || field.type === "file" || field.type === "submit") return;
        field.classList.add("saved-locked");
        if (field.tagName === "SELECT") {
          const hidden = document.createElement("input");
          hidden.type = "hidden";
          hidden.name = field.name;
          hidden.value = field.value;
          field.before(hidden);
          field.disabled = true;
        } else {
          field.readOnly = true;
        }
      });
    }
  });

  document.querySelectorAll("input, textarea").forEach((field) => {
    setupField(field);
  });

  ["focusin", "pointerdown", "click"].forEach((eventName) => {
    document.addEventListener(eventName, (event) => {
      const field = event.target?.closest?.("input, textarea");
      if (!field) return;
      setupField(field);
      if (isDateField(field) || isTimeField(field)) {
        fillDateTime(field);
      }
    });
  });

  // ── Draft auto-save ──────────────────────────────────────────────
  const draftKey = `draft:${window.location.pathname}`;
  const draftTsKey = `draft_ts:${window.location.pathname}`;

  const serializeDraft = (form) => {
    const data = {};
    form.querySelectorAll("input[name], select[name], textarea[name]").forEach((f) => {
      if (f.disabled || f.type === "hidden" || f.type === "file" || f.type === "submit") return;
      if (f.classList.contains("saved-locked") || f.readOnly) return;
      data[f.name] = f.value;
    });
    return data;
  };

  const saveDraft = (form) => {
    const data = serializeDraft(form);
    if (!Object.keys(data).length) return;
    try {
      localStorage.setItem(draftKey, JSON.stringify(data));
      localStorage.setItem(draftTsKey, new Date().toISOString());
    } catch (_) {}
  };

  const clearDraft = () => {
    localStorage.removeItem(draftKey);
    localStorage.removeItem(draftTsKey);
  };

  const restoreDraft = (form, data) => {
    Object.entries(data).forEach(([name, value]) => {
      const field = form.querySelector(`[name="${CSS.escape(name)}"]`);
      if (!field || field.disabled || field.classList.contains("saved-locked")) return;
      field.value = value;
    });
  };

  const showRestoreBanner = (form, tsIso) => {
    const timeStr = new Date(tsIso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const banner = document.createElement("div");
    banner.className = "draft-restore-banner";
    banner.innerHTML =
      `<span>Unsaved draft from ${timeStr}</span>` +
      `<button type="button" class="draft-restore-btn" data-draft-restore>Restore</button>` +
      `<button type="button" class="draft-dismiss-btn" data-draft-dismiss>Dismiss</button>`;
    form.before(banner);

    banner.querySelector("[data-draft-restore]").addEventListener("click", () => {
      const saved = localStorage.getItem(draftKey);
      if (saved) restoreDraft(form, JSON.parse(saved));
      clearDraft();
      banner.remove();
    });

    banner.querySelector("[data-draft-dismiss]").addEventListener("click", () => {
      clearDraft();
      banner.remove();
    });
  };

  // Check for existing draft on page load
  const entryForm = document.querySelector("form[method=post], form[method=POST]");
  if (entryForm) {
    const savedDraft = localStorage.getItem(draftKey);
    const savedTs = localStorage.getItem(draftTsKey);
    if (savedDraft && savedTs) {
      try {
        const data = JSON.parse(savedDraft);
        if (Object.keys(data).length) showRestoreBanner(entryForm, savedTs);
      } catch (_) { clearDraft(); }
    }

    // Clear draft on successful submit
    entryForm.addEventListener("submit", () => clearDraft());

    // Auto-save on input (debounced 4s)
    let saveTimer = null;
    document.addEventListener("input", (event) => {
      if (!event.target.closest("input, select, textarea")) return;
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => saveDraft(entryForm), 4000);
    });
    document.addEventListener("change", (event) => {
      if (!event.target.closest("select")) return;
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => saveDraft(entryForm), 4000);
    });
  }
});
