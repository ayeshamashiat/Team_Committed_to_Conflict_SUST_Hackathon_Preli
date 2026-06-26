"""Classify complaint into one of the 8 case_types."""
from __future__ import annotations

from .text import canonicalize, normalize


def classify(complaint: str) -> tuple[str, list[str]]:
    """Return (case_type, reason_codes)."""
    if not complaint or not complaint.strip():
        return ("other", ["empty_complaint"])

    n = normalize(complaint)
    tags = canonicalize(complaint)

    # priority order — phishing > wrong_transfer > payment_failed > duplicate > merchant > agent > refund > other
    if "phishing" in tags:
        return ("phishing_or_social_engineering", ["phishing_signal"])
    if "wrong_transfer" in tags:
        return ("wrong_transfer", ["wrong_transfer_signal"])
    if "duplicate_payment" in tags:
        return ("duplicate_payment", ["duplicate_signal"])
    if "payment_failed" in tags:
        return ("payment_failed", ["payment_failed_signal"])
    if "merchant_settlement_delay" in tags:
        return ("merchant_settlement_delay", ["merchant_signal"])
    if "agent_cash_in_issue" in tags:
        return ("agent_cash_in_issue", ["agent_signal"])
    if "refund_request" in tags:
        return ("refund_request", ["refund_signal"])

    # fallback heuristic scan
    if "refund" in n or "ফেরত" in n or "money back" in n:
        return ("refund_request", ["refund_fallback"])
    if "merchant" in n or "settlement" in n:
        return ("merchant_settlement_delay", ["merchant_fallback"])
    if "agent" in n:
        return ("agent_cash_in_issue", ["agent_fallback"])
    if "transfer" in n or "sent" in n or "send" in n or "পাঠিয়েছি" in n:
        return ("wrong_transfer", ["transfer_fallback"])

    return ("other", ["no_match"])
