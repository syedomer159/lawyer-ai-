"""Request-scoped dependencies. A request gets the ONE case named in its URL and that case's
store; nothing here can hand out a second case (ADR-0001)."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException

from app.config import Settings, settings
from app.contracts.cases import Case
from app.llm.embeddings import CaseEmbedder, OllamaEmbedder
from app.store.case_store import CaseStore
from app.store.registry import CASE_ID, Registry


def get_settings() -> Settings:
    return settings


def get_registry(s: Annotated[Settings, Depends(get_settings)]) -> Iterator[Registry]:
    registry = Registry(s.data_dir)
    try:
        yield registry
    finally:
        registry.close()


RegistryDep = Annotated[Registry, Depends(get_registry)]


def get_case(case_id: str, registry: RegistryDep) -> Case:
    case = registry.get(case_id) if CASE_ID.match(case_id) else None
    if case is None:
        raise HTTPException(404, "case not found")
    return case


CaseDep = Annotated[Case, Depends(get_case)]


def get_store(case: CaseDep, registry: RegistryDep) -> Iterator[CaseStore]:
    store = CaseStore(registry.case_dir(case.id))
    try:
        yield store
    finally:
        store.close()


def get_embedder(case: CaseDep, s: Annotated[Settings, Depends(get_settings)]) -> CaseEmbedder:
    return OllamaEmbedder(case.embed_model, s.ollama_base_url)


StoreDep = Annotated[CaseStore, Depends(get_store)]
EmbedderDep = Annotated[CaseEmbedder, Depends(get_embedder)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
