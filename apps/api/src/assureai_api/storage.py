"""Document storage boundary and local filesystem adapter."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import BinaryIO, Protocol


class DocumentStorage(Protocol):
    def save(self, key: str, content: bytes) -> None: ...

    def open(self, key: str) -> AbstractContextManager[BinaryIO]: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...


class LocalDocumentStorage:
    """Store generated keys beneath a configured private directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or Path(key).name != key:
            raise ValueError("Invalid storage key")
        return self.root / key

    def save(self, key: str, content: bytes) -> None:
        path = self._path(key)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)

    @contextmanager
    def open(self, key: str) -> Iterator[BinaryIO]:
        with self._path(key).open("rb") as stream:
            yield stream

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()
