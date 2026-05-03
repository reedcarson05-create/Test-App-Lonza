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
});
