"""Step 1: parties and atomic claims from each document (role: extractor)."""

from pydantic import BaseModel, Field

from app.agents.run import AnalysisRun
from app.citations import Citation
from app.contracts.analysis import PartyRole
from app.contracts.documents import Document

MAX_CHARS_PER_CALL = 12_000  # long documents are read in page-ordered parts


class ExtractedParty(BaseModel):
    name: str
    role: PartyRole


class ExtractedClaim(BaseModel):
    speaker: str
    aspect: str
    statement: str
    when: str | None = Field(description="ISO date/time of the event if the text states it")
    citation: Citation


class Extraction(BaseModel):
    parties: list[ExtractedParty]
    claims: list[ExtractedClaim]


def document_parts(run: AnalysisRun, doc: Document) -> list[str]:
    parts: list[str] = []
    current = ""
    for chunk_id, page, text in run.store.doc_chunks(doc.id):
        block = f"[chunk {chunk_id} | page {page}]\n{text}\n"
        if current and len(current) + len(block) > MAX_CHARS_PER_CALL:
            parts.append(current)
            current = ""
        current += block
    return [*parts, current] if current else parts


async def extract_document(run: AnalysisRun, doc: Document) -> Extraction:
    merged = Extraction(parties=[], claims=[])
    for part in document_parts(run, doc):
        out = await run.call(
            "extractor",
            "extractor",
            f'<document name="{doc.filename}">\n{part}</document>',
            Extraction,
            check=lambda e: run.cite_problems([c.citation for c in e.claims]),
        )
        merged.parties += out.parties
        merged.claims += out.claims
    return merged
