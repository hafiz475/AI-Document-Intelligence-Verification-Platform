"""Paragraph-aware deterministic chunking with lightweight provenance."""

from dataclasses import dataclass

from assureai_api.extraction import TextSegment

TARGET_CHARS = 1000
OVERLAP_CHARS = 150


@dataclass(frozen=True)
class ChunkData:
    chunk_index: int
    content: str
    page_number: int | None
    section: str | None
    metadata: dict[str, object]


def _split_long_text(text: str) -> list[str]:
    if len(text) <= TARGET_CHARS:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + TARGET_CHARS, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + TARGET_CHARS // 2, end)
            if boundary > start:
                end = boundary
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - OVERLAP_CHARS, start + 1)
    return [piece for piece in pieces if piece]


def chunk_segments(segments: list[TextSegment]) -> list[ChunkData]:
    """Pack paragraphs without crossing PDF page boundaries."""

    output: list[ChunkData] = []
    current: list[str] = []
    current_page: int | None = None
    current_section: str | None = None
    source_sections: list[str] = []

    def flush() -> None:
        nonlocal current, current_page, current_section, source_sections
        if current:
            content = "\n\n".join(current)
            output.append(
                ChunkData(
                    chunk_index=len(output),
                    content=content,
                    page_number=current_page,
                    section=current_section,
                    metadata={"source_sections": source_sections.copy()},
                )
            )
        current = []
        current_page = None
        current_section = None
        source_sections = []

    for segment in segments:
        paragraphs = [part.strip() for part in segment.content.split("\n\n") if part.strip()]
        for paragraph in paragraphs:
            for piece in _split_long_text(paragraph):
                crosses_page = bool(current) and current_page != segment.page_number
                too_large = bool(current) and len("\n\n".join([*current, piece])) > TARGET_CHARS
                if crosses_page or too_large:
                    flush()
                if not current:
                    current_page = segment.page_number
                    current_section = segment.section
                current.append(piece)
                if segment.section and segment.section not in source_sections:
                    source_sections.append(segment.section)
                if len(piece) >= TARGET_CHARS:
                    flush()
    flush()
    return output
