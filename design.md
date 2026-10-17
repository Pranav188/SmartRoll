# SmartRoll interface design specification

Status: canonical design direction for the FastAPI milestone  
Audience: product designers, Google Stitch, frontend implementers, and reviewers  
Last updated: 8 September 2026

## 1. Product and design objective

SmartRoll is a classroom recognition workspace for teachers. Its interface helps a teacher choose a classroom photo, wait for processing, and review recognition suggestions. It does not decide attendance and it must never present an unmatched face as proof of absence.

The primary screen has one job: move a teacher from a class photo to understandable, reviewable suggestions with as little uncertainty as possible.

The design direction is **Camera Proof Sheet**. It borrows from camera contact sheets, crop marks, and scanning equipment without becoming technical or theatrical. The experience should feel calm, precise, private, and quick to operate in a classroom.

## 2. Scope

This specification covers:

- Take attendance
- Student roster
- Student enrollment
- Image selection and validation
- Queued recognition and enrollment jobs
- Recognition result review
- Recoverable errors and expired results
- Responsive navigation and layouts

This milestone does not include:

- Login or user management
- Classes or timetable selection
- Saving or confirming attendance
- Attendance reports
- Production administration
- Model configuration
- A dark theme

Do not design controls for excluded features. In particular, do not add a "Save attendance" button.

## 3. Design principles

### Recognition is a suggestion

Use "Recognized", "Needs review", and "Not recognized". Never label a student "Absent" based on recognition output. Confidence-like values must not be presented as calibrated probabilities.

### Show system state plainly

The user should always be able to answer three questions: what is happening, whether they need to act, and how to recover. Every asynchronous state needs a text label, icon, color treatment, and specific guidance.

### Spend expression in one place

The optical proof frame is the signature element. Its four crop marks connect the interface to classroom image review. A single scan line may move while processing. Other surfaces should remain restrained.

### Make privacy visible but quiet

Place short privacy guidance near the image workflow. Do not use alarmist language or lengthy legal copy. Never use real student images in mockups, generated designs, screenshots, or automated tests.

### Design for a teacher in motion

Primary actions must be obvious, controls must remain usable by touch, and recovery must not depend on technical knowledge. Avoid dense dashboards, hidden hover actions, and unnecessary navigation levels.

## 4. Visual system

### Color

| Token | Value | Use |
| --- | --- | --- |
| Scan White | `#F6F8FA` | Page background |
| Paper | `#FFFFFF` | Working surfaces and controls |
| Graphite | `#1D2933` | Primary text and strong outlines |
| Graphite Soft | `#52616D` | Supporting text |
| Line | `#CCD5DB` | Dividers and quiet borders |
| Scanner Cyan | `#087A8C` | Primary actions, active navigation, focus, processing |
| Cyan Dark | `#075D6A` | High-contrast cyan text and hover states |
| Cyan Pale | `#E8F4F5` | Informational state backgrounds |
| Verified Green | `#18794E` | Successful recognition and ready enrollment |
| Green Pale | `#EAF5EF` | Success backgrounds |
| Review Gold | `#A86908` | Ambiguity and review-required states |
| Gold Text | `#714600` | Accessible warning text |
| Gold Pale | `#FFF5DC` | Review backgrounds |
| Error Red | `#B42318` | Destructive actions and failures |
| Red Pale | `#FDF0EF` | Failure backgrounds |

Use color to reinforce meaning, never as the only signal. Avoid decorative gradients. Shadows should be rare and shallow. Use `0 14px 44px rgb(29 41 51 / 8%)` only where elevation communicates a real layer, such as a dialog.

### Typography

- **IBM Plex Sans Condensed Semibold**: page titles, section headings, and ordered step labels
- **IBM Plex Sans Regular and Semibold**: navigation, body copy, controls, forms, and lists
- **IBM Plex Mono Regular**: job IDs, timestamps, file metadata, and technical state details only

Bundle all font files locally. Do not use Google Fonts at runtime.

Recommended scale:

