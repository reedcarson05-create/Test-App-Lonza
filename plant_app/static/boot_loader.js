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
  const phaseNodes = Array.from(document.querySelectorAll("[data-boot-phase-threshold]"));

  if (!fillNode || !percentNode || !statusNode || !detailNode) return;

  const targetUrl = manifest.target_url || "/?fresh=1";
  const minDurationMs = Math.max(Number(manifest.min_duration_ms) || 1200, 900);
  const tasks = Array.isArray(manifest.tasks) ? manifest.tasks : [];
  const phases = [
    {
      threshold: 0,
      stage: "modern",
      status: "Initializing",
      detail: "Starting session services and authentication.",
    },
    {
      threshold: 0.4,
      stage: "modern",
      status: "Loading Resources",
      detail: "Preparing interface components and assets.",
    },
    {
      threshold: 0.68,
      stage: "modern",
      status: "Syncing Data",
      detail: "Retrieving the latest production records.",
    },
    {
      threshold: 0.87,
      stage: "modern",
      status: "Ready",
      detail: "Handing off to the workspace.",
    },
  ];

  let completedTasks = 0;
  let displayProgress = 0;
  let resourcesReady = tasks.length === 0;
  let redirected = false;
  const startedAt = performance.now();
  const easeAccelerating = (value, power) => Math.pow(Math.max(0, Math.min(value, 1)), power);

  const updatePhase = (progress) => {
    const activePhase = phases.reduce((current, phase) => (
      progress >= phase.threshold ? phase : current
    ), phases[0]);

    root.dataset.bootStage = activePhase.stage;
    statusNode.textContent = activePhase.status;
    detailNode.textContent = activePhase.detail;

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
  });

  const tick = (now) => {
    const elapsed = now - startedAt;
    const timeRatio = Math.min(elapsed / minDurationMs, 1);
    const taskRatio = tasks.length ? completedTasks / tasks.length : 1;
    const easedTimeRatio = easeAccelerating(timeRatio, 1.85);
    const easedTaskRatio = easeAccelerating(taskRatio, 1.35);
    let targetProgress = Math.min(0.97, easedTimeRatio * 0.8 + easedTaskRatio * 0.16);

    if (resourcesReady && timeRatio >= 1) {
      targetProgress = 1;
    } else if (!resourcesReady && timeRatio >= 1) {
      targetProgress = Math.min(0.96, Math.max(targetProgress, 0.92));
    }

    const chaseRate = targetProgress >= 0.999 ? 0.18 : 0.025 + timeRatio * 0.085;
    displayProgress += (targetProgress - displayProgress) * chaseRate;
    if (targetProgress === 1 && 1 - displayProgress < 0.004) {
      displayProgress = 1;
    }

    renderProgress(displayProgress);

    if (displayProgress >= 1 && resourcesReady && timeRatio >= 1) {
      if (!redirected) {
        redirected = true;
        window.setTimeout(() => {
          window.location.replace(targetUrl);
        }, 120);
      }
      return;
    }

    window.requestAnimationFrame(tick);
  };

  root.dataset.bootStage = phases[0].stage;
  renderProgress(0);
  window.requestAnimationFrame(tick);
});
