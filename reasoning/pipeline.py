"""Top-level pipeline: orchestrates Groq LLM, rule-based fallback, and safety.

Layered behavior:
    1. Rule-based pre-check (phishing shortcut, prompt-injection flag).
    2. Try Groq LLM for rich reasoning.
    3. On any failure (no key, API error, bad JSON, timeout) fall back to the
       deterministic rule pipeline.
    4. Always run the safety sanitizer as the final pass — defense in depth.
"""
from __future__ import annotations

import logging
from typing import Any

from .classifier import classify
from .drafter import draft
from .llm import GroqUnavailable, call_groq
from .matcher import match_transaction
from .router import escalate, route
from .safety import (
    detect_prompt_injection,
    sanitize_customer_reply,
    sanitize_next_action,
)
from .verifier import verify

logger = logging.getLogger("queuestorm.reasoning.pipeline")


# ----------------------------- Pre-checks ----------------------------- #

_PHISHING_KEYWORDS = (
    "pin", "otp", "password", "secret code", "verification code",
    "cvv", "card number", "share your", "send your",
)
_PHISHING_BANGLA = (
    "ওটিপি", "পিন", "পাসওয়ার্ড", "গোপন কোড", "কার্ড নম্বর",
)


def _looks_like_phishing_request(complaint: str) -> bool:
    """True when the complaint text says someone asked for credentials."""
    if not complaint:
        return False
    low = complaint.lower()
    bangla_hit = any(b in complaint for b in _PHISHING_BANGLA)
    english_hit = any(kw in low for kw in _PHISHING_KEYWORDS)
    if not (bangla_hit or english_hit):
        return False
    # require a context word like "asked", "told me", "requested", "চেয়েছে"
    context_en = ("asked", "told me", "request", "demanded", "share with", "sent me a")
    context_bn = ("চেয়েছে", "বলেছে", "জিজ্ঞেস করেছে", "চাইছে")
    return any(c in low for c in context_en) or any(c in complaint for c in context_bn)


def _phishing_override() -> dict[str, Any]:
    return {
        "case_type": "phishing_or_social_engineering",
        "severity": "critical",
        "department": "fraud_risk",
        "human_review_required": True,
        "agent_summary": "Customer reports someone asking for PIN/OTP/password or other credentials — suspected phishing.",
        "recommended_next_action": "Escalate immediately to fraud_risk. Do not contact the third party. Preserve all evidence.",
        "customer_reply": (
            "Thank you for reporting this. Please do not share any codes or "
            "account details with anyone. Our fraud team will contact you only "
            "through official channels."
        ),
        "confidence": 0.95,
    }


def _confidence(match_score: int, verdict: str, case_type: str, matched: bool) -> float:
    """Estimate confidence from evidence strength while keeping review cases cautious."""
    if case_type == "phishing_or_social_engineering":
        return 0.95
    if not matched or verdict == "insufficient_data":
        return 0.35

    # The matcher threshold is 3. Scores around 5 mean two strong signals
    # such as amount + transfer wording; 8+ means amount/counterparty/type.
    score_confidence = min(0.95, 0.58 + (min(match_score, 8) / 8) * 0.34)
    if verdict == "inconsistent":
        score_confidence -= 0.08
    return round(max(0.1, min(score_confidence, 0.95)), 2)


# ----------------------------- Fallback ----------------------------- #

def _fallback_response(ticket: dict[str, Any], reason: str) -> dict[str, Any]:
    """Deterministic safe response when the LLM path is unavailable."""
    complaint = ticket.get("complaint", "")
    history = ticket.get("transaction_history") or []

    match = match_transaction(complaint, history)
    matched_txn = None
    if match.transaction_id:
        matched_txn = next(
            (t for t in history if str(t.get("transaction_id")) == match.transaction_id),
            None,
        )
    verdict, verdict_reason = verify(complaint, matched_txn)
    case_type, case_reasons = classify(complaint)
    base = draft(case_type, match.transaction_id, verdict)
    amount = float(matched_txn["amount"]) if matched_txn and matched_txn.get("amount") is not None else None
    severity = escalate(base["severity"], verdict, amount)
    department = route(case_type, severity)

    return {
        "ticket_id": ticket.get("ticket_id", ""),
        "relevant_transaction_id": match.transaction_id,
        "evidence_verdict": verdict,
        "case_type": case_type,
        "severity": severity,
        "department": department,
        "agent_summary": base["agent_summary"],
        "recommended_next_action": sanitize_next_action(base["recommended_next_action"]),
        "customer_reply": sanitize_customer_reply(base["customer_reply"]),
        "human_review_required": True,
        "confidence": _confidence(match.score, verdict, case_type, matched_txn is not None),
        "reason_codes": case_reasons + match.reason_codes + [verdict_reason, reason],
    }


# ----------------------------- Entry point ----------------------------- #

def analyze(ticket: dict[str, Any]) -> dict[str, Any]:
    """Top-level entry point. Returns a dict matching the response schema."""
    ticket_id = str(ticket.get("ticket_id", ""))
    complaint = ticket.get("complaint", "")

    # 1. Prompt-injection detection (always log, never obey)
    injection_attempted = detect_prompt_injection(complaint)
    if injection_attempted:
        logger.warning("prompt_injection_detected ticket_id=%s", ticket_id)

    # 2. Phishing shortcut — if the complaint clearly describes someone asking
    #    for credentials, short-circuit to a safe phishing response.
    if _looks_like_phishing_request(complaint):
        ovr = _phishing_override()
        return {
            "ticket_id": ticket_id,
            "relevant_transaction_id": None,
            "evidence_verdict": "insufficient_data",
            "case_type": ovr["case_type"],
            "severity": ovr["severity"],
            "department": ovr["department"],
            "agent_summary": ovr["agent_summary"],
            "recommended_next_action": sanitize_next_action(ovr["recommended_next_action"]),
            "customer_reply": sanitize_customer_reply(ovr["customer_reply"]),
            "human_review_required": ovr["human_review_required"],
            "confidence": ovr["confidence"],
            "reason_codes": ["phishing_signal", "pre_check_override"]
            + (["prompt_injection_detected"] if injection_attempted else []),
        }

    # 3. Try Groq LLM — any failure falls back to the deterministic pipeline.
    try:
        llm_result = call_groq(ticket)
    except GroqUnavailable as e:
        logger.info("LLM unavailable, using rule-based fallback: %s", e)
        result = _fallback_response(ticket, reason="api_fallback")
        if injection_attempted:
            result["reason_codes"] = list(result.get("reason_codes", [])) + ["prompt_injection_detected"]
        return result
    except Exception as e:
        logger.exception("LLM call failed unexpectedly, using rule-based fallback: %s", e)
        result = _fallback_response(ticket, reason="llm_error")
        if injection_attempted:
            result["reason_codes"] = list(result.get("reason_codes", [])) + ["prompt_injection_detected"]
        return result

    # 4. Merge in injection flag and run final safety pass
    llm_result["ticket_id"] = ticket_id  # enforce echo
    llm_result["customer_reply"] = sanitize_customer_reply(llm_result.get("customer_reply", ""))
    llm_result["recommended_next_action"] = sanitize_next_action(
        llm_result.get("recommended_next_action", "")
    )
    if injection_attempted:
        codes = list(llm_result.get("reason_codes") or [])
        if "prompt_injection_detected" not in codes:
            codes.append("prompt_injection_detected")
        llm_result["reason_codes"] = codes

    return llm_result
