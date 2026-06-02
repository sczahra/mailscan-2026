from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QTableWidgetItem


FILTERS = ["All", "Urgent", "Due Soon", "Review", "Payable", "Info", "Reviewed", "Ignored"]
SELECTION_HIGHLIGHT = QColor("#111111")
SELECTION_TEXT = QColor("#ffffff")


def install_review_mode(main_window_cls, headers: list[str]) -> None:
    """Add simple next-item navigation and table filters for review workflow."""
    original_documents_tab = main_window_cls._documents_tab

    def documents_tab_with_review_mode(self):
        widget = original_documents_tab(self)

        self.next_urgent_button = QPushButton("Next Urgent")
        self.next_urgent_button.clicked.connect(lambda: self.jump_to_next_priority("Urgent"))

        self.next_review_button = QPushButton("Next Review")
        self.next_review_button.clicked.connect(lambda: self.jump_to_next_priority("Review"))

        self.next_payable_button = QPushButton("Next Payable")
        self.next_payable_button.clicked.connect(self.jump_to_next_payable)

        self.next_due_soon_button = QPushButton("Next Due Soon")
        self.next_due_soon_button.clicked.connect(lambda: self.jump_to_next_priority("Due Soon"))

        nav_row = QHBoxLayout()
        nav_row.addWidget(self.next_urgent_button)
        nav_row.addWidget(self.next_review_button)
        nav_row.addWidget(self.next_payable_button)
        nav_row.addWidget(self.next_due_soon_button)
        nav_row.addStretch()
        widget.layout().insertLayout(1, nav_row)

        filter_row = QHBoxLayout()
        self.filter_buttons = {}
        for name in FILTERS:
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, filter_name=name: self.apply_table_filter(filter_name))
            self.filter_buttons[name] = button
            filter_row.addWidget(button)
        filter_row.addStretch()
        widget.layout().insertLayout(2, filter_row)
        self.set_filter_button_checked("All")

        self.current_review_row = -1
        self.table.itemSelectionChanged.connect(self.update_selected_row_highlight)
        self.install_selection_table_style()
        return widget

    def install_selection_table_style(self) -> None:
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.SingleSelection)
        self.table.setStyleSheet(
            self.table.styleSheet()
            + """
            QTableWidget::item:selected {
                background: #111111;
                color: #ffffff;
                border-top: 2px solid #000000;
                border-bottom: 2px solid #000000;
            }
            QTableWidget::item:focus {
                border: 2px solid #000000;
            }
            """
        )

    def update_selected_row_highlight(self) -> None:
        row = self.table.currentRow()
        if getattr(self, "current_review_row", -1) == row:
            return
        previous = getattr(self, "current_review_row", -1)
        self.current_review_row = row
        if previous >= 0 and previous < self.table.rowCount() and hasattr(self, "apply_priority_for_row"):
            self.apply_priority_for_row(previous)
        if row >= 0:
            self.emphasize_selected_row(row)
            self.update_selected_row_label(row)

    def emphasize_selected_row(self, row: int) -> None:
        if row < 0 or row >= self.table.rowCount():
            return
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item is None:
                item = QTableWidgetItem("")
                self.table.setItem(row, col, item)
            item.setBackground(SELECTION_HIGHLIGHT)
            item.setForeground(SELECTION_TEXT)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        self.table.viewport().update()

    def update_selected_row_label(self, row: int) -> None:
        sender = cell_text(self, row, "Sender") or "Unknown sender"
        priority = cell_text(self, row, "Priority") or "No priority"
        doc_type = cell_text(self, row, "Type") or "Unknown type"
        amount = cell_text(self, row, "Amount") or "—"
        due = cell_text(self, row, "Due Date") or "—"
        self.log(f"Selected row {row + 1}: {priority} | {sender} | {doc_type} | Amount {amount} | Due {due}")

    def set_filter_button_checked(self, name: str) -> None:
        for filter_name, button in getattr(self, "filter_buttons", {}).items():
            button.blockSignals(True)
            button.setChecked(filter_name == name)
            button.blockSignals(False)

    def apply_table_filter(self, filter_name: str) -> None:
        self.set_filter_button_checked(filter_name)
        for row in range(self.table.rowCount()):
            show = row_matches_filter(self, row, filter_name)
            self.table.setRowHidden(row, not show)
        self.log(f"Applied table filter: {filter_name}")
        visible = sum(1 for row in range(self.table.rowCount()) if not self.table.isRowHidden(row))
        self.text_preview.setPlainText(review_status_summary(self, filter_name, visible))
        row = self.table.currentRow()
        if row >= 0 and self.table.isRowHidden(row):
            next_row = find_next_row(self, lambda r: not self.table.isRowHidden(r))
            if next_row is not None:
                select_and_preview(self, next_row)
        else:
            self.update_selected_row_highlight()

    def clear_table_filter(self) -> None:
        self.apply_table_filter("All")

    def jump_to_next_priority(self, priority_name: str) -> None:
        row = find_next_row(self, lambda r: cell_text(self, r, "Priority") == priority_name)
        if row is None:
            QMessageBox.information(self, "No matching rows", f"No visible or available rows match: {priority_name}")
            return
        select_and_preview(self, row)

    def jump_to_next_payable(self) -> None:
        row = find_next_row(self, lambda r: "bill / payable" in cell_text(self, r, "Type").lower())
        if row is None:
            QMessageBox.information(self, "No payable rows", "No visible or available payable rows found.")
            return
        select_and_preview(self, row)

    original_mark_reviewed = getattr(main_window_cls, "mark_selected_reviewed", None)
    original_mark_ignored = getattr(main_window_cls, "mark_selected_ignored", None)

    def mark_selected_reviewed_and_advance(self):
        row_before = self.table.currentRow()
        if original_mark_reviewed is not None:
            original_mark_reviewed(self)
        else:
            set_cell_text(self, row_before, "Status", "Reviewed")
        if row_before >= 0 and hasattr(self, "apply_priority_for_row"):
            self.apply_priority_for_row(row_before)
        self.jump_to_next_priority("Review")

    def mark_selected_ignored_and_advance(self):
        row_before = self.table.currentRow()
        if original_mark_ignored is not None:
            original_mark_ignored(self)
        else:
            set_cell_text(self, row_before, "Status", "Ignored")
        if row_before >= 0 and hasattr(self, "apply_priority_for_row"):
            self.apply_priority_for_row(row_before)
        self.jump_to_next_priority("Review")

    main_window_cls._documents_tab = documents_tab_with_review_mode
    main_window_cls.install_selection_table_style = install_selection_table_style
    main_window_cls.update_selected_row_highlight = update_selected_row_highlight
    main_window_cls.emphasize_selected_row = emphasize_selected_row
    main_window_cls.update_selected_row_label = update_selected_row_label
    main_window_cls.set_filter_button_checked = set_filter_button_checked
    main_window_cls.apply_table_filter = apply_table_filter
    main_window_cls.clear_table_filter = clear_table_filter
    main_window_cls.jump_to_next_priority = jump_to_next_priority
    main_window_cls.jump_to_next_payable = jump_to_next_payable
    main_window_cls.mark_selected_reviewed = mark_selected_reviewed_and_advance
    main_window_cls.mark_selected_ignored = mark_selected_ignored_and_advance


