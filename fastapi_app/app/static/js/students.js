import { apiFetch, debounce } from "./app.js";

const search = document.querySelector("#student-search");
const rows = document.querySelector("#student-rows");
const tableWrap = document.querySelector("#roster-table-wrap");
const empty = document.querySelector("#roster-empty");
const emptyTitle = document.querySelector("#empty-title");
const emptyCopy = document.querySelector("#empty-copy");
const emptyAction = document.querySelector("#empty-action");
const count = document.querySelector("#student-count");
const errorPanel = document.querySelector("#roster-error");
const reloadButton = document.querySelector("#reload-roster");
const dialog = document.querySelector("#delete-dialog");
const cancelDelete = document.querySelector("#cancel-delete");
const confirmDelete = document.querySelector("#confirm-delete");
const deleteName = document.querySelector("#delete-student-name");
const deleteError = document.querySelector("#delete-error");

let selectedStudent = null;
let restoreFocus = null;

const enrollmentNotes = {
  pending: "Processing photos",
  failed: "Photos could not be processed",
  none: "Photos needed",
};

function openDeleteDialog(student, trigger) {
  selectedStudent = student;
  restoreFocus = trigger;
  deleteName.textContent = student.name;
  deleteError.hidden = true;
  confirmDelete.disabled = false;
  dialog.showModal();
  window.setTimeout(() => cancelDelete.focus(), 0);
}

function studentRow(student) {
  const row = document.createElement("tr");
  const nameCell = document.createElement("td");
  const identity = document.createElement("span");
  identity.className = "student-name";
  identity.textContent = student.name;
  nameCell.append(identity);
  if (student.enrollment_state !== "ready") {
    const note = document.createElement("span");
    note.className = "enrollment-note";
    note.textContent = enrollmentNotes[student.enrollment_state || "none"] || "Enrollment needs review";
    nameCell.append(note);
  }

  const actionCell = document.createElement("td");
  const deleteButton = document.createElement("button");
  deleteButton.className = "row-action";
  deleteButton.type = "button";
  deleteButton.textContent = "Delete";
  deleteButton.setAttribute("aria-label", `Delete ${student.name}`);
  deleteButton.addEventListener("click", () => openDeleteDialog(student, deleteButton));
  actionCell.append(deleteButton);
  row.append(nameCell, actionCell);
  return row;
}

function renderRoster(payload, query) {
  rows.innerHTML = "";
  payload.items.forEach((student) => rows.append(studentRow(student)));
  count.textContent = `${payload.total} ${payload.total === 1 ? "student" : "students"}`;
  const noResults = payload.items.length === 0;
  tableWrap.hidden = noResults;
  empty.hidden = !noResults;
  errorPanel.hidden = true;

  if (noResults && query) {
    emptyTitle.textContent = "No matching students";
    emptyCopy.textContent = `No roster names match “${query}”. Try a different search.`;
    emptyAction.hidden = true;
  } else {
    emptyTitle.textContent = "No students enrolled";
    emptyCopy.textContent = "Add the first student and a clear face photo to prepare recognition.";
    emptyAction.hidden = false;
  }
}

async function loadRoster() {
  const query = search.value.trim();
  count.textContent = "Loading roster…";
  try {
    const payload = await apiFetch(`/api/students?page_size=100&search=${encodeURIComponent(query)}`);
    renderRoster(payload, query);
  } catch (_) {
    tableWrap.hidden = true;
    empty.hidden = true;
    errorPanel.hidden = false;
    count.textContent = "Roster unavailable";
  }
}

async function deleteStudent() {
  if (!selectedStudent) return;
  confirmDelete.disabled = true;
  cancelDelete.disabled = true;
  deleteError.hidden = true;
  try {
    await apiFetch(`/api/students/${selectedStudent.id}`, { method: "DELETE" });
    dialog.close("deleted");
    selectedStudent = null;
    await loadRoster();
  } catch (error) {
    deleteError.textContent = error.message || "The student could not be deleted. Try again.";
    deleteError.hidden = false;
    confirmDelete.disabled = false;
    cancelDelete.disabled = false;
  }
}

function trapDialogFocus(event) {
  if (event.key !== "Tab" || !dialog.open) return;
  const controls = [...dialog.querySelectorAll("button:not(:disabled), a[href], input:not(:disabled)")];
  if (!controls.length) return;
  const first = controls[0];
  const last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

search.addEventListener("input", debounce(loadRoster));
reloadButton.addEventListener("click", loadRoster);
confirmDelete.addEventListener("click", deleteStudent);
dialog.addEventListener("keydown", trapDialogFocus);
dialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  dialog.close("cancel");
});
dialog.addEventListener("close", () => {
  cancelDelete.disabled = false;
  confirmDelete.disabled = false;
  if (restoreFocus?.isConnected) restoreFocus.focus();
  restoreFocus = null;
});

loadRoster();