| Role | Size | Line height | Notes |
| --- | --- | --- | --- |
| Page title | `clamp(2.5rem, 6vw, 4.6rem)` | `0.98` | Tight, characterful, maximum two lines |
| Section title | `1.6rem` | `1.15` | Condensed semibold |
| Card or group title | `1rem` | `1.35` | Sans semibold |
| Lead | `1.08rem` | `1.5` | Maximum line length around 640px |
| Body | `1rem` | `1.5` | Default reading text |
| Utility | `0.72rem` | `1.4` | Mono, uppercase only for genuine metadata |

Sentence case is the default. Do not use all caps for navigation or buttons.

### Shape, border, and spacing

- Default radius: `10px`
- Buttons and inputs: restrained `6px` to `10px` radius
- Do not use fully rounded pills except for compact status indicators where the shape aids scanning
- Minimum control size: `44px` by `44px`
- Main content width: `1180px`
- Standard page side padding: `20px` on mobile and `20px` minimum on larger screens
- Use an 8px spacing rhythm, with 4px adjustments only for optical alignment
- Prefer borders and spacing over nested cards

## 5. Signature element: the proof frame

The proof frame contains the selected or processed classroom image. It has four optical crop marks placed just inside its corners. The marks should be visible without competing with the photograph.

In the idle state, the frame contains a camera glyph, brief guidance, and "Choose class photo". After selection, the image fills the frame using contain behavior so no face is silently cropped. During processing, one cyan scan line travels vertically through the frame. This is the only expressive animation in the product.

The scan line must:

- Appear only while processing
- Avoid flashing or rapid repetition
- Stop as soon as processing ends
- Become static or disappear when `prefers-reduced-motion: reduce` is active
- Never imply that recognition is guaranteed or complete before the job succeeds

Do not add animated particles, pulsing borders, facial wireframes, radar effects, or decorative camera overlays.

## 6. Shared application shell

Desktop navigation contains:

- SmartRoll brand and aperture mark
- Take attendance
- Roster
- Enroll

The active page uses text contrast and a cyan bottom rule. The footer states: "Recognition results are suggestions. Review them before recording attendance."

Below 768px, replace the horizontal navigation with a labelled "Menu" button. The menu must expose its expanded state programmatically and close after navigation. Include a visible skip link as the first focusable control.

## 7. Screen specifications

### 7.1 Take attendance

Desktop layout above 1024px:

```text
┌────────────────────────────────────────────────────────────┐
│ SmartRoll           Take attendance   Roster   Enroll      │
├────────────────────────────────────────────────────────────┤
│ Take attendance                         Privacy guidance    │
│ Upload ───────── Process ───────── Review                   │
├───────────────────────────────┬────────────────────────────┤
│ Class photo                   │ Current scan               │
│ ┌───────────────────────────┐ │ Status and guidance        │
│ │   optical proof frame     │ │ Job metadata               │
│ │   selected/result image   │ │                            │
│ └───────────────────────────┘ │ Recognized                 │
│ Start recognition             │ Needs review               │
│ Replace  Remove               │ Not recognized             │
└───────────────────────────────┴────────────────────────────┘
```

Required content and behavior:

- Page title: "Take attendance"
- Lead: "Choose one clear classroom photo, let SmartRoll scan it, then review every suggestion."
- Privacy note beside the title on desktop
- Ordered progress rail: Upload, Process, Review
- Proof frame and accepted file guidance
- Selected-file preview with Replace and Remove actions
- One primary action: "Start recognition"
- Current scan panel with live state and job metadata
- Result groups: Recognized, Needs review, Not recognized
- Completion copy: "Recognition finished. Review the suggestions."

The progress rail is a real sequence, so numbering is appropriate. Current and completed steps must be distinguishable without relying on color alone.

### 7.2 Roster

The roster prioritizes scanning and action over decoration. Use a compact table on larger screens and readable stacked rows on small screens.

Each row includes:

- Student name
- Enrollment status: Encoding, Ready, or Failed
- Date added
- Contextual delete action

