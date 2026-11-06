"""Upload validation based on filename, declared type, and file structure."""

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path


class UploadValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedUpload:
    extension: str
    mime_type: str


SUPPORTED: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


def safe_display_filename(filename: str | None) -> str:
    name = Path((filename or "").replace(chr(92), "/")).name.strip()
    if not name or name in {".", ".."}:
        raise UploadValidationError("A valid filename is required.")
    return name[:255]


def validate_upload(
    filename: str | None, declared_type: str | None, content: bytes, max_bytes: int
) -> tuple[str, ValidatedUpload]:
    if not content:
        raise UploadValidationError("The uploaded file is empty.")
    if len(content) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise UploadValidationError(f"The uploaded file exceeds the {limit_mb} MB limit.")

    safe_name = safe_display_filename(filename)
    extension = Path(safe_name).suffix.lower()
    expected_type = SUPPORTED.get(extension)
    if expected_type is None:
        raise UploadValidationError("Only PDF, DOCX, and TXT files are supported.")

    declared = (declared_type or "").split(";", maxsplit=1)[0].strip().lower()
    permitted_declared = {expected_type, "application/octet-stream", ""}
    if extension == ".txt":
        permitted_declared.update({"text/csv", "text/markdown"})
    if declared not in permitted_declared:
        raise UploadValidationError("The declared file type does not match the filename.")

    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise UploadValidationError("The file content is not a valid PDF signature.")
    if extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise UploadValidationError("The file content is not a valid DOCX document.")
        except zipfile.BadZipFile as exc:
            raise UploadValidationError("The file content is not a valid DOCX document.") from exc
    if extension == ".txt":
        if bytes([0]) in content:
            raise UploadValidationError("The TXT file contains unsupported binary content.")
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise UploadValidationError("TXT files must use UTF-8 encoding.") from exc

    return safe_name, ValidatedUpload(extension=extension, mime_type=expected_type)
