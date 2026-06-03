from __future__ import annotations

from collections import Counter
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QTextEdit, QVBoxLayout, QWidget

from mailscan2026.core import priority


DASHBOARD_CARDS = [
    "Documents",
    "Urgent",
    "Due Soon",
    "Needs Review",
    "Payable Bills",
    "Payable Total",
    "Next Due",
    "Info Mail",
    "Reviewed",
    "Ignored",
]


def install_dashboard_ui(main_window_cls) -> None:
    """Replace placeholder dashboard with practical cards and robust metric updates."""

    def dashboard_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.dashboard_metric_labels = {}

        grid = QGridLayout()
        for index, label in enumerate(DASHBOARD_CARDS):
            box = QGroupBox(label)
            box_layout = QVBoxLayout(box)
            value = QLabel("—")
            value.setObjectName("MetricValue")
            value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            box_layout.addWidget(value)
            self.dashboard_metric_labels[label] = value
            grid.addWidget(box, index // 5, index % 5)
        layout.addLayout(grid)

        self.dashboard_summary_text = QTextEdit()
        self.dashboard_summary_text.setReadOnly(True)
        self.dashboard_summary_text.setPlaceholderText("Click Identify Mail or load a session to populate the dashboard.")
        layout.addWidget(QLabel("Review Summary"))
        layout.addWidget(self.dashboard_summary_text, stretch=1)
        return w

    def update_dashboard_metrics(self):
        if not hasattr(self, "table"):
            return
        stats = calculate_dashboard_stats(self)
        labels = getattr(self, "dashboard_metric_labels", {})
        values = {
            "Documents": str(stats["documents"]),
            "Urgent": str(stats["urgent"]),
            "Due Soon": str(stats["due_soon"]),
            "Needs Review": str(stats["needs_review"]),
            "Payable Bills": str(stats["payable_bills"]),
            "Payable Total": f"${stats['payable_total']:,.2f}" if stats["payable_bills"] else "—",
            "Next Due": stats["next_due"] or "—",
            "Info Mail": str(stats["info"]),
            "Reviewed": str(stats["reviewed"]),
            "Ignored": str(stats["ignored"]),
        }
        for label, value in values.items():
            if label in labels:
                labels[label].setText(value)

        summary = dashboard_summary(stats)
        if hasattr(self, "dashboard_summary_text"):
            self.dashboard_summary_text.setPlainText(summary)
        if hasattr(self, "update_classify_button_state"):
            self.update_classify_button_state()

    main_window_cls._dashboard_tab = dashboard_tab
    main_window_cls.update_dashboard_metrics = update_dashboard_metrics


def calculate_dashboard_stats(window) -> dict[str, object]:
    header_map = table_header_map(window)
    today = date.today()
    priorities = Counter()
    categories = Counter()
    senders = Counter()
    due_candidates: list[date] = []
    payable_total = 0.0
    payable_bills = 0
    needs_review = 0
    reviewed = 0
    ignored = 0

    for row in range(window.table.rowCount()):
        row_data = {header: cell_text(window, header_map, row, header) for header in header_map}
        label = row_data.get("Priority") or priority.compute_priority(row_data).label
        priorities[label] += 1
        categories[row_data.get("Category", "Unsorted") or "Unsorted"] += 1
        sender = row_data.get("Sender", "").strip()
        if sender:
            senders[sender] += 1

        status = row_data.get("Status", "").lower().strip()
        if status == "reviewed" or label == "Reviewed":
            reviewed += 1
        if status == "ignored" or label == "Ignored":
            ignored += 1
        if row_data.get("Needs Review", "").lower().strip() in {"yes", "true", "1"} or label == "Review":
            needs_review += 1

        doc_type = row_data.get("Type", "").lower()
        amount = priority.parse_amount(row_data.get("Amount", ""))
        if "bill / payable" in doc_type and amount is not None:
            payable_bills += 1
            payable_total += amount
            due = priority.parse_due_date(row_data.get("Due Date", ""))
            if due:
                due_candidates.append(due)

    next_due_date = min(due_candidates) if due_candidates else None
    return {
        "documents": window.table.rowCount(),
        "urgent": priorities.get("Urgent", 0),
        "due_soon": priorities.get("Due Soon", 0),
        "needs_review": needs_review,
        "payable_bills": payable_bills,
        "payable_total": payable_total,
        "next_due": next_due_date.strftime("%m/%d/%Y") if next_due_date else "",
        "info": priorities.get("Info", 0),
        "reviewed": reviewed,
        "ignored": ignored,
        "top_categories": categories.most_common(5),
        "top_senders": senders.most_common(5),
    }


def dashboard_summary(stats: dict[str, object]) -> str:
    next_action = "Load or import OCR PDFs, then click Identify Mail."
    if stats["urgent"]:
        next_action = "Review urgent items first."
    elif stats["due_soon"]:
        next_action = "Review due-soon items next."
    elif stats["needs_review"]:
        next_action = "Work through Needs Review rows."
    elif stats["documents"]:
        next_action = "Export finance files or continue reviewing remaining rows."

    lines = [
        "Dashboard Summary",
        "=================",
        f"Next action: {next_action}",
        "",
        f"Documents: {stats['documents']}",
        f"Payable bills: {stats['payable_bills']}",
        f"Payable total: ${stats['payable_total']:,.2f}",
        f"Next due: {stats['next_due'] or '—'}",
        "",
        "Top categories:",
    ]
    for name, count in stats.get("top_categories", []):
        lines.append(f"- {name}: {count}")
    lines.append("")
    lines.append("Top senders:")
    for name, count in stats.get("top_senders", []):
        lines.append(f"- {name}: {count}")
    return "\n".join(lines)


def table_header_map(window) -> dict[str, int]:
    mapping = {}
    for col in range(window.table.columnCount()):
        item = window.table.horizontalHeaderItem(col)
        if item:
            mapping[item.text()] = col
    return mapping


def cell_text(window, header_map: dict[str, int], row: int, header: str) -> str:
    if header not in header_map:
        return ""
    item = window.table.item(row, header_map[header])
    return item.text().strip() if item else ""
