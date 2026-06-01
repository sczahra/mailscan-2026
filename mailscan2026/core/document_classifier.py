from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from mailscan2026.core import vendor_store


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


PAYABLE_WORDS = [
    "amount due", "balance due", "payment due", "minimum payment", "total due",
    "please pay", "pay this amount", "new charges", "autopay", "invoice due",
    "past due", "payment is due", "pay by", "remit payment",
]

STATEMENT_WORDS = [
    "statement", "statement date", "account summary", "previous balance", "transactions",
]

INFO_WORDS = [
    "we missed you", "redelivery", "tracking", "article number", "final notice",
    "delivery notice", "certified mail", "return receipt", "notice/reminder/receipt",
    "important information", "member appeal", "explanation of benefits",
]

BAD_SENDER_PHRASES = [
    "help in your language", "quote", "page ", "member appeal", "may,", "virginian",
    "today's date", "sender's name", "amount due", "delivery section", "notice left",
    "important information", "see reverse", "for redelivery", "fee", "ition",
    "if we do not have your information", "following has changed", "customer name",
    "patient information", "guarantor name", "look for important dates",
]


def classify_document(pdf: Path, text: str, summary_doc_type: str = "") -> Classification:
    lower = text.lower()
    name = pdf.name.lower()
    category = _guess_category_from_path(pdf, default="Unsorted")
    sender, sender_note = guess_sender_with_note(text, pdf)
    amounts = find_amounts(text)
    dates = find_dates(text)

    is_usps = _has_any(lower, ["usps tracking", "ps form 3849", "we missed you", "redelivery"]) or "usps" in name
    payable_score = sum(1 for word in PAYABLE_WORDS if word in lower)
    statement_score = sum(1 for word in STATEMENT_WORDS if word in lower)
    info_score = sum(1 for word in INFO_WORDS if word in lower)

    if is_usps:
        return Classification(
            category="Mail",
            sender="United States Postal Service",
            doc_type="Informational / Notice",
            amount="",
            due_date=_first(dates),
            confidence="Fair",
            needs_review="Yes",
            notes="USPS notice. Tracking/article numbers may be present. No payable amount detected.",
            is_bill=False,
        )

    is_medical_folder = category.lower() == "medical"

    if is_medical_folder:
        if payable_score >= 1 and amounts:
            return Classification(
                category="Medical",
                sender=sender,
                doc_type="Medical / Possible Payable",
                amount=_first(amounts),
                due_date=_first(dates),
                confidence="Low",
                needs_review="Yes",
                notes=_join_notes("Medical folder with amount and possible payment language. Review before counting as payable.", sender_note),
                is_bill=False,
            )
        return Classification(
            category="Medical",
            sender=sender,
            doc_type="Medical / Insurance Statement",
            amount="",
            due_date=_first(dates),
            confidence="Low" if sender_note.startswith("Needs") else "Fair",
            needs_review="Yes",
            notes=_join_notes("Medical/insurance document. Not treated as payable unless payment language is clear.", sender_note),
            is_bill=False,
        )

    if payable_score >= 1 and amounts:
        return Classification(
            category=category if category != "Unsorted" else "Bills",
            sender=sender,
            doc_type="Bill / Payable",
            amount=_first(amounts),
            due_date=_first(dates),
            confidence="Fair",
            needs_review="Yes",
            notes=_join_notes("Payable language and amount detected. Review amount and due date before relying on it.", sender_note),
            is_bill=True,
        )

    if statement_score >= 1 and amounts:
        return Classification(
            category=category if category != "Unsorted" else "Bills",
            sender=sender,
            doc_type="Statement / Possible Balance",
            amount="",
            due_date=_first(dates),
            confidence="Low",
            needs_review="Yes",
            notes=_join_notes("Amount found, but payable context is unclear. Not included in total by default.", sender_note),
            is_bill=False,
        )

    if info_score >= 1 or summary_doc_type not in ("", "Unknown", "Bill / Statement"):
        return Classification(
            category=category if category != "Unsorted" else "Info",
            sender=sender,
            doc_type=summary_doc_type if summary_doc_type and summary_doc_type != "Unknown" else "Informational / Notice",
            amount="",
            due_date=_first(dates),
            confidence="Low" if sender_note.startswith("Needs") else "Fair",
            needs_review="Yes",
            notes=_join_notes("Informational document. No payable amount detected.", sender_note),
            is_bill=False,
        )

    return Classification(
        category=category,
        sender=sender,
        doc_type="Unknown / Needs Review",
        amount="",
        due_date=_first(dates),
        confidence="Low",
        needs_review="Yes",
        notes=_join_notes("Could not confidently classify as payable bill or informational notice.", sender_note),
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
    sender, _note = guess_sender_with_note(text, pdf)
    return sender


def guess_sender_with_note(text: str, pdf: Path) -> tuple[str, str]:
    vendor = vendor_store.match_vendor(text, pdf=pdf, strong_only=True)
    if vendor:
        return vendor.name, f"Sender matched vendor database ({vendor.source})."

    lines = [clean_sender_line(line) for line in text.splitlines()[:55]]
    lines = [line for line in lines if line]

    for line in lines[:35]:
        if is_bad_sender(line):
            continue
        if re.search(r"[A-Za-z]", line) and not re.search(r"\d{5}", line):
            return line[:80], "Needs manual sender review. Sender guessed from OCR line."

    filename_vendor = vendor_store.match_vendor("", pdf=pdf, strong_only=True)
    if filename_vendor:
        return filename_vendor.name, f"Sender inferred from filename/path vendor hint ({filename_vendor.source})."

    stem = pdf.stem.replace("_OCR", "").replace("-OCR", "")
    fallback = stem.replace("_", " ").replace("-", " ").strip().title()
    if fallback:
        return fallback, "Needs manual sender review. Sender guessed from filename."
    return "", "Needs manual sender review."


def clean_sender_line(line: str) -> str:
    value = " ".join(line.strip().split())
    value = value.replace("©", "").replace("®", "").strip()
    value = re.sub(r"^[^A-Za-z0-9]+", "", value)
    value = re.sub(r"[^A-Za-z0-9 '&.,/-]+$", "", value)
    return value.strip()


def is_bad_sender(sender: str) -> bool:
    value = sender.strip()
    lower = value.lower()
    if len(value) < 4:
        return True
    if len(value) > 55:
        return True
    if re.search(r"[{}|_\[\]]", value):
        return True
    if re.search(r"^[a-zA-Z]$", value):
        return True
    if re.search(r"^page\s+\d+", lower):
        return True
    if re.search(r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*,?\s+\d{4}$", lower):
        return True
    if re.search(r"[a-zA-Z]*\d[a-zA-Z0-9-]*\d", value) and len(value.split()) <= 3:
        return True
    if lower in {"fee", "ition", "date", "time", "amount", "total", "farmville", "patient information", "guarantor name"}:
        return True
    return any(phrase in lower for phrase in BAD_SENDER_PHRASES)


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


def _join_notes(*notes: str) -> str:
    return " ".join(note for note in notes if note).strip()


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
