from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal, get_db, init_db
from .schemas import (
    ApprovalRequest,
    AuditView,
    CaseDetail,
    CaseSummary,
    EvaluationSummary,
    MetricsView,
    WebhookReceipt,
)
from .services import (
    accept_webhook,
    approve_proposal,
    audit,
    get_case,
    latest_evaluation,
    initialize_demo_data,
    list_audit,
    list_cases,
    metrics,
    reset_demo,
    save_evaluation,
)
from .worker import worker_loop


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as db:
        initialize_demo_data(db, settings)
    stop_event = asyncio.Event()
    task = asyncio.create_task(worker_loop(settings, stop_event))
    yield
    stop_event.set()
    await task


app = FastAPI(
    title=f"{settings.app_display_name} API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Operator-Token"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; "
        "img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'"
    )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def require_operator(x_operator_token: str = Header(default="", alias="X-Operator-Token")) -> None:
    expected = settings.operator_api_token.strip()
    supplied = x_operator_token.strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Operator access is not configured")
    if len(supplied) > 256 or not compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Operator authentication required")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "display_name": settings.app_display_name,
        "demo_mode": settings.demo_mode,
        "gemini": "configured" if settings.gemini_enabled else "fallback",
        "razorpay": "configured-test" if settings.razorpay_enabled else "demo-adapter",
        "operator_auth": "configured" if settings.operator_api_token else "required",
    }


@app.post("/api/webhooks/razorpay", response_model=WebhookReceipt)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    x_razorpay_event_id: str = Header(default=""),
    db: Session = Depends(get_db),
) -> WebhookReceipt:
    if not x_razorpay_event_id:
        raise HTTPException(status_code=400, detail="x-razorpay-event-id is required")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from exc
        if declared_size < 0:
            raise HTTPException(status_code=400, detail="Invalid Content-Length")
        if declared_size > settings.max_webhook_body_bytes:
            raise HTTPException(status_code=413, detail="Webhook payload is too large")
    buffered = bytearray()
    async for chunk in request.stream():
        if len(buffered) + len(chunk) > settings.max_webhook_body_bytes:
            raise HTTPException(status_code=413, detail="Webhook payload is too large")
        buffered.extend(chunk)
    raw = bytes(buffered)
    try:
        duplicate, _ = accept_webhook(
            db,
            raw_body=raw,
            signature=x_razorpay_signature,
            event_id=x_razorpay_event_id,
            settings=settings,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc
    return WebhookReceipt(accepted=True, duplicate=duplicate, event_id=x_razorpay_event_id)


@app.get("/api/operator/session", dependencies=[Depends(require_operator)])
def operator_session() -> dict:
    return {"authenticated": True}


@app.get("/api/cases", response_model=list[CaseSummary], dependencies=[Depends(require_operator)])
def cases(db: Session = Depends(get_db)) -> list[CaseSummary]:
    return list_cases(db, settings)


@app.get("/api/cases/{case_id}", response_model=CaseDetail, dependencies=[Depends(require_operator)])
def case_detail(case_id: str, db: Session = Depends(get_db)) -> CaseDetail:
    item = get_case(db, case_id, settings)
    if not item:
        raise HTTPException(status_code=404, detail="Case not found")
    return item


@app.post("/api/cases/{case_id}/approve", response_model=CaseDetail, dependencies=[Depends(require_operator)])
def approve(case_id: str, body: ApprovalRequest, db: Session = Depends(get_db)) -> CaseDetail:
    try:
        approve_proposal(db, case_id, body.decision, body.note, settings)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="External test-mode action failed safely") from exc
    return get_case(db, case_id, settings)  # type: ignore[return-value]


@app.get("/api/metrics", response_model=MetricsView, dependencies=[Depends(require_operator)])
def get_metrics(db: Session = Depends(get_db)) -> MetricsView:
    return metrics(db, settings)


@app.get("/api/audit", response_model=list[AuditView], dependencies=[Depends(require_operator)])
def get_audit(limit: int = 100, db: Session = Depends(get_db)) -> list[AuditView]:
    return list_audit(db, settings, min(max(limit, 1), 250))


@app.post("/api/evaluations", response_model=EvaluationSummary, dependencies=[Depends(require_operator)])
def create_evaluation(db: Session = Depends(get_db)) -> EvaluationSummary:
    return save_evaluation(db, settings)


@app.get("/api/evaluations/latest", response_model=EvaluationSummary | None, dependencies=[Depends(require_operator)])
def get_latest_evaluation(db: Session = Depends(get_db)) -> EvaluationSummary | None:
    return latest_evaluation(db)


@app.post("/api/demo/reset", dependencies=[Depends(require_operator)])
def demo_reset(db: Session = Depends(get_db)) -> dict:
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail="Demo mode is disabled")
    reset_demo(db, settings)
    return {"reset": True}


@app.post("/api/demo/failures/{scenario}", dependencies=[Depends(require_operator)])
def inject_failure(scenario: str, db: Session = Depends(get_db)) -> dict:
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail="Demo mode is disabled")
    scenarios = {
        "duplicate": ("Duplicate webhook suppressed", "Ten concurrent deliveries resolved to one idempotent event.", "warning"),
        "gemini-quota": ("Gemini quota fallback", "The structured advisor fell back to deterministic templates; execution stayed gated.", "warning"),
        "razorpay-500": ("Razorpay 5xx contained", "The approved action was marked retryable and no duplicate external reference was stored.", "error"),
        "worker-crash": ("Expired worker lease reclaimed", "A pending job was safely reclaimed after its lease expired.", "warning"),
    }
    if scenario not in scenarios:
        raise HTTPException(status_code=404, detail="Unknown failure scenario")
    title, detail, severity = scenarios[scenario]
    audit(db, "safety" if scenario == "duplicate" else "failure", title, detail, severity=severity, metadata={"injected": True})
    db.commit()
    return {"scenario": scenario, "contained": True}


STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="spa")
