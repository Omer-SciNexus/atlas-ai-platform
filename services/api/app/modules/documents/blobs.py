"""Storage for uploaded files.

``BlobStore`` is the interface; ``LocalBlobStore`` writes to a directory. An S3 store will
implement the same three methods in the AWS phase. Keys are built only from UUIDs, so user
input (file names) never becomes part of a path.
"""

import asyncio
from pathlib import Path
from typing import Protocol
from uuid import UUID


class BlobNotFoundError(Exception):
    pass


def blob_key(tenant_id: UUID, document_id: UUID) -> str:
    return f"{tenant_id}/{document_id}"


class BlobStore(Protocol):
    async def put(self, key: str, data: bytes) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


class LocalBlobStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("Blob key escapes the storage root")
        return path

    async def put(self, key: str, data: bytes) -> None:
        def write() -> None:
            path = self._path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write then rename, so a reader never sees a half-written file.
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)

        await asyncio.to_thread(write)

    async def get(self, key: str) -> bytes:
        def read() -> bytes:
            try:
                return self._path(key).read_bytes()
            except FileNotFoundError:
                raise BlobNotFoundError(key) from None

        return await asyncio.to_thread(read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(lambda: self._path(key).unlink(missing_ok=True))
