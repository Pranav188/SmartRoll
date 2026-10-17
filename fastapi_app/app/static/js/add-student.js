import { apiFetch } from "./app.js";

const form = document.querySelector("#enrollment-form");
const nameInput = document.querySelector("#student-name");
const nameError = document.querySelector("#name-error");
const photoInput = document.querySelector("#student-photos");
const photosError = document.querySelector("#photos-error");
const selectedPhotos = document.querySelector("#selected-photos");
const submitButton = document.querySelector("#enroll-student");
const retryButton = document.querySelector("#retry-enrollment");
const statusPanel = document.querySelector("#enrollment-status");
const statusTitle = document.querySelector("#enrollment-status-title");
const statusCopy = document.querySelector("#enrollment-status-copy");
const statusSection = document.querySelector(".enrollment-submit");
const jobMeta = document.querySelector("#enrollment-job-meta");
const jobIdNode = document.querySelector("#enrollment-job-id");

let studentId = null;
let currentJobId = null;
let pollTimer = null;
let pendingPollCount = 0;

function setStatus(tone, title, copy, busy = false) {
  statusPanel.dataset.tone = tone;
  statusTitle.textContent = title;
  statusCopy.textContent = copy;
  statusSection.setAttribute("aria-busy", String(busy));
}

function setFieldError(input, node, message) {
  node.textContent = message;
  node.hidden = !message;
  input.setAttribute("aria-invalid", String(Boolean(message)));
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KiB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function validateFiles(files) {
  if (!files.length) return "Choose at least one enrollment photo.";
  if (files.length > 10) return "Choose no more than ten enrollment photos.";
  const invalidType = files.find((file) => !["image/jpeg", "image/png"].includes(file.type));
  if (invalidType) return `${invalidType.name} is not a JPEG or PNG image.`;
  const tooLarge = files.find((file) => file.size > 10 * 1024 * 1024);
  if (tooLarge) return `${tooLarge.name} is larger than 10 MiB.`;
  return null;
}

function renderPhotos() {
  const files = [...(photoInput.files || [])];
  selectedPhotos.innerHTML = "";
  const validationError = validateFiles(files);
  setFieldError(photoInput, photosError, files.length ? validationError : "");
  files.forEach((file) => {
    const row = document.createElement("li");
    const invalid = !["image/jpeg", "image/png"].includes(file.type) || file.size > 10 * 1024 * 1024;
    if (invalid) row.dataset.state = "invalid";
    const name = document.createElement("span");
    name.textContent = file.name;
    const detail = document.createElement("small");
    detail.textContent = invalid ? "Choose another file" : formatBytes(file.size);
    row.append(name, detail);
    selectedPhotos.append(row);
  });
}

function validateForm() {
  const name = nameInput.value.trim();
  const files = [...(photoInput.files || [])];
  const nameMessage = name ? "" : "Enter the student's full name.";
  const photosMessage = validateFiles(files);
  setFieldError(nameInput, nameError, nameMessage);
  setFieldError(photoInput, photosError, photosMessage);
  if (nameMessage) nameInput.focus();
  else if (photosMessage) photoInput.focus();
  return !nameMessage && !photosMessage;
}

async function createStudentIfNeeded() {
  if (studentId) return studentId;
  const student = await apiFetch("/api/students", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: nameInput.value.trim() }),
  });
  studentId = student.id;
  nameInput.disabled = true;
  return studentId;
}

async function pollJob() {
  try {
    const job = await apiFetch(`/api/jobs/${currentJobId}`);
    if (job.state === "succeeded") {
      window.clearTimeout(pollTimer);
      const accepted = Number(job.result?.accepted_count || 0);
      const rejected = Array.isArray(job.result?.rejected) ? job.result.rejected.length : 0;
      setStatus(
        rejected ? "review" : "success",
        "Enrollment ready",
        `${accepted} ${accepted === 1 ? "photo is" : "photos are"} ready for recognition${rejected ? `; ${rejected} could not be used.` : "."}`,
      );
      submitButton.textContent = "View roster";
      submitButton.type = "button";
      submitButton.disabled = false;
      submitButton.addEventListener("click", () => { window.location.href = "/students"; }, { once: true });
      photoInput.disabled = true;
      return;
    }
    if (job.state === "failed" || job.state === "dispatch_failed") {
      const canRetryDispatch = job.state === "dispatch_failed";
      setStatus(
        "error",
        canRetryDispatch ? "Encoding could not start" : "Photos could not be encoded",
        job.error_message || (canRetryDispatch ? "The worker is unavailable. Retry encoding when it is running." : "Choose different photos containing one clear face each."),
      );
      retryButton.hidden = !canRetryDispatch;
      submitButton.disabled = false;
      submitButton.textContent = "Upload different photos";
      return;
    }
    pendingPollCount = job.state === "pending" ? pendingPollCount + 1 : 0;
    retryButton.hidden = pendingPollCount < 3;
    setStatus(
      "active",
      job.state === "running" ? "Encoding face samples" : "Encoding queued",
      job.state === "running" ? "Each photo is being checked for one usable face." : "The worker will start shortly.",
      true,
    );
    pollTimer = window.setTimeout(pollJob, 1200);
  } catch (_) {
    setStatus("error", "Status could not update", "The job may still be running. Check the connection, then reload the roster to confirm.");
    submitButton.disabled = false;
  }
}

async function submitEnrollment(event) {
  event.preventDefault();
  if (!validateForm()) return;
  submitButton.disabled = true;
  retryButton.hidden = true;
  setStatus("active", studentId ? "Uploading new photos" : "Creating student", "Keep this page open while the enrollment starts.", true);
  try {
    const id = await createStudentIfNeeded();
    const data = new FormData();
    [...photoInput.files].forEach((file) => data.append("photos", file));
    const job = await apiFetch(`/api/students/${id}/photos`, { method: "POST", body: data });
    currentJobId = job.job_id;
    pendingPollCount = 0;
    jobIdNode.textContent = job.job_id;
    jobMeta.hidden = false;
    if (job.state === "dispatch_failed") {
      setStatus("error", "Encoding could not start", "The student was created, but the worker is unavailable. Retry encoding when it is running.");
      retryButton.hidden = false;
      submitButton.disabled = false;
      return;
    }
    setStatus("active", "Encoding queued", "The worker will check each photo for one usable face.", true);
    pollTimer = window.setTimeout(pollJob, 500);
  } catch (error) {
    const prefix = studentId ? "The student was created, but the photos were not uploaded." : "Enrollment could not start.";
    setStatus("error", prefix, error.message || "Check the details and try again.");
    submitButton.disabled = false;
  }
}

async function retryEnrollment() {
  if (!currentJobId) return;
  retryButton.disabled = true;
  setStatus("active", "Retrying encoding", "SmartRoll is sending these photos back to the worker.", true);
  try {
    const job = await apiFetch(`/api/jobs/${currentJobId}/retry`, { method: "POST" });
    if (job.state === "dispatch_failed") {
      setStatus("error", "Encoding could not start", "The worker is still unavailable. Try again later.");
      return;
    }
    retryButton.hidden = true;
    pendingPollCount = 0;
    pollTimer = window.setTimeout(pollJob, 500);
  } catch (error) {
    setStatus("error", "Retry could not start", error.message || "Check the connection and try again.");
  } finally {
    retryButton.disabled = false;
  }
}

photoInput.addEventListener("change", renderPhotos);
nameInput.addEventListener("input", () => setFieldError(nameInput, nameError, ""));
form.addEventListener("submit", submitEnrollment);
retryButton.addEventListener("click", retryEnrollment);
