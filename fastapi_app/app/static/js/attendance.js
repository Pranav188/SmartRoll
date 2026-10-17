import { apiFetch, formatDate } from "./app.js";

const input = document.querySelector("#classroom-photo");
const preview = document.querySelector("#photo-preview");
const processedImage = document.querySelector("#processed-image");
const uploadEmpty = document.querySelector("#upload-empty");
const proofFrame = document.querySelector("#proof-frame");
const proofActions = document.querySelector("#proof-actions");
const mobileProofActions = document.querySelector("#proof-actions-mobile");
const selectedFile = document.querySelector("#selected-file");
const mobileSelectedFile = document.querySelector("#selected-file-mobile");
const replacePhotoButtons = document.querySelectorAll("#replace-photo, [data-replace-photo]");
const removePhotoButtons = document.querySelectorAll("#remove-photo, [data-remove-photo]");
const startButton = document.querySelector("#start-recognition");
const photoMessage = document.querySelector("#photo-message");
const scanPanel = document.querySelector("#scan-panel");
const statusMessage = document.querySelector("#status-message");
const jobMeta = document.querySelector("#job-meta");
const jobId = document.querySelector("#job-job-id") || document.querySelector("#job-id");
const jobStarted = document.querySelector("#job-started");
const retryButton = document.querySelector("#retry-job");
const results = document.querySelector("#recognition-results");
const steps = [...document.querySelectorAll("[data-process-step]")];

let objectUrl = null;
let currentJobId = null;
let pollTimer = null;
let selectedPhoto = null;
let pendingPollCount = 0;

function setStep(activeStep) {
  const order = ["upload", "process", "review"];
  const activeIndex = order.indexOf(activeStep);
  steps.forEach((step) => {
    const index = order.indexOf(step.dataset.processStep);
    step.removeAttribute("aria-current");
    delete step.dataset.complete;
    if (index === activeIndex) step.setAttribute("aria-current", "step");
    if (index < activeIndex) step.dataset.complete = "true";
  });
}

function setState(state, title, copy) {
  const tone = ["selected", "validating", "queued", "processing"].includes(state)
    ? "active"
    : state === "succeeded"
      ? "success"
      : state === "needs_review"
        ? "review"
        : ["invalid", "failed", "expired"].includes(state)
          ? "error"
          : "idle";
  statusMessage.dataset.tone = tone;
  statusMessage.querySelector("h3").textContent = title;
  statusMessage.querySelector("p").textContent = copy;
  scanPanel.setAttribute("aria-busy", String(["validating", "queued", "processing"].includes(state)));
  proofFrame.dataset.state = state === "queued" || state === "processing" ? "processing" : state;
}

function showPhotoError(message) {
  photoMessage.textContent = message;
  photoMessage.hidden = false;
  input.setAttribute("aria-invalid", "true");
  setState("invalid", "Choose a different photo", message);
}

function clearPhotoError() {
  photoMessage.hidden = true;
  input.removeAttribute("aria-invalid");
}

function resetResults() {
  results.hidden = true;
  retryButton.hidden = true;
  processedImage.hidden = true;
  processedImage.removeAttribute("src");
}

function revokePreview() {
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  objectUrl = null;
}

function validatePhoto(file) {
  if (!file) return "Choose a classroom photo.";
  if (!["image/jpeg", "image/png"].includes(file.type)) return "Choose a JPEG or PNG image.";
  if (file.size > 20 * 1024 * 1024) return "Choose a class photo smaller than 20 MiB.";
  return null;
}

function selectPhoto(file) {
  clearPhotoError();
  resetResults();
  const error = validatePhoto(file);
  if (error) {
    selectedPhoto = null;
    startButton.disabled = true;
    showPhotoError(error);
    return;
  }

  selectedPhoto = file;
  revokePreview();
  objectUrl = URL.createObjectURL(file);
  preview.src = objectUrl;
  preview.hidden = false;
  uploadEmpty.hidden = true;
  proofActions.hidden = false;
  mobileProofActions.hidden = false;
  const fileDescription = `${file.name} · ${formatBytes(file.size)}`;
  selectedFile.textContent = fileDescription;
  mobileSelectedFile.textContent = fileDescription;
  startButton.disabled = false;
  setStep("upload");
  setState("selected", "Photo selected", "Start recognition when you are ready to upload and process it.");
}