The page includes a student search field and "Enroll a student" action. Its empty state says what the roster is for and provides the same enrollment action.

Deletion uses a native or equivalent modal dialog. The dialog must:

- Name the student being deleted
- Explain that the student and enrollment photos will be removed
- Focus Cancel initially
- Trap focus while open
- Close on Escape
- Restore focus to the originating delete button
- Keep the destructive action visually distinct but not dominant
- Show a recoverable inline error if deletion fails

### 7.3 Enroll a student

Enrollment is a two-step form followed by job status:

1. Student identity
2. Face samples

Required content and behavior:

- Full name field with plain guidance
- Local photo requirements before selection
- "Choose enrollment photos" file control
- One to ten JPEG or PNG files, up to 10 MiB each
- Selected-file list with per-file validation state
- Primary action: "Enroll student"
- Cancel action back to the roster
- Encoding job ID and progress after submission
- "Retry encoding" only when the existing job is eligible for retry

Requirements copy:

- "One visible face in each photo"
- "Even lighting and a natural angle"
- "JPEG or PNG, up to 10 MiB each"

Do not expose model names, embeddings, storage keys, or queue terminology in the normal enrollment flow.

## 8. State model

The interface supports these user-visible states:

| State | Meaning | Required presentation |
| --- | --- | --- |
| `idle` | No file selected | Neutral icon, guidance, file action |
| `selected` | A valid local file is selected | Preview, filename, Replace, Remove, enabled primary action |
| `validating` | Local or server validation is running | Informational icon and concise validation copy |
| `queued` | The job is committed and awaiting a worker | Cyan status, job ID, waiting guidance |
| `processing` | A worker is processing the image | Cyan status, scan line, `aria-busy="true"` |
| `succeeded` | Processing completed without unresolved matches | Green status and reviewable results |
| `needs_review` | Processing completed with ambiguity or unknown faces | Gold status and explicit review group |
| `invalid` | The supplied image cannot be processed | Red status plus a specific file recovery action |
| `failed` | Processing stopped unexpectedly | Red status and retry when eligible |
| `expired` | Temporary job output has been removed | Red or neutral-expired treatment and instruction to start a new scan |

Job polling updates an `aria-live="polite"` region and must never move keyboard focus. Do not announce every poll. Announce meaningful transitions only.

Required recovery copy:

- No detected face: "No face was found. Choose a clearer photo."
- Processing failure: "Processing stopped. Retry this scan."
- Completion: "Recognition finished. Review the suggestions."
- Network interruption: explain that status could not be checked and provide "Try again"
- Expired result: explain that the temporary result is no longer available and provide a route to start a new scan

## 9. Interaction rules

- File selection never uploads automatically. Upload begins only after the user activates the primary action.
- Replace opens the file picker while retaining the current preview until a replacement passes local validation.
- Remove clears the selected file, preview, validation message, and any unsubmitted local state.
- Disable the primary action while invalid, queued, or processing.
- Retry must reuse the existing retry endpoint and appear only for eligible failed or dispatch-failed jobs.
- Preserve typed names and valid selected-file feedback when a recoverable submission error occurs.
- Never steal focus when polling completes or results appear.
- Use browser-native behavior where it improves reliability, including file inputs and dialogs.

## 10. Responsive behavior

### Above 1024px

- Use the two-panel attendance workspace
- Keep privacy guidance beside the page introduction
- Display roster data as a compact table

### 768px to 1024px

- Move current scan and results beneath the proof frame
- Keep the progress rail horizontal if labels remain readable
- Allow the privacy note to move beneath the introduction

### Below 768px

- Use one logical column
- Replace horizontal navigation with the labelled menu
- Use this attendance order: title, privacy guidance, file selection, primary action, job state, results, supporting actions
- Convert roster rows into a layout that does not require horizontal scrolling
- Keep dialog actions large enough for touch

### 380px and below

- Reduce page gutters, not control size
- Allow long filenames and job IDs to wrap safely
- Stack paired dialog actions
- Verify at both 375px and 320px widths

