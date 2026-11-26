"""Private document storage boundary and local/Azure adapters."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import BinaryIO, Protocol

from assureai_api.config import Settings
from assureai_api.observability import operation_span


class DocumentStorage(Protocol):
    provider: str
    container: str | None

    def save(self, key: str, content: bytes, content_type: str | None = None) -> None: ...

    def open(self, key: str) -> AbstractContextManager[BinaryIO]: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def ready(self) -> bool: ...

    def close(self) -> None: ...


class LocalDocumentStorage:
    """Store generated keys beneath a configured private directory."""

    def __init__(self, root: str | Path) -> None:
        self.provider = "local"
        self.container: str | None = None
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._resolved_root = self.root.resolve()

    def _path(self, key: str) -> Path:
        if not key or "\\" in key or any(part in {"", ".", ".."} for part in key.split("/")):
            raise ValueError("Invalid storage key")
        path = (self._resolved_root / Path(*key.split("/"))).resolve()
        if self._resolved_root not in path.parents:
            raise ValueError("Invalid storage key")
        return path

    def save(self, key: str, content: bytes, content_type: str | None = None) -> None:
        del content_type
        with operation_span("storage.save", provider=self.provider):
            path = self._path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(content)
            temporary.replace(path)

    @contextmanager
    def open(self, key: str) -> Iterator[BinaryIO]:
        with (
            operation_span("storage.read", provider=self.provider),
            self._path(key).open("rb") as stream,
        ):
            yield stream

    def delete(self, key: str) -> None:
        with operation_span("storage.delete", provider=self.provider):
            self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def ready(self) -> bool:
        return self._resolved_root.is_dir()

    def close(self) -> None:
        return None


class AzureBlobDocumentStorage:
    """Server-side private Blob Storage adapter using managed identity."""

    provider = "azure_blob"

    def __init__(self, account_url: str, container: str) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        self.container: str | None = container
        self._credential = DefaultAzureCredential()
        self._service = BlobServiceClient(account_url, credential=self._credential)
        self._container = self._service.get_container_client(container)

    @staticmethod
    def _validate_key(key: str) -> str:
        if not key or "\\" in key or any(part in {"", ".", ".."} for part in key.split("/")):
            raise ValueError("Invalid storage key")
        return key

    def save(self, key: str, content: bytes, content_type: str | None = None) -> None:
        from azure.storage.blob import ContentSettings

        with operation_span("storage.save", provider=self.provider):
            self._container.upload_blob(
                self._validate_key(key),
                content,
                overwrite=False,
                content_settings=ContentSettings(content_type=content_type),
            )

    @contextmanager
    def open(self, key: str) -> Iterator[BinaryIO]:
        import io

        with operation_span("storage.read", provider=self.provider):
            content = self._container.download_blob(self._validate_key(key)).readall()
            with io.BytesIO(content) as stream:
                yield stream

    def delete(self, key: str) -> None:
        with operation_span("storage.delete", provider=self.provider):
            self._container.delete_blob(self._validate_key(key), delete_snapshots="include")

    def exists(self, key: str) -> bool:
        return bool(self._container.get_blob_client(self._validate_key(key)).exists())

    def ready(self) -> bool:
        try:
            self._container.get_container_properties()
            return True
        except Exception:
            return False

    def close(self) -> None:
        self._service.close()
        self._credential.close()


def create_document_storage(settings: Settings) -> DocumentStorage:
    if settings.storage_provider == "azure_blob":
        assert settings.azure_storage_account_url is not None
        return AzureBlobDocumentStorage(
            settings.azure_storage_account_url, settings.azure_storage_container
        )
    return LocalDocumentStorage(settings.storage_path)
