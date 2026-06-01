from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Classification:
    category: str
    sender: str
    doc_type: str
    amount: str
    due_date: str
    confidence: str
    needs_review: str
    notes: str
    is_bill: bool


BILL_WORDS = [
    "amount due", "balance due", "payment due", "due date", "minimum payment",
    "statement balance", "total due", "please pay", "invoice", "bill", "autopay",
]

INFO_WORDS = [
    "we missed you", "redelivery", "tracking", "article number", "final notice",
    "delivery notice", "certified mail", "return receipt", "notice/reminder/receipt",
]


def classify_document(pdf: Path, text: str, summary_doc_type: str = "") -> Classification:
    lower = text.lower()
    name = pdf.name.lower()

    is_usps = _has_any(lower, ["usps tracking", "ps form 3849", "we missed you", "redelivery"]) or "usps" in name
    bill_score = sum(1 for word in BILL_WORDS if word in lower)
    info_score = sum(1 for word in INFO_WORDS if word in lower)
    amounts = find_amounts(text)
    dates = find_dates(text)

    if is_usps:
        return Classification(
            category="Mail",
            sender="United States Postal Service",
            doc_type="USPS Notice / Certified Mail Notice",
            amount="",
            due_date=_first(dates),
            confidence="Fair",
            needs_review="Yes",
            notes="Informational notice. Tracking/article numbers may be present.",
            is_bill=False,
        )

    if bill_score >= 2 or (bill_score >= 1 and amounts):
        return Classification(
            category=_guess_category_from_path(pdf, default="Bills"),
            sender=guess_sender(text, pdf),
            doc_type="Bill / Statement",
            amount=_first(amounts),
            due_date=_first(dates),
            confidence="Fair" if amounts or dates else "Low",
            needs_review="Yes",
            notes="Bill-like language detected. Review amount and due date before relying on it.",
            is_bill=True,
        )

    if info_score >= 1 or summary_doc_type not in ("", "Unknown", "Bill / Statement"):
        return Classification(
            category=_guess_category_from_path(pdf, default="Info"),
            sender=guess_sender(text, pdf),
            doc_type=summary_doc_type if summary_doc_type and summary_doc_type != "Unknown" else "Informational / Notice",
            amount="",
            due_date=_first(dates),
            confidence="Fair",
            needs_review="Yes",
            notes="Informational document. No payable amount detected.",
            is_bill=False,
        )

    return Classification(
        category=_guess_category_from_path(pdf, default="Unsorted"),
        sender=guess_sender(text, pdf),
        doc_type="Unknown",
        amount="",
        due_date=_first(dates),
        confidence="Low",
        needs_review="Yes",
        notes="Could not confidently classify as bill or informational.",
        is_bill=False,
    )


def find_amounts(text: str) -> list[str]:
    return unique_limited(re.findall(r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?", text), 8)


def find_dates(text: str) -> list[str]:
    patterns = [
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}/\d{1,2}/\d{2,4}\b",
    ]
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return unique_limited(matches, 8)


def guess_sender(text: str, pdf: Path) -> str:
    lower = text.lower()
    if "united states postal" in lower or "usps" in lower or "ps form 3849" in lower:
        return "United States Postal Service"

    for line in text.splitlines()[:30]:
        clean = " ".join(line.strip().split())
        if not clean or len(clean) < 3:
            continue
        if clean.lower() in {"today's date", "sender's name", "date", "time"}:
            continue
        if re.search(r"[A-Za-z]", clean) and not re.search(r"\d{5}", clean):
            return clean[:80]

    stem = pdf.stem.replace("_OCR", "").replace("-OCR", "")
    return stem.replace("_", " ").replace("-", " ").strip().title()


def _guess_category_from_path(pdf: Path, default: str) -> str:
    known = {"Bills", "Medical", "Car", "Mail", "Misc", "Taxes"}
    for part in reversed(pdf.parts):
        if part in known:
            return part
    return default


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _first(values: list[str]) -> str:
    return values[0] if values else ""


def unique_limited(values: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        clean = " ".join(str(value).split())
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            output.append(clean)
        if len(output) >= limit:
            break
    return output
