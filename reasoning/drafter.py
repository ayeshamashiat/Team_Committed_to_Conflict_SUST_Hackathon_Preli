"""Draft agent_summary, recommended_next_action, and customer_reply.

Templates are deliberately short, professional, and safe. They never ask for
credentials and never promise refunds or reversals — the safety layer sanitizes
the output as a final guard.
"""
from __future__ import annotations

from .router import base_severity


def _safe_draft(case_type: str, txn_id: str | None, verdict: str) -> tuple[str, str, str]:
    txn_phrase = f"transaction {txn_id}" if txn_id else "the reported transaction"
    verdict_phrase = {
        "consistent": "matches the customer complaint",
        "inconsistent": "does not match what the customer described",
        "insufficient_data": "could not be fully verified from the available history",
    }[verdict]

    summary_map = {
        "wrong_transfer": (
            f"Customer reports a transfer sent to the wrong recipient. "
            f"Available history ({txn_phrase}) {verdict_phrase}.",
            "Verify recipient details and amount with the customer, then escalate for dispute resolution.",
            f"We have noted your concern about {txn_phrase}. Our team will review the details and contact you through official channels.",
        ),
        "payment_failed": (
            f"Customer reports a failed transaction where funds may have been deducted. "
            f"Available history ({txn_phrase}) {verdict_phrase}.",
            "Check transaction status with the payments ops team and confirm whether a reversal is needed.",
            f"We understand your concern about {txn_phrase}. Our payments team will investigate and update you through official channels.",
        ),
        "duplicate_payment": (
            f"Customer reports being charged multiple times for the same payment. "
            f"Available history ({txn_phrase}) {verdict_phrase}.",
            "Verify duplicate entries with payments ops and queue for reconciliation.",
            f"Thank you for flagging this. Our team will review {txn_phrase} and follow up through official channels.",
        ),
        "refund_request": (
            f"Customer is requesting a refund related to {txn_phrase}. "
            f"Available history {verdict_phrase}.",
            "Review transaction eligibility for refund and route to the appropriate team.",
            f"Thank you for reaching out. We have recorded your request about {txn_phrase} and our team will review it through official channels.",
        ),
        "merchant_settlement_delay": (
            f"Merchant reports a delayed settlement. Available history ({txn_phrase}) {verdict_phrase}.",
            "Check settlement pipeline with merchant operations and confirm expected payout window.",
            f"We have noted your settlement concern regarding {txn_phrase}. Our merchant operations team will review and respond through official channels.",
        ),
        "agent_cash_in_issue": (
            f"Customer reports an agent cash-in that did not reflect in their balance. "
            f"Available history ({txn_phrase}) {verdict_phrase}.",
            "Verify agent receipt and reconciliation with agent operations.",
            f"We have recorded your concern about {txn_phrase}. Our team will verify the agent transaction through official channels.",
        ),
        "phishing_or_social_engineering": (
            "Customer reports a suspected phishing or social engineering attempt.",
            "Escalate immediately to fraud risk; do not engage further with the suspicious contact.",
            "Thank you for reporting this. Please do not share any codes or account details with anyone. Our fraud team will contact you only through official channels.",
        ),
        "other": (
            f"Customer submitted a general inquiry. Available history ({txn_phrase}) {verdict_phrase}.",
            "Route to customer support for triage and direct response.",
            f"Thank you for contacting us. We have noted your message about {txn_phrase} and will respond through official channels.",
        ),
    }

    return summary_map.get(case_type, summary_map["other"])


def draft(case_type: str, txn_id: str | None, verdict: str) -> dict[str, str]:
    summary, action, reply = _safe_draft(case_type, txn_id, verdict)
    severity = base_severity(case_type)
    return {
        "agent_summary": summary,
        "recommended_next_action": action,
        "customer_reply": reply,
        "severity": severity,
    }
