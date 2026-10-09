"""Evaluation Lab endpoints: start a run in the background, then poll for its metrics."""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

from adaptive_rag.api.deps import SessionDep, UserDep
from adaptive_rag.eval.lab import run_lab, write_report
from adaptive_rag.schemas import Mode
from adaptive_rag.store import db

router = APIRouter(prefix="/eval", tags=["evaluation"])
log = logging.getLogger(__name__)


class EvalRunIn(BaseModel):
    dataset: str = "demo"
    modes: list[Mode] | None = None
    full: bool = False  # True also generates answers (spends credits)
    limit: int | None = Field(default=None, ge=1)


class EvalRunOut(BaseModel):
    id: str
    dataset: str
    status: str
    progress: str = ""
    metrics: dict[str, Any] = {}


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
def start_run(
    body: EvalRunIn, _user: UserDep, session: SessionDep, background: BackgroundTasks
) -> EvalRunOut:
    if body.dataset != "demo":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only the 'demo' dataset exists")
    if session.query(db.EvalRun).filter(db.EvalRun.status == "running").first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An evaluation is already running")
    run = db.EvalRun(dataset=body.dataset, mode="full" if body.full else "retrieval")
    session.add(run)
    session.commit()
    background.add_task(_execute, run.id, body)
    return EvalRunOut(id=run.id, dataset=run.dataset, status=run.status)


@router.get("/runs")
def list_runs(_user: UserDep, session: SessionDep) -> list[EvalRunOut]:
    runs = session.query(db.EvalRun).order_by(db.EvalRun.created_at.desc()).limit(20)
    return [_out(run, summary_only=True) for run in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: str, _user: UserDep, session: SessionDep) -> EvalRunOut:
    run = session.get(db.EvalRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return _out(run)


def _out(run: db.EvalRun, summary_only: bool = False) -> EvalRunOut:
    metrics = dict(run.metrics or {})
    progress = metrics.pop("progress", "")
    if summary_only:
        metrics.pop("questions", None)  # the per-question detail is large
    return EvalRunOut(
        id=run.id, dataset=run.dataset, status=run.status, progress=progress, metrics=metrics
    )


def _execute(run_id: str, body: EvalRunIn) -> None:
    def progress(message: str) -> None:
        with db.session_scope() as session:
            run = session.get(db.EvalRun, run_id)
            if run is not None:
                run.metrics = {"progress": message}

    try:
        report = run_lab(modes=body.modes, full=body.full, limit=body.limit, progress=progress)
        write_report(report)
        final_status = "done"
    except Exception as error:
        log.exception("Evaluation run %s failed", run_id)
        report, final_status = {"error": str(error)}, "failed"
    with db.session_scope() as session:
        run = session.get(db.EvalRun, run_id)
        if run is not None:
            run.metrics = report
            run.status = final_status
