# SmartRoll: FastAPI migration and feature plan

Status: partially implemented. An isolated FastAPI app now exists in `fastapi_app/` with student enrollment, recognition jobs, and a browser UI adapted from the original Django design. Authentication and persistent attendance remain planned. The phases and dates below are the original planning baseline, not a current completion report.

Prepared on 5 September 2026 from the current repository and our discussion. This is a learning-led migration: the user writes the core implementation, with guided explanations, code review, and debugging support. Completion is based on demonstrated behavior and understanding, rather than a fixed deadline.

Time budget: 3–4 hours per week; this is a lower-priority project. Section 10 sets a provisional 9–12 month timeline for the essential release, with useful intermediate milestones and optional features kept outside that commitment.

## 1. Goal and scope

Build a FastAPI attendance application where a teacher selects a class, opens an attendance session, uploads a classroom photograph, reviews recognition suggestions, confirms attendance, and retrieves the saved record later.

The first release serves one institution. An administrator maintains student identities and teacher assignments; teachers manage attendance for their assigned classes. Recognition assists a human decision. It does not establish physical presence or prevent photo spoofing.

The engineering goals are request validation, relational modeling, transaction boundaries, authorization, reliable background work, testing, and deployment. We will learn these through complete features instead of translating every Django function directly.

### Current behavior and gaps

| Area | Current evidence | Planned change |
| --- | --- | --- |
| Student identity | Only a unique name and creation time in `core/models.py` | Stable student number, editable non-unique name, archive state |
| Class scope | `attendance_view` compares against every registered student | Classes, teacher assignments, class membership, session roster snapshots |
| Attendance | Results exist in a rendered response | Persist sessions, suggestions, confirmed records, and corrections |
| Processing errors | Missing encodings or unreadable images return everyone as absent | Explicit failed processing state; no automatic attendance conclusion |
| Enrollment | Add/delete queues a full-dataset rebuild and discards the task ID | Per-student encoding updates, persistent jobs, visible results and failures |
| Recognition storage | Names and embeddings share one directly overwritten pickle | Embeddings linked to stable student/sample IDs with transactional updates |
| Access | Application views contain no authorization checks | Login, administrator/teacher roles, resource ownership checks |
| Tests and measurement | Empty Django test file; queue submission mocked in latency benchmark; stress test uses enrollment inputs and different matching logic | Behavior tests, real worker integration tests, separate recognition evaluation data |

These are source observations, not results from running the stack. Existing performance and deployment claims require new verification.

## 2. Architecture decisions

| Component | Initial choice | Purpose and boundary |
| --- | --- | --- |
| HTTP application | FastAPI with Pydantic schemas | Validate input, enforce access, expose API contracts, return results |
| Database | PostgreSQL with synchronous SQLAlchemy 2.x | Persist application state with explicit transactions and constraints |
| Schema changes | Alembic | Reviewable, repeatable database migrations |
| Background work | Celery with Redis | Run enrollment and classroom recognition outside HTTP requests |
| Image processing | Existing OpenCV/face_recognition pipeline, extracted into plain Python | Establish a baseline before changing recognition algorithms |
| Embeddings | PostgreSQL rows linked to enrollment samples, using numeric arrays and model metadata | Avoid a shared mutable pickle; begin with class-scoped in-memory comparison |
| Image storage | Private local volume shared by API and worker on one host | Store files under generated keys; authorize every download |
| Browser UI | Adapt the existing pages into same-origin templates with small amounts of JavaScript | Support uploads, job polling, review, and history without a separate frontend project |
| Login | Expiring, revocable server-side sessions in secure cookies | Use maintained password-hashing tools; protect cookie-authenticated writes against CSRF |
| Verification | pytest, API tests, and real PostgreSQL/Redis/Celery integration tests | Test contracts and failures at the appropriate boundary |

Start with synchronous database access so session lifetime, commits, and rollbacks are explicit. Use ordinary synchronous route functions where they call blocking dependencies. A worker creates its own database session; it never receives the web request's session or ORM objects. Later, asynchronous database access can be a measured learning exercise.

Keep one application codebase plus worker processes. Add modules when responsibilities emerge; avoid generic repositories, plugin systems, and extra services at the start. Exact dependency pins and a compatible Python runtime will be verified in phase 0, retaining Python 3.10-compatible source initially as required by the repository guidance.

