from io import BytesIO

import pytest
from PIL import Image

from fastapi_app.app.services.storage import (
    PrivateStorage,
    UploadValidationError,
    read_limited,
    validate_image,
)


def make_image_bytes(size: tuple[int, int] = (256, 256), image_format: str = "PNG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=(230, 235, 240)).save(buffer, format=image_format)
    return buffer.getvalue()


def test_validate_image_accepts_png_and_reports_content_hash():
    content = make_image_bytes()

    image = validate_image(content)

    assert image.extension == "png"
    assert image.media_type == "image/png"
    assert image.width == 256
    assert image.height == 256
    assert len(image.sha256) == 64


def test_validate_image_rejects_small_images():
    with pytest.raises(UploadValidationError, match="at least 128") as error:
        validate_image(make_image_bytes((64, 64)))

    assert error.value.code == "image_too_small"


def test_read_limited_rejects_oversized_stream():
    with pytest.raises(UploadValidationError) as error:
        read_limited(BytesIO(b"1234"), max_bytes=3)

    assert error.value.code == "file_too_large"


def test_private_storage_prevents_path_traversal(tmp_path):
    storage = PrivateStorage(tmp_path)

    with pytest.raises(ValueError, match="escapes"):
        storage.resolve("../outside.jpg")


def test_private_storage_writes_and_deletes_generated_key(tmp_path):
    storage = PrivateStorage(tmp_path)
    key = storage.enrollment_key(7, "png")

    destination = storage.write(key, b"image")

    assert destination.read_bytes() == b"image"
    storage.delete(key)
    assert not destination.exists()


def test_private_storage_removes_temporary_file_when_replace_fails(
    tmp_path, monkeypatch
):
    storage = PrivateStorage(tmp_path)
    key = storage.enrollment_key(7, "png")

    def fail_replace(*_):
        raise OSError("disk error")

    monkeypatch.setattr("fastapi_app.app.services.storage.os.replace", fail_replace)

    with pytest.raises(OSError, match="disk error"):
        storage.write(key, b"image")

    assert list(tmp_path.rglob("*.tmp")) == []
