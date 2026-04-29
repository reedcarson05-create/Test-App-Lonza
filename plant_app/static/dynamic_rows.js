// Adds one blank row at a time to data-sheet tables that no longer show every paper row up front.
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-add-row]").forEach((button) => {
    const card = button.closest(".card");
    const table = card?.querySelector("[data-repeat-table]");
    const body = table?.querySelector("[data-repeat-body]");
    if (!table || !body) return;

    const maxRows = Number.parseInt(table.dataset.repeatMaxRows || "0", 10);
    const prefix = table.dataset.repeatPrefix || "";

    const refreshButton = () => {
      const rowCount = body.querySelectorAll("tr").length;
      if (maxRows && rowCount >= maxRows) {
        button.disabled = true;
        button.textContent = "All Rows Added";
      }
    };

    button.addEventListener("click", () => {
      const sourceRow = body.querySelector("tr:last-child");
      if (!sourceRow) return;

      const nextIndex = body.querySelectorAll("tr").length + 1;
      if (maxRows && nextIndex > maxRows) {
        refreshButton();
        return;
      }

      const newRow = sourceRow.cloneNode(true);
      newRow.querySelectorAll("input[name], select[name], textarea[name]").forEach((field) => {
        const fieldKey = field.dataset.repeatField || (field.name || "").split("_").pop();
        field.name = `${prefix}_${nextIndex}_${fieldKey}`;

        const defaultValue = field.dataset.defaultValue || "";
        if (field.tagName === "SELECT") {
          field.value = defaultValue;
        } else if (field.type !== "hidden") {
          field.value = defaultValue;
        }
        field.classList.remove("blank-stamped", "blank-value");
      });

      body.appendChild(newRow);
      refreshButton();
    });

    refreshButton();
  });
});
