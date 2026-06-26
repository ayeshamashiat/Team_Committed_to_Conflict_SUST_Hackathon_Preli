"""Compare complaint claim vs. matched transaction to produce an evidence verdict."""
from __future__ import annotations

from .text import normalize


_INCONSISTENCY_TOKENS = [
    # complaint says deducted / failed / not received but txn is completed
    ("completed", ["deducted but not", "taka keteche", "টাকা কেটে", "কেটে গেছে", "didn't receive", "not received", "পাইনি"]),
    ("failed", ["successful", "received", "হয়েছে", "পেয়েছি", "পেয়েছেন"]),
]


def verify(complaint: str, matched_txn: dict | None) -> tuple[str, str]:
    """Return (verdict, reason_code)."""
    if matched_txn is None:
        return ("insufficient_data", "no_matching_transaction")

    text = normalize(complaint)
    status = str(matched_txn.get("status", "")).lower()

    # Case 1: complaint says deducted / failed / not received
    deduct_phrases = ["deducted but", "taka keteche", "টাকা কেটে", "কেটে গেছে",
                      "didn't receive", "not received", "পাইনি", "received nai", "pay nai"]
    says_deducted = any(p in text for p in deduct_phrases)

    if says_deducted and status == "completed":
        return ("inconsistent", "complaint_says_deducted_but_completed")
    if says_deducted and status in ("failed", "reversed"):
        return ("consistent", "complaint_aligned_with_status")

    # Case 2: complaint says "failed" but txn completed
    fail_words = ["failed", "fail hoyeche", "ফেইল", "ব্যর্থ", "transaction failed", "payment failed"]
    if any(w in text for w in fail_words) and status == "completed":
        return ("inconsistent", "complaint_says_failed_but_completed")

    # Case 3: complaint says received/completed but txn failed
    ok_words = ["received", "successful", "হয়েছে", "পেয়েছি"]
    if any(w in text for w in ok_words) and status in ("failed", "reversed"):
        return ("inconsistent", "complaint_says_success_but_failed")

    # Case 4: pending → insufficient
    if status == "pending":
        return ("insufficient_data", "transaction_pending")

    # Default: consistent
    return ("consistent", "data_supports_complaint")
