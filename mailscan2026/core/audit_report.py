from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from mailscan2026.core import document_classifier, session_store


HEADERS = [
    "Status", "Category", "Sender", "Type", "Amount", "Due Date",
    "Confidence", "Needs Review", "Source PDF", "Notes", "Review Flags"
]


@dataclass(frozen=True)
class AuditSummary:
    total_rows: int
    flagged_rows: int
    positive_amount_rows: int
    total_amount: float
    report_path: Path


def audit_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    audited: list[dict[str, str]] = []
    for row in rows:
        clean = {header: str(row.get(header, "")) for header in HEADERS}
        flags = build_flags(clean)
        clean["Review Flags"] = "; ".join(flags)
        audited.append(clean)
    return audited


def build_flags(row: dict[str, str]) -> list[str]:
    flags: list[str] = []
    sender = row.get("Sender", "").strip()
    doc_type = row.get("Type", "").strip()
    notes = row.get("Notes", "").strip()
    amount = row.get("Amount", "").strip()
    due = row.get("Due Date", "").strip()
    source = row.get("Source PDF", "").strip()

    if source and not Path(source).exists():
        flags.append("Missing source PDF")

    if not sender:
        flags.append("Blank sender")
    elif is_bad_sender(sender):
        flags.append("Likely wrong sender")

    if "normalized from ocr" in notes.lower():
        flags.append("Sender normalized from OCR")

    amount_value = parse_amount(amount)
    type_lower = doc_type.lower()
    notes_lower = notes.lower()

    if "bill / payable" in type_lower and amount_value is None:
        flags.append("Payable bill without amount")

    if any(label in type_lower for label in ["statement / possible balance", "medical / insurance statement"]):
        if amount_value is not None and "payable" not in notes_lower:
            flags.append("Amount found but payable context unclear")

    if ("bill" in type_lower or "statement" in type_lower) and amount_value is None and "informational" not in type_lower:
        flags.append("Bill/Statement without payable amount")

    info_like = any(word in f"{doc_type} {notes}".lower() for word in ["informational", "notice", "usps", "no payable"])
    if info_like and amount in ("$0.00", "0", "0.00"):
        flags.append("Info doc showing zero amount")

    if re.search(r"\b20(?:28|29|3\d)\b", due):
        flags.append("Suspicious future due/date")

    if not doc_type:
        flags.append("Blank type")

    confidence = row.get("Confidence", "").lower().strip()
    if confidence in ("", "low"):
        flags.append("Low confidence")

    return unique_flags(flags)


def is_bad_sender(sender: str) -> bool:
    return document_classifier.is_bad_sender(sender)


def parse_amount(text: str) -> float | None:
    cleaned = text.strip().replace("$", "").replace(",", "")
    if cleaned in ("", "—", "-", "0", "0.00"):
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def unique_flags(flags: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for flag in flags:
        if flag not in seen:
            output.append(flag)
            seen.add(flag)
    return output


def export_audit_csv(rows: list[dict[str, str]]) -> AuditSummary:
    audited = audit_rows(rows)
    session_store.ensure_app_data_dir()
    report_path = session_store.app_data_dir() / "review_session_audit.csv"

    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(audited)

    total_amount = 0.0
    positive_amount_rows = 0
    flagged_rows = 0
    for row in audited:
        if row.get("Review Flags", ""):
            flagged_rows += 1
        amount = parse_amount(row.get("Amount", ""))
        if amount is not None and "bill / payable" in row.get("Type", "").lower():
            positive_amount_rows += 1
            total_amount += amount

    return AuditSummary(
        total_rows=len(audited),
        flagged_rows=flagged_rows,
        positive_amount_rows=positive_amount_rows,
        total_amount=total_amount,
        report_path=report_path,
    )
