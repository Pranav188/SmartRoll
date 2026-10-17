from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models import (
    FaceSample,
    FaceSampleState,
    JobKind,
    JobState,
    ProcessingJob,
    Student,
)
from app.services.recognition import ENCODING_MODEL_VERSION
from app.services.storage import PrivateStorage, UploadValidationError, validate_image


MANIFEST_FIELDS = (
    "source_folder",
    "source_file",
    "source_sha256",
    "target_student_id",
    "target_student_name",
    "action",
    "confirmed",
)
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png"}
VALID_ACTIONS = {"map", "create", "skip"}
MAX_ENROLLMENT_BYTES = 10 * 1024 * 1024


class ImportValidationError(ValueError):
    pass


@dataclass(frozen=True)
class LegacyStudent:
    id: int
    name: str
    created_at: datetime


@dataclass(frozen=True)
class PreviewReport:
    manifest_path: Path
    photo_folder_count: int
    exact_match_count: int
    unresolved_folders: tuple[str, ...]
    students_without_photos: tuple[str, ...]


@dataclass(frozen=True)
class ApplyReport:
    students_created: int
    samples_created: int
    samples_already_present: int
    skipped_photos: int
    job_ids: tuple[str, ...]
    dispatch_failed_job_ids: tuple[str, ...]


@dataclass(frozen=True)
class _ApprovedPhoto:
    source_path: Path
    source_sha256: str
    action: str
    target_student_id: int | None
    target_student_name: str
    content: bytes
    extension: str