The database is authoritative for attendance and user-visible job status. Redis transports jobs. Files contain images, not the only copy of business state. Queue messages carry job IDs; workers resolve authorized storage references through the database.

## 3. Migration boundaries and data protection

- Work on a future `codex/fastapi-migration` branch, with the replacement under `fastapi_app/`. Creating the branch and scaffold belongs to implementation, not this planning step.
- Keep the existing Django code, dependencies, database, media, and Compose setup available as a reference. Give FastAPI its own environment, dependency manifest, database, Redis namespace/queues, storage root, and Compose project/volumes.
- Use fabricated student records and consented local evaluation images during development. Do not commit real photos, embeddings, credentials, database dumps, or temporary benchmark outputs.
- Import into the new database through a dedicated, repeatable migration tool. Do not point Alembic at the Django database or make both applications write the same records.
- Verify the actual source database before import. The presence of local SQLite files does not establish which database is authoritative.
- Preserve existing student primary keys when importing into an empty target, and record an explicit legacy-to-target mapping. The old schema has no student number: use visibly provisional legacy identifiers until real identifiers are supplied, rather than inventing institutional numbers.
- Resolve legacy name-based photo directories through a reviewed mapping. Report missing, ambiguous, orphaned, and invalid files. Recompute embeddings from approved source photos instead of making the old pickle the new data source.
- Import only information that exists. The current schema contains no attendance history, class membership, or teacher ownership to recover. New assignments must be created explicitly; credentials must not silently inherit Django password hashes into an incompatible verifier.

## 4. Essential first-release features

These are the release boundary. Additional features come after this workflow works end to end.

| Feature | Required behavior |
| --- | --- |
| Student directory | Create, search, paginate, edit, and archive students; allow identical names; prevent duplicate student numbers |
| Teacher access | Administrator-provisioned accounts, login/logout, session expiry, administrator reset procedure, class-level access enforcement |
| Class rosters | Assign teachers and students; prevent duplicate membership; archive classes without losing history |
| Attendance sessions | Date/time, class, owner, roster snapshot, draft/confirmed state, saved records |
| Enrollment | Validate uploads; require exactly one usable face per enrollment image; show per-image rejection reasons and enrollment readiness |
| Recognition jobs | Job ID, pending/running/succeeded/failed visibility, actionable errors, controlled retry, and recovery for stale jobs |
| Teacher review | Annotated image, match suggestions, unknown/ambiguous faces, explicit manual present/absent decisions, confirmation |
| Corrections | Preserve original confirmation and append who changed which record, when, and why |
| History and export | Retrieve confirmed sessions and export class/date-filtered CSV |
| Image lifecycle | Private downloads, upload limits, cleanup of temporary/failed uploads, explicit biometric deletion and retention rules |
| Delivery evidence | CI, clean setup instructions, reproducible migrations, real job tests, honest recognition/latency measurements |

### Core data model and invariants

Introduce tables only when their phase requires them.

| Entity | Responsibility and key rule |
| --- | --- |
| User / LoginSession | Teacher or administrator identity; revocable login sessions; no public role escalation |
| Student | Stable internal ID and unique student number; name is not an identity or filesystem path |
| Class / TeacherAssignment / ClassMembership | Explicit ownership and roster; each membership/assignment pair is unique |
| EnrollmentSample | Student, private image key, validation outcome, embedding, encoding version, timestamps |
| AttendanceSession | Class/time, creator, draft/confirmed state, revision, processing-run reference |
| AttendanceRecord | One row per session/student, initialized from the roster snapshot; initially unmarked |
| ProcessingJob | Operation, resource owner, attempt, input revision, state, timestamps, errors, result reference |
| RecognitionRun / FaceSuggestion | Image and encoding version, matching threshold/rule, face box, proposed student or unknown/ambiguous result, distance |
| AttendanceChange | Append-only correction with actor, before/after values, reason, and time |

Snapshot session membership when the session opens so later roster edits do not rewrite history. Enforce uniqueness of session/student pairs in PostgreSQL. An archived student remains referenced by historical records, while removal of their biometric material is a separate operation.

Do not equate a matching distance with a calibrated probability. Keep processing state, recognition suggestions, and attendance decisions separate. A face that was not detected is not proof of absence. Confirmation requires the teacher to resolve every unmarked student, either individually or through an explicit reviewed bulk action. Concurrent edits must use revision checks or equivalent transaction controls so changes are not silently overwritten.

