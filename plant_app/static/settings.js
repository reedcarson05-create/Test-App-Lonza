// Shared page chrome for settings persistence plus a reusable loading screen.
document.addEventListener("DOMContentLoaded", () => {
  initDnaBackground();
  initLoadingScreen();
  initSettingsPanel();
});

function initDnaBackground() {
  const page = document.body;
  if (!page || page.querySelector(".dna-bg")) return;

  const layer = document.createElement("div");
  layer.className = "dna-bg";
  layer.setAttribute("aria-hidden", "true");
  layer.innerHTML = buildStaticDnaMarkup();
  page.prepend(layer);
}

function buildStaticDnaMarkup() {
  const rungCount = 16;
  const railPointsA = [];
  const railPointsB = [];
  const nodes = [];
  const rungs = [];
  const centerX = 320;
  const amplitude = 98;
  const top = -120;
  const spacing = 118;

  for (let index = 0; index < rungCount; index += 1) {
    const phase = index * 0.7;
    const y = top + index * spacing;
    const offset = Math.sin(phase) * amplitude;
    const depth = (Math.cos(phase) + 1) * 0.5;
    const leftX = centerX - offset;
    const rightX = centerX + offset;
    const railAY = y + Math.cos(phase) * 26;
    const railBY = y - Math.cos(phase) * 26;

    railPointsA.push(`${leftX},${railAY}`);
    railPointsB.push(`${rightX},${railBY}`);
    rungs.push(
      `<line x1="${leftX}" y1="${y}" x2="${rightX}" y2="${y}" class="dna-bg__rung" style="opacity:${(0.28 + depth * 0.4).toFixed(3)}" />`
    );
    nodes.push(
      `<circle cx="${leftX}" cy="${railAY}" r="${(6 + depth * 5).toFixed(2)}" class="dna-bg__node dna-bg__node--a" style="opacity:${(0.34 + depth * 0.42).toFixed(3)}" />`
    );
    nodes.push(
      `<circle cx="${rightX}" cy="${railBY}" r="${(6 + (1 - depth) * 5).toFixed(2)}" class="dna-bg__node dna-bg__node--b" style="opacity:${(0.34 + (1 - depth) * 0.42).toFixed(3)}" />`
    );
  }

  return `
    <div class="dna-bg__glow dna-bg__glow--left"></div>
    <div class="dna-bg__glow dna-bg__glow--right"></div>
    <div class="dna-bg__helix-wrap">
      <svg class="dna-bg__helix" viewBox="0 0 640 1800" preserveAspectRatio="xMidYMid meet" role="presentation" aria-hidden="true">
        <defs>
          <linearGradient id="dna-rail-a" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#8ef3ff" />
            <stop offset="50%" stop-color="#2df0c2" />
            <stop offset="100%" stop-color="#8ef3ff" />
          </linearGradient>
          <linearGradient id="dna-rail-b" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#ffd37a" />
            <stop offset="50%" stop-color="#59e9ff" />
            <stop offset="100%" stop-color="#ffd37a" />
          </linearGradient>
          <linearGradient id="dna-rung" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#49f0d3" />
            <stop offset="50%" stop-color="#d7fdff" />
            <stop offset="100%" stop-color="#ffc86e" />
          </linearGradient>
          <filter id="dna-soft-glow" x="-40%" y="-20%" width="180%" height="140%">
            <feGaussianBlur stdDeviation="8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <g filter="url(#dna-soft-glow)">
          <polyline points="${railPointsA.join(" ")}" class="dna-bg__rail dna-bg__rail--a" />
          <polyline points="${railPointsB.join(" ")}" class="dna-bg__rail dna-bg__rail--b" />
          ${rungs.join("")}
          ${nodes.join("")}
        </g>
      </svg>
    </div>
    <div class="dna-bg__mesh"></div>
  `;
}

function initLoadingScreen() {
  const page = document.body;
  if (!page) return;
  page.classList.add("page-transition-entering");

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
  let transitionTimer = 0;
  let pageTurning = false;

  window.setTimeout(() => {
    page.classList.remove("page-transition-entering");
  }, 760);

  const showLoadingScreen = (message, options = {}) => {
    if (messageNode) {
      messageNode.textContent = message || "Opening the next screen...";
    }
    overlay.classList.toggle("is-minimal", options.minimal === true);
    page.classList.add("page-loading");
    page.setAttribute("aria-busy", "true");
    overlay.setAttribute("aria-hidden", "false");
  };

  const hideLoadingScreen = () => {
    window.clearTimeout(transitionTimer);
    pageTurning = false;
    page.classList.remove("page-loading");
    page.classList.remove("page-transition-leaving");
    page.removeAttribute("aria-busy");
    overlay.classList.remove("is-minimal");
    overlay.setAttribute("aria-hidden", "true");
  };

  const runPageTurn = (message, continueNavigation) => {
    if (pageTurning) return;
    pageTurning = true;
    showLoadingScreen(message, { minimal: true });
    page.classList.add("page-transition-leaving");
    transitionTimer = window.setTimeout(() => {
      continueNavigation();
    }, 430);
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
    if (form.dataset.skipPageTurn === "true") {
      showLoadingScreen(inferFormMessage(form, event.submitter));
      return;
    }
    if (form.dataset.submitting === "true") {
      delete form.dataset.submitting;
      showLoadingScreen(inferFormMessage(form, event.submitter));
      return;
    }
    event.preventDefault();
    runPageTurn(inferFormMessage(form, event.submitter), () => {
      form.dataset.submitting = "true";
      HTMLFormElement.prototype.submit.call(form);
    });
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
    event.preventDefault();
    runPageTurn(inferLinkMessage(link), () => {
      window.location.assign(url.toString());
    });
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
