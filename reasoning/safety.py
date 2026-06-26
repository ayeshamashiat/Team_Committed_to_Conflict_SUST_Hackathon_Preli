"""Post-processing safety layer.

Enforces the four rules from Section 8 of the problem statement:
  - No PIN / OTP / password / card-number requests.
  - No unauthorized refund / reversal / unblock promises.
  - No third-party contact directions.
  - Prompt-injection detection (logged, never obeyed).

All replacement strings are safe, neutral, and do not reference credentials.
"""
from __future__ import annotations

import re

# Credential request patterns — case-insensitive whole phrases.
_CREDENTIAL_PATTERNS = [
    r"\b(?:share|send|provide|tell|give|type|enter)\b[^\.]{0,40}\b(?:pin|otp|password|cvv|card\s*number)\b",
    r"\b(?:your|the)\s+(?:pin|otp|password|cvv|card\s*number)\b",
    r"\bpin\s*code\b",
    r"\botp\s*code\b",
]

# Unauthorized commitment patterns.
_COMMITMENT_PATTERNS = [
    r"\bwe\s+(?:will|shall|are\s+going\s+to)\s+refund\b",
    r"\byour\s+refund\s+(?:is|has\s+been)\s+(?:confirmed|approved|processed)\b",
    r"\bwe\s+(?:will|shall|are\s+going\s+to)\s+reverse\b",
    r"\baccount\s+(?:will\s+be\s+)?unblocked\b",
    r"\brefund\s+(?:has\s+been|is)\s+(?:initiated|processed|sent)\b",
    r"\bmoney\s+(?:will\s+be\s+)?returned\s+(?:now|immediately|today)\b",
]

# Third-party direction patterns.
_THIRDPARTY_PATTERNS = [
    r"\bcontact\s+(?:this|that|the)\s+(?:number|person|agent|officer)\b",
    r"\bcall\s+\+?\d{6,}\b",
    r"\bmeet\s+(?:him|her|them)\b",
    r"\bsend\s+money\s+to\s+\+?\d{6,}\b",
]

# Prompt-injection signatures.
_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?previous\s+instructions?",
    r"ignore\s+the\s+above",
    r"disregard\s+(?:all\s+)?prior",
    r"system\s*:\s*you\s+are",
    r"</?\s*system\s*>",
    r"reveal\s+(?:your|the)\s+(?:system|hidden|secret)\s+prompt",
    r"act\s+as\s+(?:an?\s+)?(?:admin|developer|root)",
]

_CREDENTIAL_REPLACEMENTS = [
    ("share your pin", "keep your account secure"),
    ("share your otp", "keep your account secure"),
    ("share your password", "keep your account secure"),
    ("enter your pin", "keep your account secure"),
    ("enter your otp", "keep your account secure"),
    ("enter your password", "keep your account secure"),
    ("send your pin", "keep your account secure"),
    ("send your otp", "keep your account secure"),
    ("provide your pin", "keep your account secure"),
    ("provide your otp", "keep your account secure"),
    ("your pin", "your account security"),
    ("your otp", "your account security"),
    ("your password", "your account security"),
    ("your card number", "your account details"),
]

_SAFE_REFUND_LANGUAGE = (
    "Any eligible amount will be reviewed and returned through official channels "
    "after verification by the support team."
)
_SAFE_UNBLOCK_LANGUAGE = (
    "Account-related actions will be reviewed by the support team and processed "
    "through official channels if eligible."
)


def _apply_replacements(text: str) -> str:
    out = text
    # credential phrase replacements first
    low = out.lower()
    for needle, replacement in _CREDENTIAL_REPLACEMENTS:
        if needle in low:
            # case-insensitive replace keeping replacement as-is
            pattern = re.compile(re.escape(needle), re.IGNORECASE)
            out = pattern.sub(replacement, out)
            low = out.lower()
    # block any remaining credential request patterns outright
    for pat in _CREDENTIAL_PATTERNS:
        out = re.sub(pat, "keep your account secure", out, flags=re.IGNORECASE)
    # block commitment promises
    for pat in _COMMITMENT_PATTERNS:
        out = re.sub(pat, _SAFE_REFUND_LANGUAGE, out, flags=re.IGNORECASE)
    # block third-party contact directions
    for pat in _THIRDPARTY_PATTERNS:
        out = re.sub(pat, "use only official support channels", out, flags=re.IGNORECASE)
    return out


def sanitize_customer_reply(text: str) -> str:
    return _apply_replacements(text or "")


def sanitize_next_action(text: str) -> str:
    # next_action is internal/agent-facing; apply same commitment sanitizer
    out = text or ""
    for pat in _COMMITMENT_PATTERNS:
        out = re.sub(pat, _SAFE_REFUND_LANGUAGE, out, flags=re.IGNORECASE)
    for pat in _COMMITMENT_PATTERNS:
        out = re.sub(pat.replace("refund", "unblock"), _SAFE_UNBLOCK_LANGUAGE, out, flags=re.IGNORECASE)
    return out


def detect_prompt_injection(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(re.search(p, low) for p in _INJECTION_PATTERNS)
