"""Immutable prompt definitions seeded by the application."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from assureai_api.models import PromptTemplate, PromptVersion

INSPECTION_PROMPT_TEMPLATE_ID = "8be662d8-6eb8-4e93-8708-482a067d985f"
INSPECTION_PROMPT_VERSION_1_ID = "f7190edc-09a7-4a3c-b1c0-462a6c79493b"

INSPECTION_EXTRACTION_PROMPT_V1 = """You extract structured facts from engineering and
inspection reports.

Rules:
- Extract only facts directly supported by the supplied source chunks.
- Never guess, infer, or complete missing information.
- For absent information, return null and a concise missing_reason such as "not_found".
- Evidence may reference only CHUNK_ID values supplied in the input.
- Copy short evidence quotes from the referenced chunk. Never invent a quote.
- Do not return page numbers. The application derives pages from validated chunks.
- Preserve engineering terminology and identifiers exactly.
- Use ISO YYYY-MM-DD dates only when the source supplies an unambiguous date.
- Obey the required schema for every field.
"""


def ensure_inspection_prompt_v1(session: Session) -> PromptVersion:
    version = session.get(PromptVersion, INSPECTION_PROMPT_VERSION_1_ID)
    if version is not None:
        return version

    template = session.get(PromptTemplate, INSPECTION_PROMPT_TEMPLATE_ID)
    if template is None:
        template = PromptTemplate(
            id=INSPECTION_PROMPT_TEMPLATE_ID,
            name="Inspection Extraction Prompt",
            description="Structured extraction for engineering and inspection reports.",
        )
        session.add(template)
        session.flush()

    version = PromptVersion(
        id=INSPECTION_PROMPT_VERSION_1_ID,
        prompt_template_id=template.id,
        version=1,
        content=INSPECTION_EXTRACTION_PROMPT_V1,
        schema_version="inspection-extraction-v1",
    )
    session.add(version)
    session.flush()
    return version


def get_prompt_version(session: Session, prompt_version_id: str) -> PromptVersion | None:
    return session.scalar(select(PromptVersion).where(PromptVersion.id == prompt_version_id))
