from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from mailscan2026.core import priority


@dataclass(frozen=True)
class BalanceFinding:
    sender: str
    status: str
    reason: str
    current_row: int
    related_rows: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class AttentionSummary:
    document_count: int
    bills_found: int
    payable_total: float
    urgent_count: int
    due_soon_count: int
    review_count: int
    info_count: int
    reviewed_count: int
    ignored_count: int
    possible_updates: list[BalanceFinding]
    possible_duplicates: list[BalanceFinding]
    unclear_senders: int
    top_senders: list[tuple[str, int]]


def summarize_rows(rows: list[dict[str, str]]) -> AttentionSummary:
    priorities = Counter()
    senders = Counter()
    bills_found = 0
    payable_total = 0.0
    unclear_senders = 0

    for row in rows:
        label = str(row.get("Priority", "")).strip() or priority.compute_priority(row).label
        priorities[label] += 1
        sender = str(row.get("Sender", "")).strip()
        if sender:
            senders[sender] += 1
        else:
            unclear_senders += 1
        doc_type = str(row.get("Type", "")).lower()
        amount = priority.parse_amount(str(row.get("Amount", "")))
        if "bill / payable" in doc_type and amount is not None:
            bills_found += 1
            payable_total += amount

    duplicates, updates = detect_balance_warnings(rows)
    return AttentionSummary(
        document_count=len(rows),
        bills_found=bills_found,
        payable_total=payable_total,
        urgent_count=priorities.get("Urgent", 0),
        due_soon_count=priorities.get("Due Soon", 0),
        review_count=priorities.get("Review", 0),
        info_count=priorities.get("Info", 0),
        reviewed_count=priorities.get("Reviewed", 0),
        ignored_count=priorities.get("Ignored", 0),
        possible_updates=updates,
        possible_duplicates=duplicates,
        unclear_senders=unclear_senders,
        top_senders=senders.most_common(5),
    )


def detect_balance_warnings(rows: list[dict[str, str]]) -> tuple[list[BalanceFinding], list[BalanceFinding]]:
    groups: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for index, row in enumerate(rows):
        sender = normalize_sender(str(row.get("Sender", "")))
        doc_type = str(row.get("Type", "")).lower()
        amount = priority.parse_amount(str(row.get("Amount", "")))
        if not sender or amount is None or "bill / payable" not in doc_type:
            continue
        groups[sender].append((index, row))

    duplicates: list[BalanceFinding] = []
    updates: list[BalanceFinding] = []
    for _sender_key, items in groups.items():
        if len(items) < 2:
            continue
        items_sorted = sorted(items, key=lambda pair: sort_date(pair[1]))
        latest_index, latest_row = items_sorted[-1]
        latest_amount = priority.parse_amount(str(latest_row.get("Amount", ""))) or 0.0
        sender = str(latest_row.get("Sender", "")).strip() or "Unknown sender"
        same_amount_rows: list[int] = []
        lower_amount_rows: list[int] = []
        for row_index, row in items_sorted[:-1]:
            amount = priority.parse_amount(str(row.get("Amount", ""))) or 0.0
            if abs(amount - latest_amount) < 0.01:
                same_amount_rows.append(row_index)
            elif amount < latest_amount:
                lower_amount_rows.append(row_index)

        if same_amount_rows:
            duplicates.append(BalanceFinding(sender, "Possible Duplicate", "Same sender and same payable amount appears more than once.", latest_index, same_amount_rows))
        if lower_amount_rows:
            updates.append(BalanceFinding(sender, "Possible Updated Balance", "Newer bill from same sender has a higher balance; review before adding amounts together.", latest_index, lower_amount_rows))
    return duplicates, updates


def sort_date(row: dict[str, str]) -> tuple[int, str]:
    due = priority.parse_due_date(str(row.get("Due Date", "")))
    if due:
        return (1, due.isoformat())
    source = str(row.get("Source PDF", ""))
    try:
        mtime = Path(source).stat().st_mtime if source else 0
    except Exception:
        mtime = 0
    return (0, str(mtime))


def normalize_sender(value: str) -> str:
    clean = " ".join(value.lower().split())
    for token in [" llc", " inc", " company", " co.", " co"]:
        clean = clean.replace(token, "")
    return clean.strip()


def render_home_summary(summary: AttentionSummary) -> str:
    lines = [
        "MailScan Home",
        "=============",
        "",
        f"Documents imported: {summary.document_count}",
        f"Bills found: {summary.bills_found}",
        f"Current payable total: ${summary.payable_total:,.2f}",
        f"Due soon: {summary.due_soon_count}",
        f"Urgent: {summary.urgent_count}",
        f"Needs review: {summary.review_count}",
        f"Possible duplicates: {len(summary.possible_duplicates)}",
        f"Possible updated balances: {len(summary.possible_updates)}",
        f"Unclear senders: {summary.unclear_senders}",
        "",
        f"Next step: {next_step(summary)}",
    ]
    if summary.possible_updates or summary.possible_duplicates:
        lines.extend(["", "Balance warnings:"])
        for finding in summary.possible_updates[:5] + summary.possible_duplicates[:5]:
            related = ", ".join(str(r + 1) for r in finding.related_rows)
            lines.append(f"- {finding.status}: {finding.sender}, row {finding.current_row + 1}, related row(s): {related}. {finding.reason}")
    if summary.top_senders:
        lines.extend(["", "Top senders:"])
        for sender, count in summary.top_senders:
            lines.append(f"- {sender}: {count}")
    return "\n".join(lines)


def next_step(summary: AttentionSummary) -> str:
    if summary.document_count == 0:
        return "Import OCR PDFs or load a saved session."
    if summary.possible_updates or summary.possible_duplicates:
        return "Review balance warnings before exporting."
    if summary.urgent_count:
        return "Review urgent mail first."
    if summary.review_count:
        return "Review attention items."
    if summary.bills_found:
        return "Export results or review payable bills."
    return "No urgent action found; review informational mail if needed."
