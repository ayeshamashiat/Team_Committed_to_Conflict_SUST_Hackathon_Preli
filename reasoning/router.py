"""Routing and severity decisions.

Maps case_type → department and computes severity from case_type + amount + verdict.
"""
from __future__ import annotations


# Section 7.2 of the problem statement
DEPARTMENT_MAP: dict[str, str] = {
    "wrong_transfer": "dispute_resolution",
    "payment_failed": "payments_ops",
    "duplicate_payment": "payments_ops",
    "refund_request": "dispute_resolution",
    "merchant_settlement_delay": "merchant_operations",
    "agent_cash_in_issue": "agent_operations",
    "phishing_or_social_engineering": "fraud_risk",
    "other": "customer_support",
}

# baseline severity per case_type
_BASE_SEVERITY: dict[str, str] = {
    "wrong_transfer": "high",
    "payment_failed": "medium",
    "duplicate_payment": "high",
    "refund_request": "medium",
    "merchant_settlement_delay": "medium",
    "agent_cash_in_issue": "medium",
    "phishing_or_social_engineering": "critical",
    "other": "low",
}

# Refund is contested → dispute_resolution; pure refund ask without contest → customer_support
_REFUND_TO_CUSTOMER_SUPPORT = {"low", "medium"}


def route(case_type: str, severity: str) -> str:
    dept = DEPARTMENT_MAP.get(case_type, "customer_support")
    if case_type == "refund_request" and severity in _REFUND_TO_CUSTOMER_SUPPORT:
        return "customer_support"
    return dept


def base_severity(case_type: str) -> str:
    return _BASE_SEVERITY.get(case_type, "low")


def escalate(severity: str, verdict: str, amount: float | None) -> str:
    """Adjust severity upward given evidence and amount."""
    order = ["low", "medium", "high", "critical"]
    idx = order.index(severity) if severity in order else 0

    if verdict == "inconsistent":
        idx = min(idx + 1, 3)
    if verdict == "insufficient_data":
        idx = min(idx + 1, 3)
    if amount is not None:
        if amount >= 50_000:
            idx = max(idx, 3)  # critical
        elif amount >= 10_000:
            idx = max(idx, 2)  # high

    return order[idx]