## 5. Implementation phases

### Phase 0: Establish the baseline and isolated workspace

Tasks: map the existing flows and known behavior differences; verify the Mac runtime and container dependencies; create the migration branch and isolated application environment; define test database/storage settings and tiny controlled fixtures. Record the existing matcher behavior, including ties and missing inputs, before changing it. Add FastAPI application startup and a basic health endpoint.

Completion check: the new API starts independently, reports health, and an automated smoke test passes without opening the existing dataset or modifying the Django database. Record commands, purpose, and expected output in setup notes when the environment is selected.

Learning checkpoint: explain the boundary between the ASGI server, FastAPI application, router, and request/response schema.

### Phase 1: Student API and database foundation

Tasks: add SQLAlchemy session management, separate create/update/read schemas, the student table, first Alembic revision, CRUD, search/pagination, and consistent validation/conflict responses. Use synthetic records in this local-only phase. Add PostgreSQL-backed tests and a minimal CI job immediately.

Completion check: a fresh database can be created from migrations; data survives restart; failed writes roll back; simultaneous requests for the same student number create exactly one student; response schemas expose only intended fields. Preserve migration scripts instead of relying on automatic table creation at startup.

Learning checkpoint: explain Pydantic versus ORM models, flush versus commit, the request session's lifetime, and why validation cannot replace a database uniqueness constraint.

### Phase 2: Identity, permissions, and class rosters

Tasks: add administrator/teacher accounts, maintained password hashing, session login/logout/expiry, CSRF protection, and an administrator account bootstrap/reset procedure. Add classes, teacher assignments, and student membership. Apply access checks to the API itself, including student detail visibility; ordinary teachers see only students in their assigned classes. Student creation and institution-wide editing remain administrator operations initially.

Completion check: an anonymous caller cannot access protected data; a teacher cannot read or edit another teacher's class by changing an ID; users cannot grant themselves privileges; membership duplicates are rejected. Every subsequent image/job/export endpoint inherits these resource checks.

Learning checkpoint: explain authentication versus authorization, and why a hidden browser button does not enforce either.

### Phase 3: Saved attendance without recognition

Tasks: implement session creation, roster snapshots, manual marking, atomic confirmation, revision checking, corrections with an audit trail, history, and CSV export. This creates a useful workflow before adding uncertain machine output.

Completion check: a teacher can create, confirm, reopen, and correct a session; reopening does not lose data; later roster edits do not alter the old session; repeated confirmation does not duplicate records; conflicting edits fail visibly; exported confirmed records match the database. Escape spreadsheet formula-like values in CSV exports.

Learning checkpoint: explain the transaction boundary for confirmation and why recognition should produce suggestions independently of final attendance.

### Phase 4: Private enrollment and reliable jobs

Tasks: validate file size, decoded dimensions, type, and usable face count; store uploads under generated keys; extract encoding into framework-independent functions. Set up the new Celery worker explicitly and add persistent jobs. Compute embeddings for affected samples only. Publish a completed enrollment update transactionally, retaining the previous usable version until replacement succeeds. Rejected images get visible reasons.

Reliability requirements: commit a job before dispatch; expose dispatch failures and provide an authorized retry; retry only transient failures with bounded attempts. Duplicate deliveries must converge on one result. Detect jobs stranded between database commit and dispatch, and jobs abandoned by a dead worker. Start with a documented reconciliation operation and stale-job retry; use attempt/revision checks to prevent a late worker from publishing obsolete results. Do not promise exactly-once execution.

Completion check: a real API request submits to Redis and the worker completes it; invalid enrollment never reports ready; duplicate delivery cannot create duplicate samples; Redis being unavailable yields a visible recoverable state; a worker restart can be recovered; deleting a student's biometric data while work runs prevents that job from restoring it. Database rows and files are reconciled after partial failure.

Learning checkpoint: explain the database-to-broker failure window, idempotency, retry versus replay, and why a successful HTTP response is not a completed encoding job.

### Phase 5: Classroom recognition and review UI

Tasks: queue classroom recognition, restrict candidates to the session roster and available approved enrollments, persist versioned suggestions, and show annotated results. Adapt the existing UI for login, rosters, uploads, job polling, manual review, confirmation, and history. Keep invalid images, unavailable encodings, zero detected faces, unknown faces, ambiguous matches, and processing exceptions distinguishable.

