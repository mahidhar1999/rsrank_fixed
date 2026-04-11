from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import text
from sqlalchemy.engine import Connection
from typing import Optional
from datetime import datetime
from app.db import get_db
from app.dependencies import require_admin

router = APIRouter()

_pipeline_status = {"running": False, "last_run": None, "last_result": None}


@router.post("/run-daily")
def run_daily_pipeline(
    background_tasks: BackgroundTasks,
    trade_date: Optional[str] = None,
    current_user: dict = Depends(require_admin),
):
    if _pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")

    background_tasks.add_task(_run_daily, trade_date)
    return {"status": "started", "trade_date": trade_date or "today"}


@router.post("/run-monthly")
def run_monthly_pipeline(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_admin),
):
    if _pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")

    background_tasks.add_task(_run_monthly)
    return {"status": "started"}


@router.get("/status")
def pipeline_status(current_user: dict = Depends(require_admin)):
    return _pipeline_status


def _run_daily(trade_date: Optional[str]):
    _pipeline_status["running"] = True
    try:
        from pipeline.daily import run_pipeline
        from datetime import date
        d = datetime.strptime(trade_date, "%Y-%m-%d").date() if trade_date else date.today()
        run_pipeline(d)
        _pipeline_status["last_result"] = "success"
    except Exception as e:
        _pipeline_status["last_result"] = f"error: {str(e)}"
    finally:
        _pipeline_status["running"] = False
        _pipeline_status["last_run"] = datetime.now().isoformat()


def _run_monthly():
    _pipeline_status["running"] = True
    try:
        from pipeline.monthly import run_monthly_pipeline
        run_monthly_pipeline()
        _pipeline_status["last_result"] = "success"
    except Exception as e:
        _pipeline_status["last_result"] = f"error: {str(e)}"
    finally:
        _pipeline_status["running"] = False
        _pipeline_status["last_run"] = datetime.now().isoformat()
