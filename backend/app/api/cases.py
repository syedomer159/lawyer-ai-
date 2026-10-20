from fastapi import APIRouter, Response

from app.api.deps import CaseDep, RegistryDep, SettingsDep
from app.contracts.cases import Case, CaseCreate

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.post("", status_code=201)
def create_case(body: CaseCreate, registry: RegistryDep, settings: SettingsDep) -> Case:
    return registry.create(body, embed_model=settings.embed_model)


@router.get("")
def list_cases(registry: RegistryDep) -> list[Case]:
    return registry.list()


@router.get("/{case_id}")
def get_case(case: CaseDep) -> Case:
    return case


@router.delete("/{case_id}", status_code=204)
def delete_case(case: CaseDep, registry: RegistryDep) -> Response:
    registry.delete(case.id)
    return Response(status_code=204)
