"""Match complaint text to a transaction in the provided history.

Scoring:
- amount match: +3
- counterparty (phone or substring) match: +3
- type match (transfer/payment/etc.): +2
- status match: +1
Threshold: 3 to consider a match.
"""
from __future__ import annotations

from dataclasses import dataclass

from .entities import ExtractedEntities, extract
from .text import normalize


@dataclass
class MatchResult:
    transaction_id: str | None
    score: int
    reason_codes: list[str]


def _counterparty_in_text(cp: str, text: str) -> bool:
    if not cp:
        return False
    if cp in text:
        return True
    # compare last 8 digits of any phone present in text vs counterparty
    digits = "".join(ch for ch in cp if ch.isdigit())
    if len(digits) >= 8:
        return digits[-8:] in text.replace(" ", "")
    return False


def _type_in_text(txn_type: str, text: str) -> bool:
    synonyms = {
        "transfer": ["transfer", "send", "sent", "পাঠাই", "পাঠিয়েছি"],
        "payment": ["payment", "pay", "paid", "বিল", "পেমেন্ট"],
        "cash_in": ["cash in", "deposit", "জমা", "ক্যাশ ইন"],
        "cash_out": ["cash out", "withdraw", "তুলেছি", "ক্যাশ আউট"],
        "settlement": ["settlement", "সেটেলমেন্ট"],
        "refund": ["refund", "ফেরত"],
    }
    for kw in synonyms.get(txn_type, []):
        if kw in text:
            return True
    return False


def _status_in_text(status: str, text: str) -> bool:
    synonyms = {
        "completed": ["completed", "successful", "হয়েছে", "সফল"],
        "failed": ["failed", "fail", "ফেইল", "ব্যর্থ"],
        "pending": ["pending", "অপেক্ষা", "পেন্ডিং"],
        "reversed": ["reversed", "ফেরত"],
    }
    for kw in synonyms.get(status, []):
        if kw in text:
            return True
    return False


def match_transaction(complaint: str, history: list[dict]) -> MatchResult:
    if not complaint or not history:
        return MatchResult(None, 0, ["no_history"])

    text = normalize(complaint)
    entities: ExtractedEntities = extract(complaint)

    best: tuple[str | None, int, list[str]] = (None, 0, [])

    for txn in history:
        score = 0
        reasons: list[str] = []

        # amount
        try:
            amt = float(txn.get("amount", 0))
        except (TypeError, ValueError):
            amt = 0.0
        if amt and amt in entities.amounts:
            score += 3
            reasons.append("amount_match")

        # counterparty
        cp = str(txn.get("counterparty", ""))
        if _counterparty_in_text(cp, text):
            score += 3
            reasons.append("counterparty_match")

        # type
        ttype = str(txn.get("type", ""))
        if _type_in_text(ttype, text):
            score += 2
            reasons.append("type_match")

        # status
        status = str(txn.get("status", ""))
        if _status_in_text(status, text):
            score += 1
            reasons.append("status_match")

        if score > best[1]:
            best = (str(txn.get("transaction_id")), score, reasons)

    txn_id, score, reasons = best
    if score < 3:
        return MatchResult(None, score, reasons + ["below_threshold"])

    return MatchResult(txn_id, score, ["transaction_match"] + reasons)
