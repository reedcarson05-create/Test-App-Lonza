document.addEventListener("DOMContentLoaded", () => {
  const selectors = "input[name], select[name], textarea[name]";
  const skipTypes = new Set(["hidden", "submit", "button", "reset", "file"]);

  document.querySelectorAll("form").forEach((form) => {
    form.querySelectorAll(selectors).forEach((field) => {
      if (!field.name || field.name.startsWith("__change__")) return;
      if (field.disabled) return;
      if (field.tagName === "INPUT" && skipTypes.has((field.type || "").toLowerCase())) return;
      if (field.classList.contains("change-initials")) return;

      const wrapper = document.createElement("div");
      wrapper.className = "field-with-change";
      field.parentNode.insertBefore(wrapper, field);

      const topRow = document.createElement("div");
      topRow.className = "field-edit-row";
      wrapper.appendChild(topRow);
      topRow.appendChild(field);

      const initialsWrap = document.createElement("div");
      initialsWrap.className = "inline-initials";

      const initialsLabel = document.createElement("div");
      initialsLabel.className = "change-caption";
      initialsLabel.textContent = "Init";
      initialsWrap.appendChild(initialsLabel);

      const changeInput = document.createElement("input");
      changeInput.type = "text";
      changeInput.name = `__change__${field.name}`;
      changeInput.maxLength = 6;
      changeInput.placeholder = "initials";
      changeInput.className = "change-initials";
      changeInput.setAttribute("title", `Initial here if ${field.name} was corrected`);
      initialsWrap.appendChild(changeInput);
      topRow.appendChild(initialsWrap);

      const originalWrap = document.createElement("div");
      originalWrap.className = "original-value-row";

      const originalLabel = document.createElement("div");
      originalLabel.className = "change-caption";
      originalLabel.textContent = "Original Saved Value";
      originalWrap.appendChild(originalLabel);

      const originalInput = document.createElement("input");
      originalInput.type = "text";
      originalInput.name = `__original__${field.name}`;
      originalInput.placeholder = "original saved value";
      originalInput.className = "change-detail";
      originalInput.readOnly = true;
      originalInput.setAttribute("title", `Original value for ${field.name}`);
      originalInput.value = field.value || "";
      originalWrap.appendChild(originalInput);
      wrapper.appendChild(originalWrap);

      const originalValue = field.value || "";
      const syncChangeInput = () => {
        if ((field.value || "") !== originalValue) {
        } else {
          changeInput.value = "";
        }
      };

      field.addEventListener("input", syncChangeInput);
      field.addEventListener("change", syncChangeInput);
    });
  });
});
