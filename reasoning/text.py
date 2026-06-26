"""Text normalization for QueueStorm.

Normalizes complaint text for keyword matching across English, Bangla, and Banglish.
"""
from __future__ import annotations

import re
import unicodedata

# Bangla digit → Arabic digit
_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

# Common Banglish / Bangla → English canonical phrase map (lowercased keys)
_CANONICAL_PHRASES = {
    # wrong transfer
    "wrong number": "wrong_transfer",
    "wrong recipient": "wrong_transfer",
    "wrong person": "wrong_transfer",
    "send to wrong": "wrong_transfer",
    "sent to wrong": "wrong_transfer",
    "ভুল নম্বরে": "wrong_transfer",
    "ভুল নম্বর": "wrong_transfer",
    "ভুল মানুষ": "wrong_transfer",
    "ভুল রিসিভার": "wrong_transfer",
    "ভুল একাউন্টে": "wrong_transfer",
    # payment failed / balance deducted
    "payment failed": "payment_failed",
    "transaction failed": "payment_failed",
    "failed but deducted": "payment_failed",
    "deducted but": "payment_failed",
    "taka keteche": "payment_failed",
    "taka kete gese": "payment_failed",
    "balance keteche": "payment_failed",
    "টাকা কেটে": "payment_failed",
    "টাকা কাটা": "payment_failed",
    "কেটে নিয়েছে": "payment_failed",
    "কেটে গেছে": "payment_failed",
    "ব্যালেন্স কেটে": "payment_failed",
    # refund
    "refund": "refund_request",
    "refund please": "refund_request",
    "want my money back": "refund_request",
    "money back": "refund_request",
    "return my money": "refund_request",
    "ফেরত": "refund_request",
    "টাকা ফেরত": "refund_request",
    # duplicate payment
    "twice": "duplicate_payment",
    "double charged": "duplicate_payment",
    "charged twice": "duplicate_payment",
    "charged two times": "duplicate_payment",
    "duplicate": "duplicate_payment",
    "দুইবার": "duplicate_payment",
    "দুই বার": "duplicate_payment",
    "ডাবল": "duplicate_payment",
    # merchant settlement
    "merchant": "merchant_settlement_delay",
    "settlement": "merchant_settlement_delay",
    "merchant payment": "merchant_settlement_delay",
    "did not receive settlement": "merchant_settlement_delay",
    "মার্চেন্ট": "merchant_settlement_delay",
    "মার্চেন্ট পেমেন্ট": "merchant_settlement_delay",
    # agent cash in
    "agent": "agent_cash_in_issue",
    "cash in": "agent_cash_in_issue",
    "deposit": "agent_cash_in_issue",
    "agent did not": "agent_cash_in_issue",
    "এজেন্ট": "agent_cash_in_issue",
    "জমা": "agent_cash_in_issue",
    "এজেন্টের কাছে": "agent_cash_in_issue",
    # phishing / scam
    "otp": "phishing",
    "pin": "phishing",
    "password": "phishing",
    "phishing": "phishing",
    "scam": "phishing",
    "fraud call": "phishing",
    "fraud sms": "phishing",
    "asked for otp": "phishing",
    "asked for pin": "phishing",
    "fake": "phishing",
    "ওটিপি": "phishing",
    "পিন": "phishing",
    "পাসওয়ার্ড": "phishing",
    "স্ক্যাম": "phishing",
    "প্রতারণা": "phishing",
}


def normalize(text: str) -> str:
    """Lowercase, strip diacritics, normalize bangla digits, collapse whitespace."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = t.translate(_BANGLA_DIGITS)
    t = t.lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def canonicalize(text: str) -> set[str]:
    """Return the set of canonical intent tags present in the text."""
    n = normalize(text)
    found = set()
    for phrase, tag in _CANONICAL_PHRASES.items():
        if phrase in n:
            found.add(tag)
    return found