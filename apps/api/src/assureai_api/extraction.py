"""Deterministic PDF, DOCX, and TXT text extraction."""

import re
import unicodedata
from dataclasses import dataclass
from typing import BinaryIO

from docx import Document as DocxDocument
from pypdf import PdfReader


class ExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class TextSegment:
    content: str
    page_number: int | None = None
    section: str | None = None


@dataclass(frozen=True)
class ExtractionResult:
    segments: list[TextSegment]
    page_count: int | None

    @property
    def character_count(self) -> int:
        return len("\n\n".join(segment.content for segment in self.segments))


_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HORIZONTAL_SPACE = re.compile(r"[ \t]+")
_EXCESS_BLANKS = re.compile(r"\n{3,}")


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    value = _CONTROL.sub("", value)
    lines = [_HORIZONTAL_SPACE.sub(" ", line).strip() for line in value.split("\n")]
    return _EXCESS_BLANKS.sub("\n\n", "\n".join(lines)).strip()


def extract_text(stream: BinaryIO, mime_type: str) -> ExtractionResult:
    try:
        if mime_type == "application/pdf":
            reader = PdfReader(stream)
            segments = [
                TextSegment(content=text, page_number=index)
                for index, page in enumerate(reader.pages, start=1)
                if (text := normalize_text(page.extract_text() or ""))
            ]
            result = ExtractionResult(segments=segments, page_count=len(reader.pages))
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            document = DocxDocument(stream)
            segments = [
                TextSegment(content=text, section=f"Paragraph {index}")
                for index, paragraph in enumerate(document.paragraphs, start=1)
                if (text := normalize_text(paragraph.text))
            ]
            result = ExtractionResult(segments=segments, page_count=None)
        elif mime_type == "text/plain":
            text = normalize_text(stream.read().decode("utf-8-sig"))
            result = ExtractionResult(
                segments=[TextSegment(content=text, section="Text")] if text else [],
                page_count=None,
            )
        else:
            raise ExtractionError("Unsupported document type.")
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError("The document could not be parsed.") from exc

    if not result.segments:
        raise ExtractionError("No extractable text was found in the document.")
    return result