Use one matching implementation for application and evaluation. Retain the old majority-vote behavior as a measured baseline, then test a per-student distance rule with threshold and ambiguity margin before selecting the initial release rule. Avoid sample-count voting advantages. Multiple face boxes suggesting the same student must be flagged for review, not counted as multiple attendances. Record the rule and encoding version used by each run.

Completion check: upload, process, review, confirm, and retrieve works through the browser; recognition failures leave attendance unmarked; reprocessing creates a new run and cannot overwrite a confirmed session or manual corrections; inaccessible classes/images/jobs remain inaccessible through direct URLs.

Learning checkpoint: explain what a distance threshold can establish, what it cannot establish, and why teacher confirmation remains necessary.

### Phase 6: Migration rehearsal and release verification

Tasks: build the import tool with validation-only and apply modes; rehearse against a copy of the actual source; reconcile students, file inventories, mappings, and enrollment failures; make repeated imports safe. Add production configuration, secure image serving, service health/readiness, structured request/job logs, retention cleanup, database/media backups, and a tested restore procedure. Correct the Redis configuration mismatch in the new stack. Keep secret values and biometric content out of logs and images.

Measurement: use real HTTP requests, PostgreSQL, Redis, and Celery; record dataset size, image resolution, hardware, concurrency, warmups, failures, request acknowledgment, queue wait, worker runtime, and end-to-end completion. Use enough samples for any claimed percentile and retain raw results. Evaluate recognition on separate enrollment, threshold-tuning, and held-out classroom photos, including unknown people and different lighting/pose. Record false identifications, missed identifications, unknown rejection, and teacher correction rate, with clear denominators and sample counts.

Completion check: CI passes; the complete UI flow works in a clean deployment; an import rehearsal reconciles without unexplained omissions; a repeat import adds no duplicates; backup restore and worker failure recovery are demonstrated. Choose and document performance/recognition acceptance thresholds after measuring the baseline, then freeze them before the final evaluation. Publish measured results and limitations in the README.

Learning checkpoint: explain what the measurements support, the recovery limits, and which failures the tests actually exercised.

### Phase 7: Switch over and close the migration

Tasks: if the old app is in active use, schedule a short write freeze, back up its database and files, run the final import, reconcile counts/mappings, and verify the new app before changing traffic. If it is only a local project, perform the same rehearsal locally without inventing a production cutover. Retain the Django version and backups through verification.

Rollback boundary: before new writes are allowed, traffic can return to Django and the target can be rebuilt from backup. After FastAPI accepts new attendance data, Django cannot represent that data. A rollback then requires preserving/exporting all new records and an explicit recovery decision; simply pointing traffic back would lose functionality and hide records.

Completion check: the new system owns all intended workflows, the migration report has no unresolved data errors, setup and recovery instructions are accurate, and the user can explain the architecture and demonstrate it. Removal of the legacy implementation is a separate cleanup decision after this gate.

## 6. Initial API contracts

These are proposed interfaces, not implemented routes. Add each with its owning phase. All resource operations become access-controlled in phase 2; the unauthenticated phase-1 prototype stays local with synthetic data.

| Interface | Purpose | Expected result |
| --- | --- | --- |
| Student create/list/detail/update/archive | Manage stable student identities | Created or updated representation; validation errors; conflict for duplicate number |
| Login/logout/current user | Establish and revoke a browser session | Secure session cookie, expiry, safe user profile; invalid credentials rejected |
| Class and membership operations | Manage teaching assignments and rosters | Authorized class/roster representations; duplicate membership rejected |
| Session create/detail | Open and retrieve attendance | Draft session with frozen roster and unmarked records |
| Enrollment or recognition submission | Accept a validated upload and request processing | HTTP 202 with persistent job ID and status location; visible failure if dispatch cannot be confirmed |
| Job status/retry | Show progress and recover eligible failures | Authorized state/error/result; repeated retry cannot publish duplicate results |
| Session review/confirm/correct | Persist human decisions with revision checking | Saved draft or confirmed records; conflict if based on stale revision; correction audit entry |
| Session history/export | Retrieve past confirmed attendance | Paginated history or protected CSV matching selected records |

