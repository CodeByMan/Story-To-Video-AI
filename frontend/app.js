(() => {
  "use strict";

  const form = document.querySelector("#generate-form");
  const topicInput = document.querySelector("#topic");
  const characterCount = document.querySelector("#character-count");
  const generateButton = document.querySelector("#generate-button");
  const statusPill = document.querySelector("#job-status");
  const emptyState = document.querySelector("#preview-empty");
  const progressPanel = document.querySelector("#progress-panel");
  const progressTitle = document.querySelector("#progress-title");
  const progressPercent = document.querySelector("#progress-percent");
  const progressBar = document.querySelector("#progress-bar");
  const videoResult = document.querySelector("#video-result");
  const videoPlayer = document.querySelector("#video-player");
  const downloadLink = document.querySelector("#download-link");
  const resultTopic = document.querySelector("#result-topic");
  const errorPanel = document.querySelector("#error-panel");
  const errorMessage = document.querySelector("#error-message");
  const retryButton = document.querySelector("#retry-button");
  const localBadge = document.querySelector(".local-badge");
  let pollTimer = null;
  let pollStartedAt = 0;

  const stages = ["queued", "script", "voice", "render"];
  const stageCopy = {
    queued: ["In the queue", 12],
    script: ["Writing your story", 31],
    voice: ["Creating the voiceover", 57],
    render: ["Assembling the final video", 78],
  };

  function setStatus(label, state) {
    statusPill.textContent = label;
    statusPill.className = `status-pill ${state}`;
  }

  function updateCount() {
    characterCount.textContent = `${topicInput.value.length} / 500`;
  }

  function showView(view) {
    emptyState.classList.toggle("hidden", view !== "empty");
    progressPanel.classList.toggle("hidden", view !== "progress");
    videoResult.classList.toggle("hidden", view !== "result");
    errorPanel.classList.toggle("hidden", view !== "error");
  }

  function setLoading(loading) {
    generateButton.disabled = loading;
    generateButton.classList.toggle("is-loading", loading);
    generateButton.querySelector(".button-label").textContent = loading ? "Generating..." : "Generate video";
  }

  function updateSteps(activeStage) {
    const activeIndex = stages.indexOf(activeStage);
    document.querySelectorAll(".pipeline-step").forEach((step) => {
      const index = stages.indexOf(step.dataset.step);
      step.classList.toggle("active", index === activeIndex);
      step.classList.toggle("done", index >= 0 && index < activeIndex);
    });
  }

  function showProgress(stage) {
    const [title, percent] = stageCopy[stage] || stageCopy.queued;
    showView("progress");
    setStatus("Working", "working");
    progressTitle.textContent = title;
    progressPercent.textContent = `${percent}%`;
    progressBar.style.width = `${percent}%`;
    updateSteps(stage);
  }

  function showError(message) {
    clearTimeout(pollTimer);
    pollTimer = null;
    setLoading(false);
    setStatus("Needs attention", "error");
    errorMessage.textContent = message;
    showView("error");
  }

  function inferStage(status) {
    if (status === "queued") return "queued";
    const elapsed = Date.now() - pollStartedAt;
    if (elapsed < 4500) return "script";
    if (elapsed < 11000) return "voice";
    return "render";
  }

  async function readJson(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `Request failed with status ${response.status}`);
    }
    return data;
  }

  async function pollJob(jobId) {
    try {
      const job = await readJson(await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, { cache: "no-store" }));
      if (job.status === "completed") {
        clearTimeout(pollTimer);
        pollTimer = null;
        setLoading(false);
        setStatus("Complete", "success");
        progressBar.style.width = "100%";
        progressPercent.textContent = "100%";
        updateSteps("render");
        videoPlayer.src = job.download_url;
        downloadLink.href = job.download_url;
        resultTopic.textContent = job.topic;
        showView("result");
        return;
      }
      if (job.status === "failed") {
        showError(job.error || "The local pipeline could not finish this video.");
        return;
      }
      showProgress(inferStage(job.status));
      pollTimer = setTimeout(() => pollJob(jobId), 1200);
    } catch (error) {
      showError(error.message || "The local server could not be reached.");
    }
  }

  async function submitTopic(event) {
    event.preventDefault();
    const topic = topicInput.value.trim();
    if (!topic) {
      topicInput.focus();
      showError("Enter an English topic before generating a video.");
      return;
    }

    clearTimeout(pollTimer);
    pollTimer = null;
    setLoading(true);
    showProgress("queued");
    pollStartedAt = Date.now();

    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic }),
      });
      const job = await readJson(response);
      await pollJob(job.id);
    } catch (error) {
      showError(error.message || "The local server could not start the job.");
    }
  }

  async function checkHealth() {
    try {
      const health = await readJson(await fetch("/api/health", { cache: "no-store" }));
      if (health.status === "ok") {
        localBadge.innerHTML = '<span class="status-dot"></span> Local workspace';
        setStatus("Ready", "ready");
      }
    } catch (_error) {
      localBadge.innerHTML = '<span class="status-dot"></span> Start local server';
      setStatus("Offline", "error");
    }
  }

  topicInput.addEventListener("input", updateCount);
  form.addEventListener("submit", submitTopic);
  retryButton.addEventListener("click", () => {
    showView("empty");
    setStatus("Ready", "ready");
    topicInput.focus();
  });
  document.querySelectorAll(".example-chip").forEach((button) => {
    button.addEventListener("click", () => {
      topicInput.value = button.dataset.topic || "";
      updateCount();
      topicInput.focus();
    });
  });

  updateCount();
  checkHealth();
})();
