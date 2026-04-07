// Shared page chrome for settings persistence plus a reusable loading screen.
document.addEventListener("DOMContentLoaded", () => {
  initLoadingScreen();
  initSettingsPanel();
});

function initLoadingScreen() {
  const page = document.body;
  if (!page) return;

  const overlay = document.createElement("div");
  overlay.className = "app-loading-overlay";
  overlay.setAttribute("aria-hidden", "true");
  overlay.innerHTML = `
    <div class="loading-screen" role="status" aria-live="polite" aria-atomic="true">
      <p class="loading-screen-kicker">Plant App</p>
      <h2 class="loading-screen-title">Loading</h2>
      <p class="loading-screen-copy" data-loading-message>Opening the next screen...</p>
      <div class="loading-screen-track" aria-hidden="true">
        <span class="loading-screen-bar"></span>
      </div>
    </div>
  `;
  page.appendChild(overlay);

  const messageNode = overlay.querySelector("[data-loading-message]");

  const showLoadingScreen = (message) => {
    if (messageNode) {
      messageNode.textContent = message || "Opening the next screen...";
    }
    page.classList.add("page-loading");
    page.setAttribute("aria-busy", "true");
    overlay.setAttribute("aria-hidden", "false");
  };

  const hideLoadingScreen = () => {
    page.classList.remove("page-loading");
    page.removeAttribute("aria-busy");
    overlay.setAttribute("aria-hidden", "true");
  };

  const inferFormMessage = (form, submitter) => {
    const buttonText = (submitter?.dataset.loadingLabel || submitter?.textContent || "").trim().toLowerCase();
    const action = form.getAttribute("action") || window.location.pathname;

    if (buttonText.includes("login") || action === "/login") {
      return "Signing in...";
    }
    if (buttonText.includes("finalize")) {
      return "Finalizing the batch pack...";
    }
    if (buttonText.includes("save") || buttonText.includes("confirm")) {
      return "Saving your changes...";
    }
    return "Loading the next screen...";
  };

  const inferLinkMessage = (link) => {
    const label = (link.dataset.loadingLabel || link.textContent || "").trim().toLowerCase();
    if (label.includes("logout")) {
      return "Signing out...";
    }
    if (label.includes("open") || label.includes("start") || label.includes("home")) {
      return "Opening the next screen...";
    }
    return "Loading the next screen...";
  };

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    showLoadingScreen(inferFormMessage(form, event.submitter));
  }, true);

  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }

    const target = event.target;
    if (!(target instanceof Element)) return;

    const link = target.closest("a[href]");
    if (!(link instanceof HTMLAnchorElement)) return;
    if (link.hasAttribute("download")) return;
    if (link.target && link.target !== "_self") return;

    const href = link.getAttribute("href") || "";
    if (!href || href.startsWith("#") || href.startsWith("javascript:")) return;

    const url = new URL(href, window.location.href);
    if (url.origin !== window.location.origin) return;

    showLoadingScreen(inferLinkMessage(link));
  }, true);

  window.addEventListener("pageshow", hideLoadingScreen);
  window.addEventListener("load", hideLoadingScreen);

  window.showPlantLoading = showLoadingScreen;
  window.hidePlantLoading = hideLoadingScreen;
}

function initSettingsPanel() {
  const root = document.documentElement;
  const page = document.body;
  const panel = document.querySelector("[data-settings-panel]");
  const toggle = document.querySelector("[data-settings-toggle]");
  if (!page || !panel || !toggle) return;

  const settingsEndpoint = page.dataset.settingsEndpoint || "";
  const shouldPersist = page.dataset.settingsPersist === "true";
  const initialTheme = page.dataset.settingsTheme || "light";
  const initialFontScale = page.dataset.settingsFontScale || "1";

  const applyTheme = (theme) => {
    root.dataset.theme = theme === "dark" ? "dark" : "light";
    page.dataset.settingsTheme = root.dataset.theme;
    panel.querySelectorAll("[data-theme-choice]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.themeChoice === root.dataset.theme);
    });
  };

  const applyFontScale = (scale) => {
    const nextScale = ["1", "1.15", "1.3"].includes(scale) ? scale : "1";
    root.style.setProperty("--font-scale", nextScale);
    page.dataset.settingsFontScale = nextScale;
    panel.querySelectorAll("[data-font-choice]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.fontChoice === nextScale);
    });
  };

  const persistPreferences = async () => {
    if (!shouldPersist || !settingsEndpoint) return;
    const payload = new URLSearchParams({
      theme: page.dataset.settingsTheme || "light",
      font_scale: page.dataset.settingsFontScale || "1",
    });

    try {
      const response = await fetch(settingsEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: payload.toString(),
      });
      if (!response.ok) return;
      const saved = await response.json();
      applyTheme(saved.theme || "light");
      applyFontScale(saved.font_scale || "1");
    } catch (error) {
      // If saving fails, keep the current page state and avoid interrupting the operator.
      console.error("Unable to save user settings", error);
    }
  };

  const refreshPreferences = async () => {
    if (!shouldPersist || !settingsEndpoint) return;
    try {
      const response = await fetch(settingsEndpoint, { method: "GET" });
      if (!response.ok) return;
      const saved = await response.json();
      applyTheme(saved.theme || "light");
      applyFontScale(saved.font_scale || "1");
    } catch (error) {
      console.error("Unable to refresh user settings", error);
    }
  };

  const closePanel = () => {
    panel.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
  };

  const openPanel = () => {
    panel.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
  };

  toggle.addEventListener("click", () => {
    if (panel.hidden) {
      openPanel();
    } else {
      closePanel();
    }
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (!panel.hidden && !target.closest(".settings-root")) {
      closePanel();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closePanel();
    }
  });

  panel.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.addEventListener("click", async () => {
      applyTheme(button.dataset.themeChoice || "light");
      await persistPreferences();
    });
  });

  panel.querySelectorAll("[data-font-choice]").forEach((button) => {
    button.addEventListener("click", async () => {
      applyFontScale(button.dataset.fontChoice || "1");
      await persistPreferences();
    });
  });

  applyTheme(initialTheme);
  applyFontScale(initialFontScale);
  refreshPreferences();
}
