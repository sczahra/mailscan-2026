from __future__ import annotations

from collections import Counter
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox, QPushButton

from mailscan2026.core import audit_report, session_store, vendor_candidates, vendor_store


ADVANCED_BUTTON_ATTRS = [
    "classify_selected_button",
    "classify_all_button",
    "classify_unclassified_button",
    "classify_flagged_button",
    "generate_audit_button",
    "learn_vendors_button",
    "collect_candidates_button",
    "show_candidates_button",
    "clean_candidates_button",
    "clear_candidates_button",
    "promote_candidates_button",
    "apply_priority_button",
    "show_vendors_button",
    "open_local_folder_button",
    "save_session_button",
    "clear_session_button",
]


def install_identify_mail_workflow(main_window_cls, headers: list[str], classify_row: Callable) -> None:
    """Add one normal-user workflow button and tuck developer controls behind Advanced."""
    original_documents_tab = main_window_cls._documents_tab

    def documents_tab_with_identify_mail(self):
        widget = original_documents_tab(self)

        self.identify_mail_button = QPushButton("Identify Mail")
        self.identify_mail_button.setToolTip(
            "Run the normal mail workflow: classify, flag, highlight, learn vendors, update audit, and save session."
        )
        self.identify_mail_button.setMinimumWidth(140)
        self.identify_mail_button.clicked.connect(self.identify_mail)

        self.advanced_tools_button = QPushButton("Advanced Tools")
        self.advanced_tools_button.setCheckable(True)
        self.advanced_tools_button.setToolTip("Show or hide the individual power-user buttons.")
        self.advanced_tools_button.clicked.connect(self.toggle_advanced_tools)

        primary_row = QHBoxLayout()
        primary_row.addWidget(self.identify_mail_button)
        primary_row.addWidget(self.advanced_tools_button)
        primary_row.addStretch()
        widget.layout().insertLayout(0, primary_row)

        self.set_advanced_tools_visible(False)
        return widget

    def set_advanced_tools_visible(self, visible: bool) -> None:
        for attr in ADVANCED_BUTTON_ATTRS:
            button = getattr(self, attr, None)
            if button is not None:
                button.setVisible(visible)
        label = getattr(self, "session_status_label", None)
        if label is not None:
            label.setVisible(visible)

    def toggle_advanced_tools(self) -> None:
        visible = bool(self.advanced_tools_button.isChecked())
        self.set_advanced_tools_visible(visible)
        self.advanced_tools_button.setText("Hide Advanced" if visible else "Advanced Tools")

    def identify_mail(self) -> None:
        if self.table.rowCount() == 0:
            self.load_review_session(silent=True)

        if self.table.rowCount() == 0:
            QMessageBox.information(
                self,
                "No Mail Loaded",
                "No saved mail session is loaded yet. Import OCR PDFs first, then click Identify Mail.",
            )
            return

        self.log("Identify Mail started.")
        self.identify_mail_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()

        try:
            rows_to_classify = _rows_for_identification(self, headers)
            completed = 0
            failed = 0
            for row in rows_to_classify:
                result = classify_row(self, row, update_preview=False)
                if result:
                    completed += 1
                else:
                    failed += 1
                QApplication.processEvents()

            if hasattr(self, "refresh_review_flags"):
                self.refresh_review_flags()
            if hasattr(self, "apply_priority_highlights"):
                self.apply_priority_highlights()
            self.normalize_info_amount_cells()
            self.update_dashboard_metrics()

            learned_removed, _ = vendor_store.compact_learned_database()
            learned_count, learned_path = vendor_store.learn_from_rows(self.table_rows_as_dicts())
            candidate_added, candidate_updated, candidate_rejected, candidate_path = vendor_candidates.collect_from_rows(self.table_rows_as_dicts())
            summary = audit_report.export_audit_csv(self.table_rows_as_dicts())
            session_path = session_store.save_session(self.table_rows_as_dicts())
            self.update_session_status()

            report = _plain_english_summary(
                self,
                classified=completed,
                failed=failed,
                learned_count=learned_count,
                learned_removed=learned_removed,
                candidate_added=candidate_added,
                candidate_updated=candidate_updated,
                candidate_rejected=candidate_rejected,
                audit_summary=summary,
                session_path=session_path,
                learned_path=learned_path,
                candidate_path=candidate_path,
            )
            self.text_preview.setPlainText(report)
            self.log(report)
        finally:
            QApplication.restoreOverrideCursor()
            self.identify_mail_button.setEnabled(True)
            QApplication.processEvents()

    main_window_cls._documents_tab = documents_tab_with_identify_mail
    main_window_cls.identify_mail = identify_mail
    main_window_cls.set_advanced_tools_visible = set_advanced_tools_visible
    main_window_cls.toggle_advanced_tools = toggle_advanced_tools


