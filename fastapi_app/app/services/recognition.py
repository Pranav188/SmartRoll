from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import cv2
import face_recognition
import numpy as np


DETECTION_MODEL = "hog"
MATCH_TOLERANCE = 0.5
ENCODING_MODEL_VERSION = "face_recognition-1.3.0-hog-v1"


class RecognitionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class KnownSample:
    student_id: int
    student_name: str
    embedding: Sequence[float]


def _load_rgb(path: str | Path) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    bgr_image = cv2.imread(str(path))
    if bgr_image is None:
        raise RecognitionError("invalid_image", "The image could not be decoded.")
    return bgr_image, cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)


def encode_enrollment_image(path: str | Path) -> list[float]:
    _, rgb_image = _load_rgb(path)
    boxes = face_recognition.face_locations(rgb_image, model=DETECTION_MODEL)
    if not boxes:
        raise RecognitionError(
            "no_face", "No face was found. Choose a clearer student photo."
        )
    if len(boxes) != 1:
        raise RecognitionError(
            "multiple_faces", "Use a student photo containing exactly one face."
        )
    embeddings = face_recognition.face_encodings(rgb_image, boxes)
    if len(embeddings) != 1:
        raise RecognitionError(
            "encoding_failed", "The detected face could not be encoded."
        )
    return embeddings[0].astype(float).tolist()


def recognize_classroom(
    image_path: str | Path,
    output_path: str | Path,
    samples: Sequence[KnownSample],
    all_students: Sequence[tuple[int, str]],
) -> dict[str, Any]:
    if not samples:
        raise RecognitionError(
            "no_ready_embeddings",
            "No enrolled faces are ready. Enroll a student before recognition.",
        )

    bgr_image, rgb_image = _load_rgb(image_path)
    boxes = face_recognition.face_locations(rgb_image, model=DETECTION_MODEL)
    if not boxes:
        raise RecognitionError(
            "no_faces", "No face was found. Choose a clearer classroom photo."
        )
    encodings = face_recognition.face_encodings(rgb_image, boxes)

    known_embeddings = [np.asarray(sample.embedding, dtype=float) for sample in samples]
    names_by_student: dict[int, str] = {}
    for sample in samples:
        names_by_student[sample.student_id] = sample.student_name

    recognized: dict[int, str] = {}
    review_items: list[dict[str, Any]] = []
    annotations: list[tuple[tuple[int, int, int, int], str, tuple[int, int, int]]] = []

    for box, encoding in zip(boxes, encodings):
        matches = face_recognition.compare_faces(
            known_embeddings, encoding, tolerance=MATCH_TOLERANCE
        )
        vote_counts: dict[int, int] = {}
        for index, matched in enumerate(matches):
            if matched:
                student_id = samples[index].student_id
                vote_counts[student_id] = vote_counts.get(student_id, 0) + 1
        box_payload = {
            "top": int(box[0]),
            "right": int(box[1]),
            "bottom": int(box[2]),
            "left": int(box[3]),
        }

        if not vote_counts:
            review_items.append(
                {"reason": "unknown_face", "box": box_payload, "candidates": []}
            )
            annotations.append((box, "Review", (0, 165, 255)))
            continue

        if len(vote_counts) > 1:
            highest_vote_count = max(vote_counts.values())
            winner_count = sum(
                count == highest_vote_count for count in vote_counts.values()
            )
            candidates = [
                {
                    "id": student_id,
                    "name": names_by_student[student_id],
                    "vote_count": vote_counts[student_id],
                }
                for student_id in sorted(
                    vote_counts,
                    key=lambda item: (-vote_counts[item], names_by_student[item].casefold()),
                )
            ]
            review_items.append(
                {
                    "reason": "tie" if winner_count > 1 else "ambiguous_match",
                    "box": box_payload,
                    "candidates": candidates,
                }
            )
            annotations.append((box, "Review", (0, 165, 255)))
            continue

        student_id = next(iter(vote_counts))
        student_name = names_by_student[student_id]
        if student_id in recognized:
            review_items.append(
                {
                    "reason": "duplicate_student",
                    "box": box_payload,
                    "candidates": [{"id": student_id, "name": student_name}],
                }
            )
            annotations.append((box, "Review", (0, 165, 255)))
            continue

        recognized[student_id] = student_name
        annotations.append((box, student_name, (78, 121, 24)))

    for (top, right, bottom, left), label, color in annotations:
        cv2.rectangle(bgr_image, (left, top), (right, bottom), color, 2)
        label_y = top - 12 if top > 28 else bottom + 22
        cv2.putText(
            bgr_image,
            label,
            (left, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), bgr_image):
        raise RecognitionError(
            "output_failed", "The annotated image could not be saved."
        )

    recognized_students = [
        {"id": student_id, "name": name}
        for student_id, name in sorted(recognized.items(), key=lambda item: item[1].casefold())
    ]
    not_recognized_students = [
        {"id": student_id, "name": name}
        for student_id, name in sorted(all_students, key=lambda item: item[1].casefold())
        if student_id not in recognized
    ]
    return {
        "recognized_students": recognized_students,
        "needs_review": review_items,
        "not_recognized_students": not_recognized_students,
        "unknown_face_count": sum(
            item["reason"] == "unknown_face" for item in review_items
        ),
    }
