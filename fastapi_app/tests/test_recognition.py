from pathlib import Path

import numpy as np
import pytest

from fastapi_app.app.services import recognition
from fastapi_app.app.services.recognition import KnownSample, RecognitionError


@pytest.fixture
def image_pipeline(monkeypatch):
    monkeypatch.setattr(recognition.cv2, "imread", lambda _: np.zeros((200, 200, 3), dtype=np.uint8))
    monkeypatch.setattr(recognition.cv2, "cvtColor", lambda image, _: image)
    monkeypatch.setattr(recognition.cv2, "rectangle", lambda *args, **kwargs: None)
    monkeypatch.setattr(recognition.cv2, "putText", lambda *args, **kwargs: None)
    monkeypatch.setattr(recognition.cv2, "imwrite", lambda *args, **kwargs: True)


def test_enrollment_requires_exactly_one_face(monkeypatch, image_pipeline):
    monkeypatch.setattr(recognition.face_recognition, "face_locations", lambda *args, **kwargs: [])

    with pytest.raises(RecognitionError) as error:
        recognition.encode_enrollment_image("student.png")

    assert error.value.code == "no_face"


def test_tied_face_is_reviewed_not_recognized(monkeypatch, image_pipeline, tmp_path):
    box = (10, 80, 90, 5)
    monkeypatch.setattr(recognition.face_recognition, "face_locations", lambda *args, **kwargs: [box])
    monkeypatch.setattr(
        recognition.face_recognition,
        "face_encodings",
        lambda *args, **kwargs: [np.zeros(128)],
    )
    monkeypatch.setattr(
        recognition.face_recognition,
        "compare_faces",
        lambda *args, **kwargs: [True, True],
    )
    samples = [
        KnownSample(1, "Ada", [0.0] * 128),
        KnownSample(2, "Grace", [0.0] * 128),
    ]

    result = recognition.recognize_classroom(
        "classroom.png", tmp_path / "processed.jpg", samples, [(1, "Ada"), (2, "Grace")]
    )

    assert result["recognized_students"] == []
    assert result["needs_review"][0]["reason"] == "tie"
    assert [candidate["vote_count"] for candidate in result["needs_review"][0]["candidates"]] == [1, 1]
    assert [student["name"] for student in result["not_recognized_students"]] == [
        "Ada",
        "Grace",
    ]


def test_multi_identity_vote_is_reviewed_even_with_a_unique_majority(
    monkeypatch, image_pipeline, tmp_path
):
    box = (10, 80, 90, 5)
    monkeypatch.setattr(recognition.face_recognition, "face_locations", lambda *args, **kwargs: [box])
    monkeypatch.setattr(
        recognition.face_recognition,
        "face_encodings",
        lambda *args, **kwargs: [np.zeros(128)],
    )
    monkeypatch.setattr(
        recognition.face_recognition,
        "compare_faces",
        lambda *args, **kwargs: [True, True, True],
    )
    samples = [
        KnownSample(1, "Ada", [0.0] * 128),
        KnownSample(1, "Ada", [0.0] * 128),
        KnownSample(2, "Grace", [0.0] * 128),
    ]

    result = recognition.recognize_classroom(
        "classroom.png", tmp_path / "processed.jpg", samples, [(1, "Ada"), (2, "Grace")]
    )

    assert result["recognized_students"] == []
    assert result["needs_review"][0]["reason"] == "ambiguous_match"
    assert result["needs_review"][0]["candidates"] == [
        {"id": 1, "name": "Ada", "vote_count": 2},
        {"id": 2, "name": "Grace", "vote_count": 1},
    ]


def test_duplicate_student_face_is_flagged_for_review(monkeypatch, image_pipeline, tmp_path):
    boxes = [(10, 80, 90, 5), (20, 180, 100, 100)]
    monkeypatch.setattr(recognition.face_recognition, "face_locations", lambda *args, **kwargs: boxes)
    monkeypatch.setattr(
        recognition.face_recognition,
        "face_encodings",
        lambda *args, **kwargs: [np.zeros(128), np.zeros(128)],
    )
    monkeypatch.setattr(
        recognition.face_recognition,
        "compare_faces",
        lambda *args, **kwargs: [True],
    )
    samples = [KnownSample(1, "Ada", [0.0] * 128)]

    result = recognition.recognize_classroom(
        "classroom.png", tmp_path / "processed.jpg", samples, [(1, "Ada")]
    )

    assert result["recognized_students"] == [{"id": 1, "name": "Ada"}]
    assert result["needs_review"][0]["reason"] == "duplicate_student"
    assert result["not_recognized_students"] == []


def test_recognition_fails_when_no_embeddings_are_ready(tmp_path):
    with pytest.raises(RecognitionError) as error:
        recognition.recognize_classroom(
            "classroom.png", Path(tmp_path) / "processed.jpg", [], [(1, "Ada")]
        )

    assert error.value.code == "no_ready_embeddings"
