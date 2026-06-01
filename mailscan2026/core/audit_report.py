from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from mailscan2026.core import session_store


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

    amount_value = parse_amount(amount)
    if ("bill" in doc_type.lower() or "statement" in doc_type.lower()) and amount_value is None:
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

    return flags


def is_bad_sender(sender: str) -> bool:
    value = sender.strip()
    lower = value.lower()
    if len(value) < 3:
        return True
    if re.search(r"[{}|_\[\]©®]", value):
        return True
    if re.search(r"^[a-zA-Z]$", value):
        return True
    bad_phrases = [
        "help in your language", "quote", "page ", "member appeal", "may,", "virginian",
        "today's date", "sender's name", "amount due", "delivery section", "notice left",
        "important information", "see reverse", "for redelivery",
    ]
    return any(phrase in lower for phrase in bad_phrases)


def parse_amount(text: str) -> float | None:
    cleaned = text.strip().replace("$", "").replace(",", "")
    if cleaned in ("", "—", "-", "0", "0.00"):
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


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
        if amount is not None:
            positive_amount_rows += 1
            total_amount += amount

    return AuditSummary(
        total_rows=len(audited),
        flagged_rows=flagged_rows,
        positive_amount_rows=positive_amount_rows,
        total_amount=total_amount,
        report_path=report_path,
    )
