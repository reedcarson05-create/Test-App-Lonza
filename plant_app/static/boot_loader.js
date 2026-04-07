document.addEventListener("DOMContentLoaded", () => {
  const manifestNode = document.getElementById("boot-manifest");
  if (!manifestNode) return;

  let manifest = {};
  try {
    manifest = JSON.parse(manifestNode.textContent || "{}");
  } catch (error) {
    console.error("Unable to parse boot manifest.", error);
  }

  const root = document.documentElement;
  const fillNode = document.querySelector("[data-boot-fill]");
  const percentNode = document.querySelector("[data-boot-percent]");
  const statusNode = document.querySelector("[data-boot-status]");
  const detailNode = document.querySelector("[data-boot-detail]");
  const eraNode = document.querySelector("[data-boot-era]");
  const phaseNodes = Array.from(document.querySelectorAll("[data-boot-phase-threshold]"));

  if (!fillNode || !percentNode || !statusNode || !detailNode || !eraNode) return;

  const targetUrl = manifest.target_url || "/?fresh=1";
  const minDurationMs = Math.max(Number(manifest.min_duration_ms) || 6200, 4200);
  const tasks = Array.isArray(manifest.tasks) ? manifest.tasks : [];
  const phases = [
    {
      threshold: 0,
      stage: "retro",
      era: "1988",
      headline: "Booting legacy control shell",
      detail: "Starting the old-school startup routine before the app swaps into modern UI layers.",
    },
    {
      threshold: 0.28,
      stage: "y2k",
      era: "1999",
      headline: "Refreshing the interface language",
      detail: "Upgrading the loading surface from pixel segments into polished gradients and glassier chrome.",
    },
    {
      threshold: 0.58,
      stage: "web",
      era: "2012",
      headline: "Caching shared plant app assets",
      detail: "Preloading scripts for signatures, corrections, image uploads, and the shared stylesheet.",
    },
    {
      threshold: 0.84,
      stage: "modern",
      era: "2026",
      headline: "Warming templates and login flow",
      detail: "Compiling the page stack and preparing the operator sign-in screen before handoff.",
    },
  ];

  let completedTasks = 0;
  let latestTaskLabel = tasks[0]?.label || "Preparing startup sequence";
  let displayProgress = 0;
  let resourcesReady = tasks.length === 0;
  let redirected = false;
  const startedAt = performance.now();

  const updatePhase = (progress) => {
    const activePhase = phases.reduce((current, phase) => (
      progress >= phase.threshold ? phase : current
    ), phases[0]);

    root.dataset.bootStage = activePhase.stage;
    eraNode.textContent = activePhase.era;
    statusNode.textContent = activePhase.headline;
    detailNode.textContent = latestTaskLabel || activePhase.detail;

    phaseNodes.forEach((node) => {
      const threshold = Number(node.dataset.bootPhaseThreshold || "1");
      node.classList.toggle("is-active", progress >= threshold);
    });
  };

  const renderProgress = (progress) => {
    const clamped = Math.max(0, Math.min(progress, 1));
    fillNode.style.width = `${(clamped * 100).toFixed(1)}%`;
    percentNode.textContent = `${Math.round(clamped * 100)}%`;
    updatePhase(clamped);
  };

  const preloadTask = async (task) => {
    latestTaskLabel = task.label || latestTaskLabel;
    try {
      const response = await fetch(task.url, {
        method: "GET",
        credentials: "same-origin",
        cache: "default",
      });
      if (!response.ok) {
        throw new Error(`Preload failed for ${task.url}: ${response.status}`);
      }

      if (task.kind === "image") {
        await response.blob();
      } else if (task.kind === "json") {
        await response.json();
      } else {
        await response.text();
      }
    } catch (error) {
      console.error("Boot preload task failed.", task, error);
    } finally {
      completedTasks += 1;
    }
  };

  Promise.allSettled(tasks.map(preloadTask)).then(() => {
    resourcesReady = true;
    latestTaskLabel = "Startup cache is ready. Opening secure operator login.";
  });

  const tick = (now) => {
    const elapsed = now - startedAt;
    const timeRatio = Math.min(elapsed / minDurationMs, 1);
    const taskRatio = tasks.length ? completedTasks / tasks.length : 1;
    let targetProgress = Math.max(timeRatio * 0.88, taskRatio * 0.94);

    if (resourcesReady && timeRatio >= 1) {
      targetProgress = 1;
    } else if (!resourcesReady && timeRatio >= 1) {
      targetProgress = Math.min(0.96, Math.max(targetProgress, 0.92));
    }

    displayProgress += (targetProgress - displayProgress) * (targetProgress >= 0.999 ? 0.2 : 0.09);
    if (targetProgress === 1 && 1 - displayProgress < 0.004) {
      displayProgress = 1;
    }

    renderProgress(displayProgress);

    if (displayProgress >= 1 && resourcesReady && timeRatio >= 1) {
      if (!redirected) {
        redirected = true;
        detailNode.textContent = "Startup complete. Handing off to operator login.";
        window.setTimeout(() => {
          window.location.replace(targetUrl);
        }, 420);
      }
      return;
    }

    window.requestAnimationFrame(tick);
  };

  root.dataset.bootStage = phases[0].stage;
  renderProgress(0);
  window.requestAnimationFrame(tick);
});