function clearPhoto() {
  selectedPhoto = null;
  input.value = "";
  revokePreview();
  preview.hidden = true;
  preview.removeAttribute("src");
  processedImage.hidden = true;
  uploadEmpty.hidden = false;
  proofActions.hidden = true;
  mobileProofActions.hidden = true;
  startButton.disabled = true;
  clearPhotoError();
  resetResults();
  setStep("upload");
  setState("idle", "Ready for a class photo", "Choose a photo to begin. Nothing is uploaded until you start recognition.");
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KiB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function describeReview(item) {
  const candidates = Array.isArray(item?.candidates) ? item.candidates : [];
  if (candidates.length) return candidates.map((candidate) => candidate.name).filter(Boolean).join(" or ");
  if (item?.reason === "unknown_face") return "No roster match";
  return "Ambiguous match";
}

function renderNamedList(listId, countId, items, formatter) {
  const list = document.querySelector(`#${listId}`);
  const count = document.querySelector(`#${countId}`);
  list.innerHTML = "";
  count.textContent = String(items.length);
  if (!items.length) {
    const empty = document.createElement("li");
    empty.className = "result-empty";
    empty.textContent = "None";
    list.append(empty);
    return;
  }
  items.forEach((item, index) => {
    const row = document.createElement("li");
    const content = formatter(item, index);
    const label = document.createElement("span");
    label.textContent = content.label;
    row.append(label);
    if (content.detail) {
      const detail = document.createElement("small");
      detail.textContent = content.detail;
      row.append(detail);
    }
    list.append(row);
  });
}

function showResults(payload) {
  if (payload.expired) {
    resetResults();
    setStep("review");
    setState(
      "expired",
      "This scan has expired",
      "Choose the class photo again to run a new recognition scan.",
    );
    return;
  }

  const recognized = Array.isArray(payload.recognized_students) ? payload.recognized_students : [];
  const needsReview = Array.isArray(payload.needs_review) ? payload.needs_review : [];
  const notRecognized = Array.isArray(payload.not_recognized_students) ? payload.not_recognized_students : [];

  renderNamedList("recognized-list", "recognized-count", recognized, (item) => ({
    label: item.name || "Recognized student",
  }));
  renderNamedList("review-list", "review-count", needsReview, (item, index) => ({
    label: `Face ${index + 1}`,
    detail: describeReview(item),
  }));
  renderNamedList("not-recognized-list", "not-recognized-count", notRecognized, (item) => ({
    label: item.name || "Roster student",
  }));

  const unknownCount = Number(payload.unknown_face_count || 0);
  document.querySelector("#unknown-summary").textContent = unknownCount === 1
    ? "1 face had no roster match."
    : `${unknownCount} faces had no roster match.`;
  results.hidden = false;

  if (payload.processed_image_url) {
    processedImage.onload = () => {
      preview.hidden = true;
      processedImage.hidden = false;
    };
    processedImage.onerror = () => {
      processedImage.hidden = true;
      preview.hidden = false;
      setState("expired", "Processed image expired", "The result list is still available, but the annotated photo is no longer stored.");
    };
    processedImage.src = `${payload.processed_image_url}?t=${Date.now()}`;
  }

  setStep("review");
  if (needsReview.length) {
    setState("needs_review", "Recognition finished. Review the suggestions.", `${needsReview.length} ${needsReview.length === 1 ? "face needs" : "faces need"} your attention.`);
  } else {
    setState("succeeded", "Recognition finished. Review the suggestions.", "Every detected face has been grouped for review.");
  }
}

function handleFailedJob(job) {
  window.clearTimeout(pollTimer);
  setStep("process");
  const message = ["no_face", "no_faces"].includes(job.error_code)
    ? "No face was found. Choose a clearer photo."
    : job.error_message || "Processing stopped. Retry this scan.";
  setState("failed", "Processing stopped", message);
  retryButton.hidden = [
    "no_face",
    "no_faces",
    "invalid_image",
    "multiple_faces",
    "attempts_exhausted",
    "enrollment_rejected",
    "target_deleted",
    "invalid_job_input",
  ].includes(job.error_code);
  startButton.disabled = false;
}

async function pollJob() {
  try {
    const job = await apiFetch(`/api/jobs/${currentJobId}`);
    if (job.started_at) jobStarted.textContent = formatDate(job.started_at);
    if (job.error_code === "expired" || job.result?.expired) {
      window.clearTimeout(pollTimer);
      retryButton.hidden = true;
      startButton.disabled = false;
      setStep("review");
      setState(
        "expired",
        "This scan has expired",
        "Choose the class photo again to run a new recognition scan.",
      );
      return;
    }
    if (job.state === "succeeded") {
      window.clearTimeout(pollTimer);
      startButton.disabled = false;
      showResults(job.result || {});
      return;
    }
    if (job.state === "failed" || job.state === "dispatch_failed") {
      handleFailedJob(job);
      if (job.state === "dispatch_failed") retryButton.hidden = false;
      return;
    }
    pendingPollCount = job.state === "pending" ? pendingPollCount + 1 : 0;
    retryButton.hidden = pendingPollCount < 3;
    setStep("process");
    setState(
      job.state === "running" ? "processing" : "queued",
      job.state === "running" ? "Scanning the class photo" : "Recognition queued",
      job.state === "running" ? "Faces are being compared with enrolled students." : "The worker will start this scan shortly.",
    );
    pollTimer = window.setTimeout(pollJob, 1200);
  } catch (_) {
    setState("failed", "Status could not update", "The scan may still be running. Check the connection and retry the status request.");
    retryButton.hidden = true;
    startButton.disabled = false;
  }
}

async function submitRecognition() {
  if (!selectedPhoto) return;
  clearPhotoError();
  resetResults();
  startButton.disabled = true;
  setStep("process");
  setState("validating", "Checking the photo", "SmartRoll is validating the file before the scan starts.");
  const data = new FormData();
  data.append("classroom_photo", selectedPhoto);
  try {
    const job = await apiFetch("/api/recognition-jobs", { method: "POST", body: data });
    currentJobId = job.job_id;
    pendingPollCount = 0;
    jobId.textContent = job.job_id;
    jobStarted.textContent = "Waiting for worker";
    jobMeta.hidden = false;
    if (job.state === "dispatch_failed") {
      setState("failed", "Processing could not start", "The worker is unavailable. Retry this scan when it is running.");
      retryButton.hidden = false;
      return;
    }
    setState("queued", "Recognition queued", "The worker will start this scan shortly.");
    pollTimer = window.setTimeout(pollJob, 500);
  } catch (error) {
    startButton.disabled = false;
    setStep("upload");
    showPhotoError(error.message || "The photo could not be uploaded. Try again.");
  }
}

async function retryJob() {
  if (!currentJobId) return;
  retryButton.disabled = true;
  setState("queued", "Retry queued", "SmartRoll is sending this scan back to the worker.");
  try {
    const job = await apiFetch(`/api/jobs/${currentJobId}/retry`, { method: "POST" });
    if (job.state === "dispatch_failed") {
      setState("failed", "Processing could not start", "The worker is still unavailable. Try again later.");
      return;
    }
    retryButton.hidden = true;
    pendingPollCount = 0;
    pollTimer = window.setTimeout(pollJob, 500);
  } catch (error) {
    setState("failed", "Retry could not start", error.message || "Check the connection and try again.");
  } finally {
    retryButton.disabled = false;
  }
}

input.addEventListener("change", () => selectPhoto(input.files?.[0]));
replacePhotoButtons.forEach((button) => button.addEventListener("click", () => input.click()));
removePhotoButtons.forEach((button) => button.addEventListener("click", clearPhoto));
startButton.addEventListener("click", submitRecognition);
retryButton.addEventListener("click", retryJob);
window.addEventListener("beforeunload", revokePreview);
