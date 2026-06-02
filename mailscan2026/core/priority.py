from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta


PRIORITY_HEADER = "Priority"


@dataclass(frozen=True)
class PriorityResult:
    label: str
    color_name: str
    reason: str


COLOR_HEX = {
    "red": "#ffd6d6",
    "orange": "#ffe4c4",
    "yellow": "#fff7bf",
    "blue": "#dcebff",
    "green": "#d8f5d0",
    "gray": "#eeeeee",
    "none": "#ffffff",
}


def compute_priority(row: dict[str, str], due_soon_days: int = 7, today: date | None = None) -> PriorityResult:
    today = today or date.today()
    status = row.get("Status", "").strip().lower()
    doc_type = row.get("Type", "").strip().lower()
    amount = row.get("Amount", "").strip()
    due_text = row.get("Due Date", "").strip()
    confidence = row.get("Confidence", "").strip().lower()
    flags = row.get("Review Flags", "").strip().lower()
    notes = row.get("Notes", "").strip().lower()

    if status in {"reviewed", "done", "complete"}:
        return PriorityResult("Reviewed", "green", "Marked reviewed")
    if status in {"ignored", "archive", "archived", "duplicate"}:
        return PriorityResult("Ignored", "gray", "Marked ignored/archive")

    due = parse_due_date(due_text)
    payable = "bill / payable" in doc_type and parse_amount(amount) is not None
    urgent_words = any(word in f"{doc_type} {notes} {flags}" for word in ["past due", "final notice", "urgent", "returned", "late fee"])

    if payable and due and due < today:
        return PriorityResult("Urgent", "red", "Payable item is past due")
    if payable and urgent_words:
        return PriorityResult("Urgent", "red", "Urgent/final-notice language detected")
    if payable and not due:
        return PriorityResult("Urgent", "red", "Payable amount found but due date is missing")

    if payable and due <= today + timedelta(days=due_soon_days):
        return PriorityResult("Due Soon", "orange", f"Payable item due within {due_soon_days} days")
    if "medical / possible payable" in doc_type:
        return PriorityResult("Due Soon", "orange", "Medical possible payable needs manual review")
    if "statement / possible balance" in doc_type:
        return PriorityResult("Due Soon", "orange", "Possible balance not counted as payable")

    if flags or confidence in {"", "low"} or "unknown" in doc_type or "manual sender review" in notes:
        return PriorityResult("Review", "yellow", "Low confidence, unknown, or flagged row")

    if "informational" in doc_type or "notice" in doc_type or "no payable" in notes:
        return PriorityResult("Info", "blue", "Informational or non-payable notice")

    if payable:
        return PriorityResult("Payable", "orange", "Payable item")

    return PriorityResult("Review", "yellow", "Needs review")


def parse_amount(text: str) -> float | None:
    cleaned = text.strip().replace("$", "").replace(",", "")
    if cleaned in ("", "—", "-", "0", "0.00"):
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def parse_due_date(text: str) -> date | None:
    value = text.strip()
    if not value:
        return None
    value = re.sub(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+", "", value, flags=re.IGNORECASE)
    for fmt in ["%m/%d/%Y", "%m/%d/%y"]:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None
