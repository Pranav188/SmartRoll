from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path

import pytest
from PIL import Image

from app.importer import ImportValidationError, apply_import, preview_import
from app.models import FaceSample, JobState, ProcessingJob, Student


def _write_dump(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "model": "core.student",
                    "pk": 17,
                    "fields": {
                        "name": "ashish",
                        "created_at": "2025-11-29T14:57:24.754Z",
                    },
                },
                {
                    "model": "core.student",
                    "pk": 18,
                    "fields": {
                        "name": "vedant_raut",
                        "created_at": "2025-11-29T14:57:49.314Z",
                    },
                },
            ]
        ),
        encoding="utf-8",
    )


def _write_image(path: Path, color: str = "white") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 128), color).save(path)


def _fixture_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    dump = tmp_path / "datadump.json"
    source = tmp_path / "dataset"
    manifest = tmp_path / "var" / "import" / "students.csv"
    _write_dump(dump)
    _write_image(source / "ashish" / "ashish.png")
    _write_image(source / "vedantr" / "vedantr.jpg", "black")
    return dump, source, manifest


def _read_rows(manifest: Path) -> list[dict[str, str]]:
    with manifest.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_rows(manifest: Path, rows: list[dict[str, str]]) -> None:
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def _confirm_all(rows: list[dict[str, str]]) -> None:
    for row in rows:
        row["confirmed"] = "true"


class _ScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows


class _Dialect:
    name = "sqlite"


class _Bind:
    dialect = _Dialect()


class _FakeSession:
    def __init__(self) -> None:
        self.rows: list[object] = []
        self.commit_count = 0
        self.rollback_count = 0

    def scalars(self, model: type[object]) -> _ScalarResult:
        return _ScalarResult([row for row in self.rows if isinstance(row, model)])

    def add(self, row: object) -> None:
        self.rows.append(row)

    def flush(self) -> None:
        students = [row for row in self.rows if isinstance(row, Student)]
        next_id = max((row.id or 0 for row in students), default=0) + 1
        for student in students:
            if student.id is None:
                student.id = next_id
                next_id += 1
        for row in self.rows:
            if isinstance(row, (FaceSample, ProcessingJob)) and row.id is None:
                row.id = uuid.uuid4()

    def commit(self) -> None:
        self.flush()
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def get_bind(self) -> _Bind:
        return _Bind()


def test_preview_only_auto_maps_normalized_exact_names(tmp_path: Path) -> None:
    dump, source, manifest = _fixture_tree(tmp_path)
    source_hashes = {
        path.relative_to(source): path.read_bytes() for path in source.rglob("*.*")
    }

    report = preview_import(dump, source, manifest)

    rows = _read_rows(manifest)
    assert report.photo_folder_count == 2
    assert report.exact_match_count == 1
    assert report.unresolved_folders == ("vedantr",)
    assert report.students_without_photos == ("vedant_raut",)
    assert rows[0]["source_folder"] == "ashish"
    assert rows[0]["action"] == "map"
    assert rows[0]["target_student_id"] == "17"
    assert rows[0]["confirmed"] == "false"
    assert rows[1]["source_folder"] == "vedantr"
    assert rows[1]["action"] == "skip"
    assert rows[1]["target_student_id"] == ""
    assert rows[1]["confirmed"] == "false"
    assert {
        path.relative_to(source): path.read_bytes() for path in source.rglob("*.*")
    } == source_hashes


def test_apply_refuses_an_unconfirmed_row_before_database_access(tmp_path: Path) -> None:
    dump, source, manifest = _fixture_tree(tmp_path)
    preview_import(dump, source, manifest)

    with pytest.raises(ImportValidationError, match="not confirmed"):
        apply_import(object(), dump, source, manifest, tmp_path / "storage", lambda _: None)


def test_apply_refuses_a_changed_source_hash_before_database_access(
    tmp_path: Path,
) -> None:
    dump, source, manifest = _fixture_tree(tmp_path)
    preview_import(dump, source, manifest)
    rows = _read_rows(manifest)
    _confirm_all(rows)
    _write_rows(manifest, rows)
    _write_image(source / "ashish" / "ashish.png", "red")

    with pytest.raises(ImportValidationError, match="Source hash changed"):
        apply_import(object(), dump, source, manifest, tmp_path / "storage", lambda _: None)