def header_map(window) -> dict[str, int]:
    output = {}
    for col in range(window.table.columnCount()):
        item = window.table.horizontalHeaderItem(col)
        if item:
            output[item.text()] = col
    return output


def cell_text(window, row: int, header: str) -> str:
    mapping = header_map(window)
    if row < 0 or header not in mapping:
        return ""
    item = window.table.item(row, mapping[header])
    return item.text().strip() if item else ""


def set_cell_text(window, row: int, header: str, value: str) -> None:
    mapping = header_map(window)
    if row < 0 or header not in mapping:
        return
    window.table.setItem(row, mapping[header], QTableWidgetItem(value))


def row_matches_filter(window, row: int, filter_name: str) -> bool:
    if filter_name == "All":
        return True
    priority = cell_text(window, row, "Priority")
    status = cell_text(window, row, "Status").lower()
    doc_type = cell_text(window, row, "Type").lower()
    if filter_name in {"Urgent", "Due Soon", "Review", "Info", "Reviewed", "Ignored"}:
        if filter_name in {"Reviewed", "Ignored"}:
            return status == filter_name.lower() or priority == filter_name
        return priority == filter_name
    if filter_name == "Payable":
        return "bill / payable" in doc_type
    return True


def find_next_row(window, predicate) -> int | None:
    total = window.table.rowCount()
    if total <= 0:
        return None
    start = window.table.currentRow()
    if start < 0:
        start = -1
    for offset in range(1, total + 1):
        row = (start + offset) % total
        if window.table.isRowHidden(row):
            continue
        if predicate(row):
            return row
    for offset in range(1, total + 1):
        row = (start + offset) % total
        if predicate(row):
            return row
    return None


def select_and_preview(window, row: int) -> None:
    window.table.setRowHidden(row, False)
    window.table.selectRow(row)
    window.table.setCurrentCell(row, 0)
    window.table.scrollToItem(window.table.item(row, 0))
    if hasattr(window, "emphasize_selected_row"):
        window.emphasize_selected_row(row)
    if hasattr(window, "extract_selected_pdf_text"):
        window.extract_selected_pdf_text()


def review_status_summary(window, active_filter: str, visible_count: int) -> str:
    priorities = Counter()
    types = Counter()
    for row in range(window.table.rowCount()):
        priorities[cell_text(window, row, "Priority")] += 1
        types[cell_text(window, row, "Type")] += 1
    lines = [
        "Review mode summary",
        "===================",
        f"Active filter: {active_filter}",
        f"Visible rows: {visible_count} of {window.table.rowCount()}",
        "",
        "Priorities:",
        f"- Urgent: {priorities.get('Urgent', 0)}",
        f"- Due Soon: {priorities.get('Due Soon', 0)}",
        f"- Review: {priorities.get('Review', 0)}",
        f"- Info: {priorities.get('Info', 0)}",
        f"- Reviewed: {priorities.get('Reviewed', 0)}",
        f"- Ignored: {priorities.get('Ignored', 0)}",
        "",
        "Next suggestion: use Next Urgent first, then Next Review.",
    ]
    return "\n".join(lines)
