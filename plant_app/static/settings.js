// Shared page chrome for settings persistence plus a reusable loading screen.
document.addEventListener("DOMContentLoaded", () => {
  initDnaBackground();
  initLoadingScreen();
  initSettingsPanel();
});

function initDnaBackground() {
  const page = document.body;
  if (!page || page.querySelector(".dna-bg")) return;

  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const layer = document.createElement("div");
  layer.className = "dna-bg";
  layer.setAttribute("aria-hidden", "true");
  layer.innerHTML = `
    <div class="dna-bg__glow dna-bg__glow--left"></div>
    <div class="dna-bg__glow dna-bg__glow--right"></div>
    <canvas class="dna-bg__canvas"></canvas>
    <div class="dna-bg__mesh"></div>
  `;
  page.prepend(layer);

  const canvas = layer.querySelector(".dna-bg__canvas");
  const ctx = canvas instanceof HTMLCanvasElement ? canvas.getContext("2d") : null;
  if (!canvas || !ctx) {
    layer.remove();
    return;
  }

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const mix = (start, end, amount) => start + (end - start) * amount;
  const blendRgb = (start, end, amount) => start.map((channel, index) => Math.round(mix(channel, end[index], amount)));
  const rgba = (rgb, alpha) => `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;

  let width = 0;
  let height = 0;
  let dpr = 1;
  let renderScale = 1;
  let spinAngle = Math.random() * Math.PI * 2;
  let riseOffset = 0;
  let scrollBoost = 0;
  let targetBoost = 0;
  let particles = [];
  let lastFrame = performance.now();
  let lastDraw = 0;
  let lastScrollY = window.scrollY;
  let lastScrollTime = lastFrame;

  const paletteForTheme = () => {
    const darkMode = document.documentElement.dataset.theme === "dark";
    if (darkMode) {
      return {
        rail: [119, 229, 255],
        railAlt: [77, 255, 210],
        rungA: [86, 255, 223],
        rungB: [255, 188, 84],
        particleA: [150, 244, 255],
        particleB: [255, 214, 129],
        ambient: [16, 84, 130],
        core: [15, 224, 193],
      };
    }

    return {
      rail: [92, 238, 255],
      railAlt: [51, 249, 204],
      rungA: [36, 240, 199],
      rungB: [255, 194, 96],
      particleA: [163, 248, 255],
      particleB: [255, 226, 151],
      ambient: [18, 114, 161],
      core: [18, 239, 204],
    };
  };

  const desiredParticleCount = () => {
    if (motionQuery.matches) return 8;
    if (width < 700) return 12;
    if (width < 1100) return 18;
    return 26;
  };

  const seedParticle = (particle = {}) => {
    particle.side = Math.random() < 0.5 ? -1 : 1;
    particle.life = particle.life ?? Math.random();
    particle.speed = 0.12 + Math.random() * 0.2;
    particle.size = 1.6 + Math.random() * 3.8;
    particle.outward = 28 + Math.random() * 128;
    particle.spin = (Math.random() - 0.5) * 1.3;
    particle.wobble = 0.8 + Math.random() * 2.3;
    particle.phaseOffset = Math.random() * Math.PI * 2;
    particle.seed = Math.random() * Math.PI * 2;
    particle.tint = Math.random();
    particle.lift = 8 + Math.random() * 24;
    return particle;
  };

  const syncParticles = () => {
    const desired = desiredParticleCount();
    while (particles.length < desired) {
      particles.push(seedParticle());
    }
    if (particles.length > desired) {
      particles = particles.slice(0, desired);
    }
  };

  const resizeCanvas = () => {
    width = window.innerWidth;
    height = window.innerHeight;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    renderScale = motionQuery.matches ? 0.44 : (width < 700 ? 0.42 : 0.5);
    canvas.width = Math.max(1, Math.round(width * dpr * renderScale));
    canvas.height = Math.max(1, Math.round(height * dpr * renderScale));
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr * renderScale, 0, 0, dpr * renderScale, 0, 0);
    ctx.imageSmoothingEnabled = true;
    syncParticles();
  };

  const projectPoint = (y, phase, side) => {
    const centerX = width * 0.5;
    const centerY = height * 0.48;
    const radius = Math.max(108, Math.min(width * 0.165, 196));
    const depthRange = Math.max(120, Math.min(width * 0.15, 220));
    const perspective = width < 700 ? 920 : 1180;
    const baseX = centerX + Math.sin(phase) * radius * side;
    const z = Math.cos(phase) * depthRange * side;
    const scale = perspective / (perspective - z);

    return {
      x: centerX + (baseX - centerX) * scale,
      y: centerY + (y - centerY) * scale,
      z,
      scale,
      depthRange,
    };
  };

  const buildHelixRows = () => {
    const spacing = width < 700 ? 62 : 72;
    const overscan = spacing * 6;
    const visibleSpan = height + overscan * 2;
    const count = Math.ceil(visibleSpan / spacing) + 2;
    const twistStep = 0.62;
    const rows = [];

    for (let index = 0; index < count; index += 1) {
      const y = height + overscan - ((index * spacing + riseOffset) % visibleSpan);
      const phase = spinAngle + index * twistStep;
      rows.push({
        a: projectPoint(y, phase, 1),
        b: projectPoint(y, phase, -1),
        phase,
      });
    }

    return rows;
  };

  const drawAmbientGlow = (palette, boost) => {
    const centerX = width * 0.5;
    const centerY = height * 0.46;
    const gradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, Math.max(width, height) * 0.42);
    gradient.addColorStop(0, rgba(palette.ambient, 0.22 + boost * 0.06));
    gradient.addColorStop(0.34, rgba(palette.core, 0.1 + boost * 0.04));
    gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
  };

  const drawHelix = (palette, boost) => {
    const rows = buildHelixRows();
    const depthRange = rows[0]?.a.depthRange || 180;
    const segments = [];
    const nodes = [];

    for (let index = 0; index < rows.length; index += 1) {
      const row = rows[index];
      const next = rows[index + 1];
      nodes.push({ point: row.a, z: row.a.z, tint: palette.rail });
      nodes.push({ point: row.b, z: row.b.z, tint: palette.railAlt });
      segments.push({
        kind: "rung",
        from: row.a,
        to: row.b,
        z: (row.a.z + row.b.z) * 0.5,
      });

      if (!next) continue;
      segments.push({
        kind: "rail",
        side: "a",
        from: row.a,
        to: next.a,
        z: (row.a.z + next.a.z) * 0.5,
        tint: palette.rail,
      });
      segments.push({
        kind: "rail",
        side: "b",
        from: row.b,
        to: next.b,
        z: (row.b.z + next.b.z) * 0.5,
        tint: palette.railAlt,
      });
    }

    segments.sort((left, right) => left.z - right.z);
    nodes.sort((left, right) => left.z - right.z);

    ctx.save();
    ctx.globalCompositeOperation = "lighter";

    for (const segment of segments) {
      const depthMix = clamp((segment.z + depthRange) / (depthRange * 2), 0, 1);
      const lineScale = mix(segment.from.scale, segment.to.scale, 0.5);

      if (segment.kind === "rail") {
        ctx.beginPath();
        ctx.moveTo(segment.from.x, segment.from.y);
        ctx.lineTo(segment.to.x, segment.to.y);
        ctx.strokeStyle = rgba(segment.tint, 0.16 + depthMix * 0.44);
        ctx.lineWidth = Math.max(1.2, (1.2 + depthMix * 3.1 + boost * 0.4) * lineScale);
        ctx.shadowBlur = 14 + depthMix * 22;
        ctx.shadowColor = rgba(segment.tint, 0.2 + depthMix * 0.24);
        ctx.stroke();

        ctx.shadowBlur = 0;
        ctx.beginPath();
        ctx.moveTo(segment.from.x, segment.from.y);
        ctx.lineTo(segment.to.x, segment.to.y);
        ctx.strokeStyle = `rgba(240, 254, 255, ${0.06 + depthMix * 0.16})`;
        ctx.lineWidth = Math.max(0.8, (0.6 + depthMix * 1.1) * lineScale);
        ctx.stroke();
        continue;
      }

      const rungGradient = ctx.createLinearGradient(segment.from.x, segment.from.y, segment.to.x, segment.to.y);
      rungGradient.addColorStop(0, rgba(palette.rungA, 0.18 + depthMix * 0.38));
      rungGradient.addColorStop(0.5, rgba(palette.particleA, 0.1 + depthMix * 0.2));
      rungGradient.addColorStop(1, rgba(palette.rungB, 0.16 + depthMix * 0.34));
      ctx.beginPath();
      ctx.moveTo(segment.from.x, segment.from.y);
      ctx.lineTo(segment.to.x, segment.to.y);
      ctx.strokeStyle = rungGradient;
      ctx.lineWidth = Math.max(0.8, (0.75 + depthMix * 1.4 + boost * 0.16) * lineScale);
      ctx.shadowBlur = 12 + depthMix * 16;
      ctx.shadowColor = rgba(palette.rungA, 0.12 + depthMix * 0.16);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    for (const node of nodes) {
      const depthMix = clamp((node.z + depthRange) / (depthRange * 2), 0, 1);
      const radius = Math.max(1.2, (1.2 + depthMix * 2.8 + boost * 0.24) * node.point.scale);
      const fill = ctx.createRadialGradient(node.point.x, node.point.y, 0, node.point.x, node.point.y, radius * 5.4);
      fill.addColorStop(0, `rgba(255, 255, 255, ${0.22 + depthMix * 0.34})`);
      fill.addColorStop(0.24, rgba(node.tint, 0.28 + depthMix * 0.48));
      fill.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = fill;
      ctx.beginPath();
      ctx.arc(node.point.x, node.point.y, radius * 5.4, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  };

  const drawParticles = (palette, dt, boost) => {
    const items = [];

    for (const particle of particles) {
      particle.life += dt * (particle.speed + boost * 0.16);
      if (particle.life > 1.08) {
        seedParticle(particle);
        particle.life = 0;
      }

      const progress = clamp(particle.life, 0, 1);
      const y = height + 90 - progress * (height + 180);
      const phase = spinAngle + particle.phaseOffset + progress * (5.4 + particle.spin);
      const origin = projectPoint(y, phase, particle.side);
      const spread = Math.pow(progress, 0.82) * particle.outward * (0.82 + boost * 0.22);
      const driftX =
        Math.cos(particle.seed + progress * (4.6 + particle.spin)) * spread +
        Math.sin((spinAngle + progress * 8.4) * particle.wobble + particle.seed) * (12 + particle.outward * 0.14);
      const driftY = Math.sin(particle.seed + progress * 11.4) * particle.lift;
      const tint = blendRgb(palette.particleA, palette.particleB, particle.tint);
      items.push({
        x: origin.x + driftX * origin.scale,
        y: origin.y + driftY,
        z: origin.z + progress * 60,
        color: tint,
        alpha: 0.08 + (1 - progress) * 0.5,
        size: particle.size * (0.55 + origin.scale * 0.82),
      });
    }

    items.sort((left, right) => left.z - right.z);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";

    for (const item of items) {
      const glow = ctx.createRadialGradient(item.x, item.y, 0, item.x, item.y, item.size * 5.6);
      glow.addColorStop(0, rgba(item.color, item.alpha));
      glow.addColorStop(0.42, rgba(item.color, item.alpha * 0.38));
      glow.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(item.x, item.y, item.size * 5.6, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = rgba(item.color, Math.min(0.92, item.alpha + 0.18));
      ctx.beginPath();
      ctx.arc(item.x, item.y, Math.max(0.8, item.size * 0.7), 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  };

  const animate = (timestamp) => {
    const dt = Math.min(0.05, Math.max(0.001, (timestamp - lastFrame) / 1000));
    lastFrame = timestamp;

    if (document.visibilityState === "hidden") {
      window.requestAnimationFrame(animate);
      return;
    }

    const targetFrameMs = motionQuery.matches ? 1000 / 14 : 1000 / 24;
    if (timestamp - lastDraw < targetFrameMs) {
      window.requestAnimationFrame(animate);
      return;
    }
    lastDraw = timestamp;

    scrollBoost = mix(scrollBoost, targetBoost, motionQuery.matches ? 0.08 : 0.1);
    targetBoost *= motionQuery.matches ? 0.8 : 0.9;

    const baseSpin = motionQuery.matches ? 0.12 : 0.28;
    const baseRise = motionQuery.matches ? 6 : 14;
    spinAngle += dt * (baseSpin + scrollBoost * 1.5);
    riseOffset += dt * (baseRise + scrollBoost * 78);

    ctx.setTransform(dpr * renderScale, 0, 0, dpr * renderScale, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const palette = paletteForTheme();
    drawAmbientGlow(palette, scrollBoost);
    drawHelix(palette, scrollBoost);
    drawParticles(palette, dt, scrollBoost);
    window.requestAnimationFrame(animate);
  };

  const handleScroll = () => {
    const now = performance.now();
    const currentY = window.scrollY;
    const distance = Math.abs(currentY - lastScrollY);
    const elapsed = Math.max(16, now - lastScrollTime);
    const velocity = distance / elapsed;
    targetBoost = clamp(targetBoost + velocity * (motionQuery.matches ? 0.2 : 0.8), 0, motionQuery.matches ? 0.25 : 0.85);
    lastScrollY = currentY;
    lastScrollTime = now;
  };

  resizeCanvas();
  window.addEventListener("resize", resizeCanvas);
  window.addEventListener("scroll", handleScroll, { passive: true });
  if (typeof motionQuery.addEventListener === "function") {
    motionQuery.addEventListener("change", resizeCanvas);
  } else if (typeof motionQuery.addListener === "function") {
    motionQuery.addListener(resizeCanvas);
  }
  window.requestAnimationFrame(animate);
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
