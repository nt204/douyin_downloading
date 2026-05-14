const form = document.getElementById("job-form");
const submitBtn = document.getElementById("submit-btn");
const emptyState = document.getElementById("empty-state");
const jobState = document.getElementById("job-state");
const progressBar = document.getElementById("progress-bar");
const progressLabel = document.getElementById("progress-label");
const stageLabel = document.getElementById("stage-label");
const metaLabel = document.getElementById("meta-label");
const resultPanel = document.getElementById("result-panel");
const errorPanel = document.getElementById("error-panel");
const errorMessage = document.getElementById("error-message");
const videoTitle = document.getElementById("video-title");
const videoMeta = document.getElementById("video-meta");
const downloadVideo = document.getElementById("download-video");
const downloadSrt = document.getElementById("download-srt");

const POLL_INTERVALS = [1000, 1000, 2000, 2000, 3000];

function setLoading(loading) {
  submitBtn.disabled = loading;
  submitBtn.textContent = loading ? "Dang gui..." : "Tao job";
}

function showJobShell() {
  emptyState.classList.add("hidden");
  jobState.classList.remove("hidden");
  resultPanel.classList.add("hidden");
  errorPanel.classList.add("hidden");
}

function updateProgress(data) {
  showJobShell();
  const progress = Number(data.progress || 0);
  progressBar.style.width = `${progress}%`;
  progressLabel.textContent = `${progress}%`;
  stageLabel.textContent = data.stage_label || data.stage || "Dang xu ly...";
  metaLabel.textContent = `Job ${data.job_id} • Stage: ${data.stage}`;
}

function showError(message) {
  errorPanel.classList.remove("hidden");
  resultPanel.classList.add("hidden");
  errorMessage.textContent = message;
}

function showDone(data) {
  resultPanel.classList.remove("hidden");
  errorPanel.classList.add("hidden");
  videoTitle.textContent = data.video_title || "Video hoan tat";
  videoMeta.textContent = `${data.subtitle_count || 0} dong subtitle • ${Math.round(data.duration_seconds || 0)}s`;
  downloadVideo.href = data.download_url;
  downloadSrt.href = data.srt_url;
}

async function pollJob(jobId) {
  let attempt = 0;
  while (true) {
    const res = await fetch(`/api/jobs/${jobId}`);
    const data = await res.json();
    updateProgress(data);

    if (data.status === "done") {
      showDone(data);
      break;
    }

    if (data.status === "error") {
      showError(data.error || "Co loi xay ra.");
      break;
    }

    const delay = POLL_INTERVALS[Math.min(attempt, POLL_INTERVALS.length - 1)];
    attempt += 1;
    await new Promise((resolve) => setTimeout(resolve, delay));
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading(true);
  showJobShell();
  updateProgress({ job_id: "...", progress: 0, stage: "queued", stage_label: "Dang tao job..." });

  const payload = {
    url: document.getElementById("url").value.trim(),
    options: {
      font_size: Number(document.getElementById("font-size").value),
      font_color: document.getElementById("font-color").value,
      position: document.getElementById("position").value,
    },
  };

  try {
    const res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Khong tao duoc job.");
    }
    await pollJob(data.job_id);
  } catch (error) {
    showError(error.message || "Khong the ket noi server.");
  } finally {
    setLoading(false);
  }
});