## 7. Additional features, ranked after the first release

Choose one extension based on the skill to deepen. These are not prerequisites for migration completion.

| Order | Feature | Why add it | Completion evidence |
| --- | --- | --- | --- |
| 1 | Bulk roster import with preview and row-level errors | Useful administration and deeper validation/transaction practice | Bad rows are explained; preview changes no data; rerunning cannot duplicate membership |
| 2 | Attendance summaries and student history | Useful SQL aggregation and reporting | Percentages use confirmed sessions where the student was on the snapshot roster; unknown/unconfirmed work is excluded and explained |
| 3 | Enrollment quality feedback | Improve recognition inputs | Specific face-count, lighting, or blur feedback; measured reduction in rejected/missed matches on separate evaluation data |
| 4 | SSE job updates | Learn asynchronous streaming when polling already works | Updates reconnect safely, enforce access, and avoid leaking other users' jobs; polling remains a fallback |
| 5 | Automatic dispatch reconciliation or a transactional outbox | Deepen delivery reliability beyond manual recovery | Database-to-broker outage/crash tests eventually deliver committed work without duplicate results |
| 6 | Object storage | Support API/worker deployment across hosts when needed | Private access, retention, failed-upload cleanup, and restore behavior remain correct |
| 7 | Controlled async database experiment | Learn event-loop behavior and connection-pool limits | Compare the same endpoints/workload before and after; report throughput, tail latency, and complexity even if there is no improvement |
| 8 | Better matcher/model or similarity index | Improve a demonstrated recognition or lookup bottleneck | Same held-out evaluation, versioned embeddings, measured benefit, documented memory/latency cost |

Defer multi-institution tenancy, mobile apps, webcam streaming, liveness detection, Kubernetes, and unrelated AI chat features. Each substantially changes the scope. A classroom photograph alone must not be presented as spoof-resistant attendance verification.

## 8. Working method and first milestone

For each small feature: explain the concept, specify behavior and failure cases, let the user implement, review the diff, test it, and ask the user to explain the underlying decision. Any supplied command will include its purpose and expected result. Add tests alongside features; do not postpone them to the release phase.

The first working milestone is phase 0 plus phase 1: an isolated FastAPI student API backed by PostgreSQL, with an Alembic migration and meaningful validation/transaction tests. The first lesson is the student identity contract and the difference between request validation and database constraints. No images, Celery migration, or large scaffold are needed to complete that lesson.

## 9. Reference documentation

