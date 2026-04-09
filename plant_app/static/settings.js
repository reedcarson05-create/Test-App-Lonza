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
      <div class="loading-screen-header">
        <p class="loading-screen-kicker">LAG Plant Operations</p>
        <span class="loading-screen-badge">Secure Session</span>
      </div>
      <h2 class="loading-screen-title">Preparing Workspace</h2>
      <p class="loading-screen-copy" data-loading-message>Opening the next screen...</p>
      <div class="loading-screen-track" aria-hidden="true">
        <span class="loading-screen-bar"></span>
      </div>
      <p class="loading-screen-caption">Loading the next view and the latest shared resources.</p>
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
    if (buttonText.includes("finalize") || buttonText.includes("close run")) {
      return "Closing the run...";
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
    if (event.defaultPrevented) {
      hideLoadingScreen();
      return;
    }
    showLoadingScreen(inferFormMessage(form, event.submitter));
  });

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
  const appStatusEndpoint = page.dataset.appStatusEndpoint || "";
  const pageBuildVersion = page.dataset.appVersion || "";
  const pageBuildLabel = page.dataset.appBuildLabel || "";
  const pageChangedFile = page.dataset.appChangedFile || "";

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

  const describeBuild = (label, changedFile) => {
    const details = [];
    if (label) {
      details.push(label);
    }
    if (changedFile) {
      details.push(changedFile);
    }
    return details.join(" | ");
  };

  const reloadPageWithFreshQuery = () => {
    const url = new URL(window.location.href);
    url.searchParams.set("refresh", Date.now().toString());
    if (typeof window.showPlantLoading === "function") {
      window.showPlantLoading("Loading the newest app build...");
    }
    window.location.replace(url.toString());
  };

  const initAppUpdateSection = () => {
    if (!appStatusEndpoint || panel.querySelector("[data-app-update-group]")) return;

    const group = document.createElement("div");
    group.className = "settings-group settings-update-group";
    group.dataset.appUpdateGroup = "true";
    group.innerHTML = `
      <span class="settings-label">App Updates</span>
      <p class="settings-copy muted small settings-build-meta" data-app-build-meta></p>
      <div class="settings-update-actions">
        <button class="btn ghost settings-update-button" type="button" data-app-update-button>Check for Updates</button>
        <button class="btn settings-update-button" type="button" data-app-reload-button hidden>Reload Page</button>
      </div>
      <p class="settings-status muted small" data-app-update-status aria-live="polite"></p>
    `;
    panel.appendChild(group);

    const buildMeta = group.querySelector("[data-app-build-meta]");
    const statusNode = group.querySelector("[data-app-update-status]");
    const checkButton = group.querySelector("[data-app-update-button]");
    const reloadButton = group.querySelector("[data-app-reload-button]");

    const setStatus = (message, state = "") => {
      statusNode.textContent = message;
      statusNode.dataset.state = state;
    };

    const setReloadVisible = (visible) => {
      reloadButton.hidden = !visible;
    };

    if (buildMeta) {
      buildMeta.textContent = pageBuildLabel
        ? `This page loaded build ${describeBuild(pageBuildLabel, pageChangedFile)}.`
        : "This page does not expose a build stamp yet.";
    }
    setStatus("Use Check for Updates to see whether newer code has been picked up.", "idle");
    setReloadVisible(false);

    reloadButton.addEventListener("click", () => {
      reloadPageWithFreshQuery();
    });

    checkButton.addEventListener("click", async () => {
      checkButton.disabled = true;
      checkButton.textContent = "Checking...";
      setReloadVisible(false);
      setStatus("Checking the newest code visible to the app...", "checking");

      try {
        const response = await fetch(appStatusEndpoint, {
          method: "GET",
          headers: {
            "Accept": "application/json",
          },
          credentials: "same-origin",
          cache: "no-store",
        });
        if (response.status === 404) {
          setStatus(
            "This app window is still using an older backend build. The new Settings button loaded from disk, but the running Plant App needs to be closed and reopened before update checks will work.",
            "warning"
          );
          return;
        }
        if (!response.ok) {
          throw new Error(`Update check failed (${response.status}).`);
        }

        const status = await response.json();
        const loadedVersion = status.loaded_version || "";
        const loadedBuildLabel = status.loaded_build_label || "";
        const loadedChangedFile = status.loaded_changed_file || "";
        const diskVersion = status.disk_version || loadedVersion;
        const diskBuildLabel = status.disk_build_label || loadedBuildLabel;
        const diskChangedFile = status.disk_changed_file || loadedChangedFile;

        if (loadedVersion && pageBuildVersion && loadedVersion !== pageBuildVersion) {
          setStatus(
            `A newer app build is already running: ${describeBuild(loadedBuildLabel, loadedChangedFile)}. Reload this page after you save any work.`,
            "update"
          );
          setReloadVisible(true);
          return;
        }

        if (diskVersion && loadedVersion && diskVersion !== loadedVersion) {
          setStatus(
            `Newer code is on disk: ${describeBuild(diskBuildLabel, diskChangedFile)}. Reload this page first; if it still looks old, close and reopen the Plant App launcher.`,
            "warning"
          );
          setReloadVisible(true);
          return;
        }

        setStatus(
          `No newer update found. Running build ${describeBuild(loadedBuildLabel || pageBuildLabel, loadedChangedFile || pageChangedFile)}.`,
          "ok"
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : `Update check failed: ${error}`;
        setStatus(message, "error");
      } finally {
        checkButton.disabled = false;
        checkButton.textContent = "Check for Updates";
      }
    });
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

  initAppUpdateSection();
  applyTheme(initialTheme);
  applyFontScale(initialFontScale);
  refreshPreferences();
}