def normalize_name(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def load_legacy_students(dump_path: str | Path) -> list[LegacyStudent]:
    path = Path(dump_path).expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImportValidationError(f"Could not read legacy dump: {path}") from exc

    if not isinstance(payload, list):
        raise ImportValidationError("The legacy dump must contain a JSON list.")

    students: list[LegacyStudent] = []
    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    for item in payload:
        if not isinstance(item, dict) or item.get("model") != "core.student":
            continue
        fields = item.get("fields")
        if not isinstance(fields, dict):
            raise ImportValidationError("A legacy student has invalid fields.")
        try:
            student_id = int(item["pk"])
            name = str(fields["name"]).strip()
            created_at = datetime.fromisoformat(
                str(fields["created_at"]).replace("Z", "+00:00")
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ImportValidationError("A legacy student row is invalid.") from exc
        normalized_name = normalize_name(name)
        if student_id <= 0 or not normalized_name:
            raise ImportValidationError("Legacy student IDs and names must be valid.")
        if student_id in seen_ids or normalized_name in seen_names:
            raise ImportValidationError("The legacy dump contains duplicate students.")
        seen_ids.add(student_id)
        seen_names.add(normalized_name)
        students.append(LegacyStudent(student_id, name, created_at))
    if not students:
        raise ImportValidationError("The legacy dump contains no core.student rows.")
    return students


def preview_import(
    dump_path: str | Path,
    source_dir: str | Path,
    manifest_path: str | Path,
) -> PreviewReport:
    students = load_legacy_students(dump_path)
    source_root = _source_root(source_dir)
    output = Path(manifest_path).expanduser().resolve()
    _ensure_manifest_outside_source(output, source_root)
    if output.suffix.casefold() != ".csv":
        raise ImportValidationError("The import manifest must be a CSV file.")

    students_by_name = {normalize_name(student.name): student for student in students}
    rows: list[dict[str, str]] = []
    matched_ids: set[int] = set()
    unresolved: list[str] = []
    for folder, photo in _photo_folders(source_root):
        content = _read_source_image(photo)
        validated = _validate_source_image(content, photo)
        match = students_by_name.get(normalize_name(folder.name))
        if match is None:
            action = "skip"
            target_id = ""
            target_name = ""
            confirmed = "false"
            unresolved.append(folder.name)
        else:
            action = "map"
            target_id = str(match.id)
            target_name = match.name
            confirmed = "false"
            matched_ids.add(match.id)
        rows.append(
            {
                "source_folder": folder.name,
                "source_file": photo.relative_to(source_root).as_posix(),
                "source_sha256": validated.sha256,
                "target_student_id": target_id,
                "target_student_name": target_name,
                "action": action,
                "confirmed": confirmed,
            }
        )

    _write_manifest(output, rows)
    without_photos = tuple(
        student.name for student in students if student.id not in matched_ids
    )
    return PreviewReport(
        manifest_path=output,
        photo_folder_count=len(rows),
        exact_match_count=len(matched_ids),
        unresolved_folders=tuple(unresolved),
        students_without_photos=without_photos,
    )


def apply_import(
    session: Any,
    dump_path: str | Path,
    source_dir: str | Path,
    manifest_path: str | Path,
    storage_root: str | Path,
    dispatch: Callable[[str], bool | None],
) -> ApplyReport:
    students = load_legacy_students(dump_path)
    source_root = _source_root(source_dir)
    manifest = Path(manifest_path).expanduser().resolve()
    _ensure_manifest_outside_source(manifest, source_root)
    approved = _load_and_validate_manifest(manifest, source_root, students)

    from sqlalchemy import select

    existing_students = list(session.scalars(select(Student)).all())
    existing_samples = list(session.scalars(select(FaceSample)).all())
    _validate_database_state(existing_students, existing_samples, students, approved)

    students_by_id = {student.id: student for student in existing_students}
    students_by_name = {
        normalize_name(student.name): student for student in existing_students
    }
    created_students = 0
    for legacy in students:
        if legacy.id in students_by_id:
            continue
        student = Student(
            id=legacy.id,
            name=legacy.name,
            created_at=legacy.created_at,
        )
        session.add(student)
        students_by_id[legacy.id] = student
        students_by_name[normalize_name(legacy.name)] = student
        created_students += 1

    for photo in approved:
        if photo.action != "create":
            continue
        normalized = normalize_name(photo.target_student_name)
        if normalized in students_by_name:
            continue
        student = Student(name=photo.target_student_name)
        session.add(student)
        students_by_name[normalized] = student
        created_students += 1
    session.flush()

    storage = PrivateStorage(storage_root)
    samples_by_pair = {
        (sample.student_id, sample.sha256): sample for sample in existing_samples
    }
    written_keys: list[str] = []
    jobs: list[ProcessingJob] = []
    samples_created = 0
    samples_already_present = 0
    skipped_photos = 0
    try:
        for photo in approved:
            if photo.action == "skip":
                skipped_photos += 1
                continue
            if photo.action == "map":
                student = students_by_id[photo.target_student_id]
            else:
                student = students_by_name[normalize_name(photo.target_student_name)]

            pair = (student.id, photo.source_sha256)
            if pair in samples_by_pair:
                samples_already_present += 1
                continue

            key = storage.enrollment_key(student.id, photo.extension)
            storage.write(key, photo.content)
            written_keys.append(key)
            sample = FaceSample(
                student_id=student.id,
                storage_key=key,
                sha256=photo.source_sha256,
                state=FaceSampleState.PENDING,
                rejection_reason=None,
                embedding=None,
                model_version=ENCODING_MODEL_VERSION,
            )
            job = ProcessingJob(
                kind=JobKind.ENROLLMENT,
                state=JobState.PENDING,
                student_id=student.id,
                input_keys=[key],
                attempt_count=0,
                result=None,
                error_code=None,
                error_message=None,
            )
            session.add(sample)
            session.add(job)
            samples_by_pair[pair] = sample
            jobs.append(job)
            samples_created += 1

        for photo in approved:
            if photo.action == "skip":
                continue
            if _sha256_file(photo.source_path) != photo.source_sha256:
                raise ImportValidationError(
                    f"Source changed while applying manifest: {photo.source_path.name}"
                )
        _reset_student_sequence(session)
        session.commit()
    except Exception:
        session.rollback()
        storage.delete_many(written_keys)
        raise

    failed: list[str] = []
    for job in jobs:
        job_id = str(job.id)
        try:
            if dispatch(job_id) is False:
                raise RuntimeError("The enrollment job could not be queued.")
        except Exception as exc:
            job.state = JobState.DISPATCH_FAILED
            job.error_code = "dispatch_failed"
            job.error_message = str(exc)[:500] or "The enrollment job could not be queued."
            session.commit()
            failed.append(job_id)

    return ApplyReport(
        students_created=created_students,
        samples_created=samples_created,
        samples_already_present=samples_already_present,
        skipped_photos=skipped_photos,
        job_ids=tuple(str(job.id) for job in jobs),
        dispatch_failed_job_ids=tuple(failed),
    )


def _source_root(source_dir: str | Path) -> Path:
    raw = Path(source_dir).expanduser()
    if raw.is_symlink():
        raise ImportValidationError("The photo source must not be a symbolic link.")
    root = raw.resolve()
    if not root.is_dir():
        raise ImportValidationError(f"Photo source is not a directory: {root}")
    return root


def _ensure_manifest_outside_source(manifest: Path, source_root: Path) -> None:
    try:
        manifest.relative_to(source_root)
    except ValueError:
        return
    raise ImportValidationError("The manifest must be stored outside the photo source.")


def _photo_folders(source_root: Path) -> list[tuple[Path, Path]]:
    result: list[tuple[Path, Path]] = []
    for folder in sorted(source_root.iterdir(), key=lambda path: path.name.casefold()):
        if folder.name.startswith(".") or not folder.is_dir():
            continue
        if folder.is_symlink():
            raise ImportValidationError(f"Symbolic link is not allowed: {folder.name}")
        photos = [
            path
            for path in folder.iterdir()
            if not path.name.startswith(".")
            and path.is_file()
            and path.suffix.casefold() in SUPPORTED_SUFFIXES
        ]
        if any(path.is_symlink() for path in photos):
            raise ImportValidationError(
                f"Symbolic-link photos are not allowed in {folder.name}."
            )
        if len(photos) != 1:
            raise ImportValidationError(
                f"Photo folder {folder.name!r} must contain exactly one JPEG or PNG."
            )
        result.append((folder, photos[0]))
    if not result:
        raise ImportValidationError("The source contains no student photo folders.")
    return result


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _load_and_validate_manifest(
    manifest: Path,
    source_root: Path,
    students: list[LegacyStudent],
) -> list[_ApprovedPhoto]:
    try:
        with manifest.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != MANIFEST_FIELDS:
                raise ImportValidationError("The manifest columns have changed.")
            rows = list(reader)
    except OSError as exc:
        raise ImportValidationError(f"Could not read import manifest: {manifest}") from exc
    if not rows:
        raise ImportValidationError("The import manifest is empty.")

    legacy_by_id = {student.id: student for student in students}
    approved: list[_ApprovedPhoto] = []
    seen_sources: set[str] = set()
    seen_folders: set[str] = set()
    seen_targets: set[tuple[str, str]] = set()
    seen_target_names: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        action = row["action"].strip().casefold()
        if action not in VALID_ACTIONS:
            raise ImportValidationError(f"Row {row_number} has an invalid action.")
        if row["confirmed"].strip().casefold() not in {"true", "1", "yes"}:
            raise ImportValidationError(f"Row {row_number} is not confirmed.")
        relative_source = row["source_file"].strip()
        if relative_source in seen_sources:
            raise ImportValidationError("The manifest contains a duplicate source photo.")
        seen_sources.add(relative_source)
        source_path = _safe_source_file(source_root, relative_source)
        source_folder = row["source_folder"].strip()
        if source_folder != Path(relative_source).parts[0]:
            raise ImportValidationError(
                f"Row {row_number} source folder does not match its source file."
            )
        if source_folder in seen_folders:
            raise ImportValidationError("The manifest contains a duplicate source folder.")
        seen_folders.add(source_folder)
        content = _read_source_image(source_path)
        validated = _validate_source_image(content, source_path)
        expected_hash = row["source_sha256"].strip().casefold()
        if validated.sha256 != expected_hash:
            raise ImportValidationError(
                f"Source hash changed for manifest row {row_number}."
            )

        if action == "skip":
            if row["target_student_id"].strip() or row["target_student_name"].strip():
                raise ImportValidationError(
                    f"Row {row_number} must not assign a target when skipped."
                )
            approved.append(
                _ApprovedPhoto(
                    source_path=source_path,
                    source_sha256=validated.sha256,
                    action=action,
                    target_student_id=None,
                    target_student_name="",
                    content=content,
                    extension=validated.extension,
                )
            )
            continue

        target_name = row["target_student_name"].strip()
        normalized_target_name = normalize_name(target_name)
        if not normalized_target_name:
            raise ImportValidationError(f"Row {row_number} has no target student name.")
        target_id: int | None = None
        if action == "map":
            try:
                target_id = int(row["target_student_id"])
            except ValueError as exc:
                raise ImportValidationError(
                    f"Row {row_number} has an invalid target student ID."
                ) from exc
            legacy = legacy_by_id.get(target_id)
            if legacy is None or normalize_name(legacy.name) != normalized_target_name:
                raise ImportValidationError(
                    f"Row {row_number} does not map to a legacy student."
                )
            target_key = ("id", str(target_id))
        else:
            if row["target_student_id"].strip():
                raise ImportValidationError(
                    f"Row {row_number} must not assign an ID to a new student."
                )
            target_key = ("name", normalized_target_name)

        if target_key in seen_targets or normalized_target_name in seen_target_names:
            raise ImportValidationError("The manifest contains a duplicate target mapping.")
        seen_targets.add(target_key)
        seen_target_names.add(normalized_target_name)
        approved.append(
            _ApprovedPhoto(
                source_path=source_path,
                source_sha256=validated.sha256,
                action=action,
                target_student_id=target_id,
                target_student_name=target_name,
                content=content,
                extension=validated.extension,
            )
        )
    return approved


def _safe_source_file(source_root: Path, relative_value: str) -> Path:
    relative = Path(relative_value)
    if (
        not relative_value
        or relative.is_absolute()
        or ".." in relative.parts
        or len(relative.parts) != 2
    ):
        raise ImportValidationError("A manifest source path escapes the photo source.")
    candidate = source_root.joinpath(relative)
    current = source_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ImportValidationError("Symbolic links are not allowed in source paths.")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(source_root)
    except ValueError as exc:
        raise ImportValidationError(
            "A manifest source path escapes the photo source."
        ) from exc
    if not resolved.is_file() or resolved.suffix.casefold() not in SUPPORTED_SUFFIXES:
        raise ImportValidationError(f"Manifest source is not a JPEG or PNG: {relative_value}")
    return resolved


def _read_source_image(path: Path) -> bytes:
    try:
        with path.open("rb") as handle:
            content = handle.read(MAX_ENROLLMENT_BYTES + 1)
    except OSError as exc:
        raise ImportValidationError(f"Could not read source image: {path}") from exc
    if len(content) > MAX_ENROLLMENT_BYTES:
        raise ImportValidationError(f"Source image exceeds 10 MiB: {path.name}")
    return content


def _validate_source_image(content: bytes, path: Path):
    try:
        return validate_image(content)
    except UploadValidationError as exc:
        raise ImportValidationError(f"Invalid source image {path.name}: {exc.message}") from exc


def _validate_database_state(
    existing_students: list[Student],
    existing_samples: list[FaceSample],
    legacy_students: list[LegacyStudent],
    approved: list[_ApprovedPhoto],
) -> None:
    by_id = {student.id: student for student in existing_students}
    by_name = {normalize_name(student.name): student for student in existing_students}
    for legacy in legacy_students:
        id_match = by_id.get(legacy.id)
        if id_match is not None and normalize_name(id_match.name) != normalize_name(
            legacy.name
        ):
            raise ImportValidationError(
                f"Student ID {legacy.id} already belongs to another name."
            )
        name_match = by_name.get(normalize_name(legacy.name))
        if name_match is not None and name_match.id != legacy.id:
            raise ImportValidationError(
                f"Student name {legacy.name!r} already has another ID."
            )

    reserved_names = {normalize_name(student.name) for student in legacy_students}
    for photo in approved:
        if photo.action != "create":
            continue
        normalized = normalize_name(photo.target_student_name)
        if normalized in reserved_names:
            raise ImportValidationError(
                f"New student {photo.target_student_name!r} duplicates a legacy student."
            )
        database_student = by_name.get(normalized)
        if database_student is not None:
            if not any(
                sample.student_id == database_student.id
                and sample.sha256 == photo.source_sha256
                for sample in existing_samples
            ):
                raise ImportValidationError(
                    f"New student {photo.target_student_name!r} already exists."
                )
            continue
        reserved_names.add(normalized)


def _reset_student_sequence(session: Any) -> None:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('students', 'id'), "
            "COALESCE((SELECT MAX(id) FROM students), 1), true)"
        )
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_parser() -> argparse.ArgumentParser:
    repository_root = Path(__file__).resolve().parents[2]
    default_dump = repository_root / "datadump.json"
    default_source = Path("/Users/pranav/docs/dataset")
    default_manifest = (
        repository_root / "fastapi_app/var/import/student-photo-map.csv"
    )

    parser = argparse.ArgumentParser(
        description="Preview or apply the legacy SmartRoll student-photo import."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("preview", "apply"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument(
            "--dump",
            type=Path,
            default=default_dump if default_dump.is_file() else None,
            required=not default_dump.is_file(),
        )
        command_parser.add_argument(
            "--source",
            type=Path,
            default=default_source if default_source.is_dir() else None,
            required=not default_source.is_dir(),
        )
        command_parser.add_argument(
            "--manifest", type=Path, default=default_manifest
        )
    subparsers.choices["apply"].add_argument("--storage", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "preview":
            report = preview_import(args.dump, args.source, args.manifest)
        else:
            from app.config import settings
            from app.database import SessionLocal
            from app.tasks import dispatch_job

            storage_root = args.storage or settings.storage_root
            with SessionLocal() as session:
                report = apply_import(
                    session,
                    args.dump,
                    args.source,
                    args.manifest,
                    storage_root,
                    lambda job_id: dispatch_job(uuid.UUID(job_id)),
                )
    except ImportValidationError as exc:
        print(f"Import refused: {exc}", file=sys.stderr)
        return 2

    output = asdict(report)
    if isinstance(report, PreviewReport):
        output["manifest_path"] = str(report.manifest_path)
    print(json.dumps(output, indent=2))
    if isinstance(report, ApplyReport) and report.dispatch_failed_job_ids:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
