"""QueueStorm Investigator — FastAPI service.

Exposes:
    GET  /health           → {"status": "ok"}
    POST /analyze-ticket   → structured ticket analysis

All safety guardrails run AFTER reasoning so that no credential request,
unauthorized refund promise, or third-party direction ever reaches the
customer.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from queuestorm.config import settings
from queuestorm.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorResponse,
    HealthResponse,
)
from reasoning.pipeline import analyze as run_pipeline
from reasoning.safety import sanitize_customer_reply, sanitize_next_action

logger = logging.getLogger("queuestorm")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

app = FastAPI(
    title="QueueStorm Investigator",
    version="1.0.0",
    description="AI/API SupportOps copilot for digital finance complaint triage.",
)


# ----------------------------- /health ----------------------------- #

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


# ----------------------------- /analyze-ticket ----------------------------- #

def _safe_error(message: str, status: int) -> JSONResponse:
    body = ErrorResponse(error=message).model_dump()
    return JSONResponse(status_code=status, content=body)


@app.exception_handler(ValidationError)
async def _validation_handler(_: Request, exc: ValidationError) -> JSONResponse:
    return _safe_error("malformed input: invalid schema", 400)


@app.exception_handler(Exception)
async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error: %s", exc)
    return _safe_error("internal error", 500)


@app.post("/analyze-ticket", response_model=AnalyzeResponse)
async def analyze_ticket(payload: AnalyzeRequest) -> AnalyzeResponse:
    # 422 — valid schema but semantically invalid (empty complaint already
    # blocked by Pydantic min_length=1, so we also guard whitespace-only).
    if not payload.complaint.strip():
        raise HTTPException(status_code=422, detail="complaint must not be empty")

    # Run reasoning pipeline
    raw: dict[str, Any] = payload.model_dump()
    result: dict[str, Any] = run_pipeline(raw)

    # Final safety pass — defense in depth even though pipeline already runs it.
    result["customer_reply"] = sanitize_customer_reply(result.get("customer_reply", ""))
    result["recommended_next_action"] = sanitize_next_action(
        result.get("recommended_next_action", "")
    )

    # Echo ticket_id strictly
    result["ticket_id"] = payload.ticket_id

    # Validate response against schema before returning
    try:
        response = AnalyzeResponse(**result)
    except ValidationError as ve:
        logger.error("response schema violation: %s", ve)
        raise HTTPException(status_code=500, detail="internal error: response schema invalid")

    return response


# ----------------------------- Entry point ----------------------------- #

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
    )