from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable

from PIL import Image, UnidentifiedImageError


class UploadValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidatedImage:
    content: bytes
    extension: str
    media_type: str
    width: int
    height: int
    sha256: str


def read_limited(stream: BinaryIO, max_bytes: int) -> bytes:
    content = stream.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise UploadValidationError(
            "file_too_large",
            f"The image exceeds the {max_bytes // (1024 * 1024)} MiB limit.",
        )
    if not content:
        raise UploadValidationError("empty_file", "The selected file is empty.")
    return content


def validate_image(content: bytes, max_pixels: int = 25_000_000) -> ValidatedImage:
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UploadValidationError(
            "invalid_image", "Choose a readable JPEG or PNG image."
        ) from exc

    formats = {
        "JPEG": ("jpg", "image/jpeg"),
        "PNG": ("png", "image/png"),
    }
    if image_format not in formats:
        raise UploadValidationError(
            "unsupported_image", "Only JPEG and PNG images are supported."
        )
    if width < 128 or height < 128:
        raise UploadValidationError(
            "image_too_small", "Choose an image at least 128 by 128 pixels."
        )
    if width * height > max_pixels:
        raise UploadValidationError(
            "image_too_large", "Choose an image with no more than 25 megapixels."
        )

    extension, media_type = formats[image_format]
    return ValidatedImage(
        content=content,
        extension=extension,
        media_type=media_type,
        width=width,
        height=height,
        sha256=hashlib.sha256(content).hexdigest(),
    )


class PrivateStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def resolve(self, key: str) -> Path:
        if not key or Path(key).is_absolute():
            raise ValueError("Storage keys must be non-empty relative paths.")
        candidate = (self.root / key).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Storage key escapes the private storage root.") from exc
        return candidate

    def write(self, key: str, content: bytes) -> Path:
        destination = self.resolve(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def delete(self, key: str) -> None:
        path = self.resolve(key)
        path.unlink(missing_ok=True)
        self._remove_empty_parents(path.parent)

    def delete_many(self, keys: Iterable[str]) -> None:
        for key in keys:
            self.delete(key)

    def _remove_empty_parents(self, directory: Path) -> None:
        while directory != self.root:
            try:
                directory.rmdir()
            except (FileNotFoundError, OSError):
                return
            directory = directory.parent

    @staticmethod
    def enrollment_key(student_id: int, extension: str) -> str:
        return f"enrollment/{student_id}/{uuid.uuid4()}.{extension}"

    @staticmethod
    def recognition_input_key(job_id: uuid.UUID, extension: str) -> str:
        return f"jobs/{job_id}/input/{uuid.uuid4()}.{extension}"

    @staticmethod
    def recognition_output_key(job_id: uuid.UUID) -> str:
        return f"jobs/{job_id}/processed.jpg"