The interface must remain usable at 200 percent browser zoom without clipped controls, lost content, or two-dimensional scrolling.

## 11. Accessibility requirements

- Meet WCAG AA contrast: 4.5:1 for normal text and 3:1 for large text, controls, focus indicators, and meaningful graphics
- Maintain visible `:focus-visible` styling on every interactive element
- Provide text labels for icon-only controls or avoid icon-only controls entirely
- Use semantic headings in a logical order
- Associate form guidance and errors with their fields using `aria-describedby`
- Mark invalid fields with `aria-invalid="true"`
- Use `aria-busy` on the active processing region
- Use polite live regions for meaningful asynchronous state changes
- Make all workflows keyboard operable
- Respect reduced motion
- Give images useful alternative text that describes their interface role, not inferred identities
- Never encode status using color alone

## 12. Content vocabulary

Use these terms consistently:

- Take attendance
- Choose class photo
- Start recognition
- Current scan
- Recognized
- Needs review
- Not recognized
- Roster
- Enroll a student
- Enrollment photos
- Encoding
- Ready
- Failed

Avoid:

- Absent, when derived from recognition
- AI-powered, smart, seamless, magical, or similar promotional filler
- Submit, when a more specific action is available
- Confidence percentage, unless the value is demonstrably calibrated and the product requirement changes
- Backend terms such as Celery, Redis, embeddings, or storage key in teacher-facing copy

## 13. Google Stitch brief and constraints

When using Google Stitch, generate the Take attendance desktop and mobile views first. Approve the visual direction before extending it to Roster and Enroll. This prevents three screens from drifting into unrelated component systems.

Stitch may explore:

- Exact spacing within the defined rhythm
- Crop-mark proportion and line weight
- Information density inside result groups
- Responsive composition within the specified reading order
- Quiet iconography for states

Stitch must preserve:

- The Camera Proof Sheet direction
- The palette and type roles
- The proof frame as the only signature treatment
- The exact workflow vocabulary
- All required states and recovery actions
- Recognition as suggestion, not attendance truth
- Accessibility and responsive requirements
- The absence of saved attendance controls

Reject outputs that introduce generic analytics cards, gradients, dark glass panels, decorative charts, floating sidebars, excessive pills, biometric wireframes, or real student photographs.

## 14. Implementation boundary

The frontend is server-rendered with Jinja2, semantic HTML, ordinary CSS custom properties, and small vanilla JavaScript modules. Do not introduce React, Tailwind, a runtime font service, a build framework, or a component abstraction layer for this milestone.

Relevant implementation files:

- `fastapi_app/app/templates/base.html`
- `fastapi_app/app/templates/attendance.html`
- `fastapi_app/app/templates/students.html`
- `fastapi_app/app/templates/add_student.html`
- `fastapi_app/app/static/css/smartroll.css`
- `fastapi_app/app/static/js/attendance.js`
- `fastapi_app/app/static/js/students.js`
- `fastapi_app/app/static/js/add-student.js`

Visual changes must not silently alter API routes, job states, retry eligibility, polling behavior, file constraints, or recognition semantics. If a generated design requires a contract change, document and review that change before implementation.

## 15. Design acceptance checklist

A design is ready to implement only when all of the following are true:

- Take attendance, Roster, and Enroll share one visual system
- Idle, selected, queued, processing, succeeded, needs-review, invalid, failed, and expired states are represented
- The proof frame remains the single expressive element
- There is no horizontal overflow at 1440, 1024, 768, 375, or 320 CSS pixels
- Controls remain readable and operable at 200 percent zoom
- Focus order follows the visual reading order
- Every status uses text, icon, and color
- All error states explain a recovery action
- Delete-dialog keyboard behavior is specified
- Reduced motion removes the scan animation
- Normal text and controls meet WCAG AA contrast
- Mockups and screenshots use synthetic identities and non-biometric fixtures
- No excluded feature has been added

After implementation, verify each major state with keyboard testing, automated accessibility checks, and screenshots at all five target widths. The design is not accepted from a single desktop screenshot.
