from pathlib import Path
from uuid import uuid4

import pytest

from app.modules.documents.blobs import BlobNotFoundError, LocalBlobStore, blob_key
from app.modules.documents.service import (
    InvalidCursorError,
    _decode_cursor,
    default_title,
    safe_filename,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\me\\Q3 report.pdf", "Q3 report.pdf"),
        ("bad\r\nname\x00.txt", "badname.txt"),
        ("", "document"),
        (None, "document"),
        ("a" * 400 + ".txt", "a" * 255),
    ],
)
def test_safe_filename(raw: str | None, expected: str) -> None:
    assert safe_filename(raw) == expected


def test_default_title_comes_from_the_file_name() -> None:
    assert default_title("jpm_10-k__2025.pdf") == "jpm 10 k 2025"
    assert default_title(".pdf") == ".pdf"


@pytest.mark.parametrize("cursor", ["", "not-base64!", "aGVsbG8=", "MjAyNnxub3QtYS11dWlk"])
def test_bad_cursors_are_rejected(cursor: str) -> None:
    with pytest.raises(InvalidCursorError):
        _decode_cursor(cursor)


async def test_blob_round_trip_and_delete(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)
    key = blob_key(uuid4(), uuid4())

    await store.put(key, b"first")
    await store.put(key, b"second")  # overwrite
    assert await store.get(key) == b"second"

    await store.delete(key)
    await store.delete(key)  # deleting twice is fine
    with pytest.raises(BlobNotFoundError):
        await store.get(key)


async def test_blob_key_cannot_leave_the_storage_root(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path / "blobs")
    with pytest.raises(ValueError, match="escapes"):
        await store.put("../outside", b"x")
    assert not (tmp_path / "outside").exists()
