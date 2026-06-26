"""Extract entities (amount, phone, time-of-day) from complaint text."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


_AMOUNT_PATTERNS = [
    # "5000 taka", "5000 tk", "৫০০০ টাকা", "5k", "5 thousand"
    re.compile(r"(\d[\d,\.]*)\s*(?:taka|tk|টাকা)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:k|thousand)\b", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac)\b", re.IGNORECASE),
    re.compile(r"\b(\d{2,7})\b"),
]

_PHONE_PATTERN = re.compile(r"(\+?88?0?1[3-9]\d{8})")

_TIME_PATTERNS = [
    re.compile(r"\b(\d{1,2})\s*(?:am|pm)\b", re.IGNORECASE),
    re.compile(r"\b(morning|afternoon|evening|night|সকাল|দুপুর|রাত|সন্ধ্যা)\b", re.IGNORECASE),
]


@dataclass
class ExtractedEntities:
    amounts: list[float] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    time_hints: list[str] = field(default_factory=list)


def _to_float(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def extract(text: str) -> ExtractedEntities:
    out = ExtractedEntities()
    if not text:
        return out

    seen_amounts: set[float] = set()
    for pat in _AMOUNT_PATTERNS:
        for m in pat.finditer(text):
            raw = m.group(1)
            val = _to_float(raw)
            if val is None:
                continue
            # unit conversion
            low = text[max(0, m.start() - 1): m.end() + 8].lower()
            if "lakh" in low or "lac" in low:
                val *= 100_000
            elif re.search(r"\d\s*(k|thousand)\b", low):
                val *= 1_000
            if val not in seen_amounts:
                seen_amounts.add(val)
                out.amounts.append(val)

    for m in _PHONE_PATTERN.finditer(text):
        out.phones.append(m.group(1))

    for pat in _TIME_PATTERNS:
        for m in pat.finditer(text):
            out.time_hints.append(m.group(1).lower())

    return out
