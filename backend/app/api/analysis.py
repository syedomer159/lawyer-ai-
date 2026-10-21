from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response

from app.agents.analysis import analysis_in_background
from app.api.deps import CaseDep, EmbedderDep, SettingsDep, StoreDep
from app.contracts.analysis import Analysis, AnalysisJob, ConflictUpdate
from app.store.analysis_store import latest_job, load_analysis, set_conflict_status, start_job

router = APIRouter(prefix="/api/cases/{case_id}", tags=["analysis"])

# A job still "running" after this long was cut off (e.g. server restart): allow a new run.
STALE_AFTER = timedelta(minutes=30)


def _is_live(job: AnalysisJob | None) -> bool:
    if job is None or job.status != "running":
        return False
    started = datetime.fromisoformat(job.started_at).replace(tzinfo=UTC)
    return datetime.now(UTC) - started < STALE_AFTER


@router.post("/analysis", status_code=202)
def start_analysis(
    case: CaseDep,
    store: StoreDep,
    settings: SettingsDep,
    embedder: EmbedderDep,
    background: BackgroundTasks,
) -> AnalysisJob:
    """Run the analysis workflow in the background. Poll GET /analysis for progress."""
    if _is_live(latest_job(store, "analysis")):
        raise HTTPException(409, "an analysis is already running for this case")
    if not any(d.status == "ready" for d in store.list_documents()):
        raise HTTPException(400, "upload documents and wait for them to be ready first")
    job_id = start_job(store, "analysis")
    background.add_task(analysis_in_background, store.dir, case, settings, job_id, embedder)
    job = latest_job(store, "analysis")
    assert job is not None
    return job


@router.get("/analysis")
def get_analysis(store: StoreDep) -> Analysis:
    return load_analysis(store)


@router.patch("/conflicts/{conflict_id}", status_code=204)
def update_conflict(conflict_id: int, body: ConflictUpdate, store: StoreDep) -> Response:
    if not set_conflict_status(store, conflict_id, body.status):
        raise HTTPException(404, "conflict not found")
    return Response(status_code=204)