- Explicit session and transaction ownership follows the [SQLAlchemy session guide](https://docs.sqlalchemy.org/en/20/orm/session_basics.html).
- Reviewed schema revisions follow the [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
- Retaining a worker for substantial computation follows [FastAPI background-task guidance](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat).
- Retry and duplicate-delivery design should be checked against the selected version's [Celery task documentation](https://docs.celeryq.dev/en/stable/userguide/tasks.html). Application idempotency must be implemented and tested; selecting an acknowledgment option does not establish it.

These references support implementation choices. The feature order and learning milestones are recommendations specific to SmartRoll, not framework requirements.

## 10. Realistic timeline at 3–4 hours per week

### Planning assumptions

Allow approximately 9–12 months for the complete essential release. This is an engineering estimate, not a delivery promise. It includes learning, implementation, debugging, tests, and documentation. It assumes the user writes the code with guidance, the existing recognition dependencies can be reused, the frontend stays small, and there is no new model training or additional feature scope.

The working estimate is 126 hours: 36 active weeks at an average of 3.5 hours. Reserve another six calendar weeks for missed weeks or overruns, giving a baseline of 42 calendar weeks, approximately ten months. At three hours per active week, the same work plus the reserve takes about 48 weeks; at four hours, about 38 weeks. These calculations explain the range; they do not make the effort estimate exact. Missed time and technical overruns share the reserve and must not both be counted as independently covered.

Dates below illustrate a start in the week of 7 September 2026. They do not create a schedule or reminder. Shift them if the actual start changes. Reserve weeks are movable, not mandatory breaks.

### Baseline schedule

| Calendar weeks | Phase and deliverable | Active weeks / estimated hours | Illustrative finish |
| --- | --- | --- | --- |
| 1 | Phase 0: isolated API environment, health check, student identity contract | 1 / 3.5 | 13 September 2026 |
| 2–5 | Phase 1: PostgreSQL student API, Alembic migration, validation and transaction tests, minimal CI | 4 / 14 | 11 October 2026 |
| 6 | Reserve for interruptions or foundation problems | No new deliverable | 18 October 2026 |
| 7–11 | Phase 2: teacher login, resource permissions, classes, and rosters | 5 / 17.5 | 22 November 2026 |
| 12 | Reserve | No new deliverable | 29 November 2026 |
| 13–17 | Phase 3: saved manual attendance, confirmation, corrections, history, and export | 5 / 17.5 | 3 January 2027 |
| 18 | Reserve | No new deliverable | 10 January 2027 |
| 19–25 | Phase 4: private enrollment, per-student embeddings, persistent jobs, failure recovery | 7 / 24.5 | 28 February 2027 |
| 26 | Reserve | No new deliverable | 7 March 2027 |
| 27–32 | Phase 5: queued classroom recognition and browser review flow | 6 / 21 | 18 April 2027 |
| 33 | Reserve | No new deliverable | 25 April 2027 |
| 34–40 | Phase 6: import rehearsal, deployment, backup/restore, real measurements, final documentation | 7 / 24.5 | 13 June 2027 |
| 41 | Phase 7: verified switch and migration closure | 1 / 3.5 | 20 June 2027 |
| 42 | Final reserve | No new deliverable | 27 June 2027 |

Job reliability and release verification have larger allocations because they involve several components and failure cases. Tests remain part of each phase; phase 6 does not defer all testing until the end. Actual rollout to an actively used deployment, unavailable evaluation photos, or unexpectedly difficult native dependencies may extend the estimate.

### Useful milestones and stopping points

- Around weeks 5–6: a tested, persistent FastAPI student API. This is the first learning commitment, approximately 17.5 hours of work including setup. The unauthenticated prototype remains local with synthetic data.
- Around weeks 17–18: an authenticated manual attendance backend with saved history. This is useful through the API; the polished browser workflow arrives in phase 5. It is a sensible pause point even if recognition has to wait.
- Around weeks 32–33: the complete recognition-and-review workflow running locally. It is a demo milestone; the import and release checks are still outstanding.
- Around week 42: the essential migration and release checks completed, subject to their actual acceptance criteria. With the illustrative start, target late June 2027 and allow roughly May–August 2027 across the stated pace range.

### Weekly rhythm

Use two 90-minute sessions and a 30-minute wrap-up, totaling 3.5 hours. In the first session, spend up to 20 minutes restoring context and learning one concept, then implement one bounded behavior. Use the second session to finish it, test the relevant failures, and review the result. Use the wrap-up to record what works, the remaining blocker, and the exact next action. If only three hours are available, include those notes inside the two sessions. A fourth hour is optional debugging time, not a reason to start another feature.

Keep only one task in progress. A suitable weekly task is adding one database constraint and verifying the conflict response; building all authentication is several weeks of work. End each session with a short handoff note so the next session does not begin with rediscovering the codebase. Do not compensate for a missed week with an obligatory double session; move the dates or use the reserve.

After phase 1, compare the actual hours with the 17.5-hour setup-and-student estimate and revise the remaining schedule. Re-estimate again after the first real Celery job. If the project falls behind, preserve the phase completion checks and move the date. Keep optional features deferred rather than sacrificing permissions, data integrity, or failure handling.

### Additional features after the essential release

The optional backlog has no committed finish date. At the same weekly budget, provisional effort ranges for small extensions are:

| Extension | Additional active weeks | Boundary |
| --- | --- | --- |
| Bulk roster import | 3–4 | One CSV format, preview, row errors, duplicate handling |
| Attendance summaries | 3–4 | Class/student summaries from existing confirmed records; no custom dashboard builder |
| SSE job updates | 3–5 | Authorized updates, reconnect behavior, existing polling fallback |
| Enrollment quality feedback | 4–6 | A small set of checks plus evaluation; no new model training |

Choose at most one after release. Object storage, automatic dispatch recovery/outbox, asynchronous database work, and model/index changes should be scoped and estimated only when selected. Their purpose and complexity depend on what the first release demonstrates.

Immediate commitment: complete phase 0 and phase 1 over approximately five active weeks, with one reserve week available, then decide the next allocation using actual experience. There is no need to commit the entire year now.