def _rows_for_identification(window, headers: list[str]) -> list[int]:
    rows: list[int] = []
    for row in range(window.table.rowCount()):
        doc_type = _cell_text(window, headers, row, "Type").lower()
        sender = _cell_text(window, headers, row, "Sender").strip()
        confidence = _cell_text(window, headers, row, "Confidence").lower()
        status = _cell_text(window, headers, row, "Status").lower()
        if status in {"reviewed", "ignored", "archive", "archived"}:
            continue
        if not doc_type or "unknown" in doc_type or not sender or confidence in {"", "low"}:
            rows.append(row)
    return rows


def _cell_text(window, headers: list[str], row: int, header: str) -> str:
    if header not in headers:
        return ""
    item = window.table.item(row, headers.index(header))
    return item.text().strip() if item else ""


def _plain_english_summary(
    window,
    classified: int,
    failed: int,
    learned_count: int,
    learned_removed: int,
    candidate_added: int,
    candidate_updated: int,
    candidate_rejected: int,
    audit_summary,
    session_path,
    learned_path,
    candidate_path,
) -> str:
    priorities = Counter()
    types = Counter()
    for row in range(window.table.rowCount()):
        priorities[_cell_text(window, window.table_headers if hasattr(window, "table_headers") else [], row, "Priority")] += 1
        # Fall back to direct table lookup for current patch-based headers.
        try:
            priorities[window.table.item(row, window.table.horizontalHeaderItem(0).text() == "Priority" and 0 or 0).text()] += 0
        except Exception:
            pass
        if "Type" in window.HEADERS if hasattr(window, "HEADERS") else False:
            pass

    # Use explicit table scan with visible headers so this survives future column order changes.
    header_map = {}
    for col in range(window.table.columnCount()):
        header_item = window.table.horizontalHeaderItem(col)
        if header_item:
            header_map[header_item.text()] = col

    priorities = Counter()
    types = Counter()
    for row in range(window.table.rowCount()):
        if "Priority" in header_map:
            item = window.table.item(row, header_map["Priority"])
            priorities[item.text() if item else ""] += 1
        if "Type" in header_map:
            item = window.table.item(row, header_map["Type"])
            types[item.text() if item else ""] += 1

    lines = [
        "Mail identified.",
        "",
        f"Documents reviewed: {window.table.rowCount()}",
        f"Rows classified/refreshed: {classified}",
        f"Rows skipped/failed: {failed}",
        f"Payable bills found: {audit_summary.positive_amount_rows}",
        f"Payable total: ${audit_summary.total_amount:,.2f}",
        f"Needs review / flagged rows: {audit_summary.flagged_rows}",
        "",
        "Priority summary:",
        f"- Urgent: {priorities.get('Urgent', 0)}",
        f"- Due Soon: {priorities.get('Due Soon', 0)}",
        f"- Review: {priorities.get('Review', 0)}",
        f"- Info: {priorities.get('Info', 0)}",
        f"- Reviewed: {priorities.get('Reviewed', 0)}",
        f"- Ignored: {priorities.get('Ignored', 0)}",
        "",
        "Document type summary:",
    ]
    for name, count in types.most_common():
        if name:
            lines.append(f"- {name}: {count}")

    lines.extend([
        "",
        f"Vendor learning: {learned_count} learned/updated, {learned_removed} cleaned",
        f"Vendor candidates: {candidate_added} added, {candidate_updated} updated, {candidate_rejected} rejected",
        "",
        f"Session saved: {session_path}",
        f"Audit report: {audit_summary.report_path}",
        f"Learned vendors: {learned_path}",
        f"Vendor candidates: {candidate_path}",
    ])
    return "\n".join(lines)