def test_apply_refuses_source_path_traversal(tmp_path: Path) -> None:
    dump, source, manifest = _fixture_tree(tmp_path)
    preview_import(dump, source, manifest)
    rows = _read_rows(manifest)
    rows[0]["source_file"] = "../outside.png"
    _confirm_all(rows)
    _write_rows(manifest, rows)

    with pytest.raises(ImportValidationError, match="escapes"):
        apply_import(object(), dump, source, manifest, tmp_path / "storage", lambda _: None)


def test_apply_refuses_duplicate_target_mappings(tmp_path: Path) -> None:
    dump, source, manifest = _fixture_tree(tmp_path)
    preview_import(dump, source, manifest)
    rows = _read_rows(manifest)
    rows[1].update(
        {
            "target_student_id": "17",
            "target_student_name": "ashish",
            "action": "map",
            "confirmed": "true",
        }
    )
    _confirm_all(rows)
    _write_rows(manifest, rows)

    with pytest.raises(ImportValidationError, match="duplicate target"):
        apply_import(object(), dump, source, manifest, tmp_path / "storage", lambda _: None)


def test_manifest_cannot_be_written_inside_source(tmp_path: Path) -> None:
    dump, source, _ = _fixture_tree(tmp_path)

    with pytest.raises(ImportValidationError, match="outside"):
        preview_import(dump, source, source / "manifest.csv")


def test_apply_is_idempotent_and_dispatches_only_after_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dump, source, manifest = _fixture_tree(tmp_path)
    preview_import(dump, source, manifest)
    rows = _read_rows(manifest)
    _confirm_all(rows)
    _write_rows(manifest, rows)
    session = _FakeSession()
    monkeypatch.setattr("sqlalchemy.select", lambda model: model)
    dispatch_commit_counts: list[int] = []

    first = apply_import(
        session,
        dump,
        source,
        manifest,
        tmp_path / "storage",
        lambda _: dispatch_commit_counts.append(session.commit_count),
    )
    second = apply_import(
        session,
        dump,
        source,
        manifest,
        tmp_path / "storage",
        lambda _: pytest.fail("An idempotent import must not redispatch work."),
    )

    assert first.students_created == 2
    assert first.samples_created == 1
    assert first.skipped_photos == 1
    assert len(first.job_ids) == 1
    assert dispatch_commit_counts == [1]
    assert {(row.id, row.name) for row in session.rows if isinstance(row, Student)} == {
        (17, "ashish"),
        (18, "vedant_raut"),
    }
    assert (source / "ashish" / "ashish.png").is_file()
    assert second.students_created == 0
    assert second.samples_created == 0
    assert second.samples_already_present == 1
    assert len(list((tmp_path / "storage").rglob("*.png"))) == 1


def test_dispatch_failure_is_persisted_for_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dump, source, manifest = _fixture_tree(tmp_path)
    preview_import(dump, source, manifest)
    rows = _read_rows(manifest)
    _confirm_all(rows)
    _write_rows(manifest, rows)
    session = _FakeSession()
    monkeypatch.setattr("sqlalchemy.select", lambda model: model)

    def fail_dispatch(_: str) -> None:
        raise ConnectionError("Redis is unavailable")

    report = apply_import(
        session, dump, source, manifest, tmp_path / "storage", fail_dispatch
    )

    assert report.dispatch_failed_job_ids == report.job_ids
    job = next(row for row in session.rows if isinstance(row, ProcessingJob))
    assert job.state == JobState.DISPATCH_FAILED
    assert job.error_code == "dispatch_failed"
    assert session.commit_count == 2


def test_apply_can_create_a_confirmed_nonlegacy_student(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dump, source, manifest = _fixture_tree(tmp_path)
    preview_import(dump, source, manifest)
    rows = _read_rows(manifest)
    rows[1].update(
        {
            "target_student_name": "vedantr",
            "action": "create",
            "confirmed": "true",
        }
    )
    _confirm_all(rows)
    _write_rows(manifest, rows)
    session = _FakeSession()
    monkeypatch.setattr("sqlalchemy.select", lambda model: model)

    report = apply_import(
        session, dump, source, manifest, tmp_path / "storage", lambda _: None
    )

    assert report.students_created == 3
    assert report.samples_created == 2
    assert report.skipped_photos == 0
    assert {row.name for row in session.rows if isinstance(row, Student)} == {
        "ashish",
        "vedant_raut",
        "vedantr",
    }
