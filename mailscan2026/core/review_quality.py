from __future__ import annotations

import os
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox, QProgressDialog, QPushButton, QTableWidgetItem

from mailscan2026.core import audit_report, priority, session_store, vendor_candidates, vendor_store


REVIEW_FLAGS_HEADER = "Review Flags"


def install_review_quality_tools(
    main_window_cls,
    headers: list[str],
    classify_row: Callable,
    pdf_path_for_row: Callable,
    cell_text: Callable,
) -> None:
    """Patch review-quality tools into the current development UI."""
    if priority.PRIORITY_HEADER not in headers:
        headers.insert(0, priority.PRIORITY_HEADER)
    if REVIEW_FLAGS_HEADER not in headers:
        headers.append(REVIEW_FLAGS_HEADER)

    original_documents_tab = main_window_cls._documents_tab
    original_update_classify_button_state = main_window_cls.update_classify_button_state
    original_apply_classification_to_row = main_window_cls.apply_classification_to_row
    original_populate_table_from_rows = main_window_cls.populate_table_from_rows

    def documents_tab_with_review_tools(self):
        widget = original_documents_tab(self)
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        self.classify_unclassified_button = QPushButton("Classify Unclassified")
        self.classify_unclassified_button.clicked.connect(self.classify_unclassified_documents)
        self.classify_flagged_button = QPushButton("Classify Flagged")
        self.classify_flagged_button.clicked.connect(self.classify_flagged_documents)
        self.generate_audit_button = QPushButton("Generate Audit Report")
        self.generate_audit_button.clicked.connect(self.generate_audit_report)
        self.learn_vendors_button = QPushButton("Learn Vendors")
        self.learn_vendors_button.clicked.connect(self.learn_vendors_from_session)
        self.collect_candidates_button = QPushButton("Collect Candidates")
        self.collect_candidates_button.clicked.connect(self.collect_vendor_candidates_from_session)
        self.show_candidates_button = QPushButton("Show Candidates")
        self.show_candidates_button.clicked.connect(self.show_vendor_candidates)
        self.clean_candidates_button = QPushButton("Clean Candidates")
        self.clean_candidates_button.clicked.connect(self.clean_vendor_candidates)
        self.clear_candidates_button = QPushButton("Clear Candidates")
        self.clear_candidates_button.clicked.connect(self.clear_vendor_candidates)
        self.promote_candidates_button = QPushButton("Promote Candidates")
        self.promote_candidates_button.clicked.connect(self.promote_vendor_candidates)
        self.apply_priority_button = QPushButton("Apply Highlights")
        self.apply_priority_button.clicked.connect(self.apply_priority_highlights)
        self.mark_reviewed_button = QPushButton("Mark Reviewed")
        self.mark_reviewed_button.clicked.connect(self.mark_selected_reviewed)
        self.mark_ignored_button = QPushButton("Mark Ignored")
        self.mark_ignored_button.clicked.connect(self.mark_selected_ignored)
        self.show_vendors_button = QPushButton("Show Vendor DB")
        self.show_vendors_button.clicked.connect(self.show_vendor_database)
        self.open_local_folder_button = QPushButton("Open Local Folder")
        self.open_local_folder_button.clicked.connect(self.open_local_folder)

        review_row = QHBoxLayout()
        review_row.addWidget(self.classify_unclassified_button)
        review_row.addWidget(self.classify_flagged_button)
        review_row.addWidget(self.generate_audit_button)
        review_row.addWidget(self.learn_vendors_button)
        review_row.addWidget(self.collect_candidates_button)
        review_row.addWidget(self.show_candidates_button)
        review_row.addWidget(self.clean_candidates_button)
        review_row.addWidget(self.clear_candidates_button)
        review_row.addWidget(self.promote_candidates_button)
        review_row.addWidget(self.apply_priority_button)
        review_row.addWidget(self.mark_reviewed_button)
        review_row.addWidget(self.mark_ignored_button)
        review_row.addWidget(self.show_vendors_button)
        review_row.addWidget(self.open_local_folder_button)
        review_row.addStretch()
        widget.layout().addLayout(review_row)
        return widget

    def populate_table_from_rows_with_flags(self, rows: list[dict[str, str]]):
        original_populate_table_from_rows(self, rows)
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.refresh_review_flags()
        self.apply_priority_highlights()

    def apply_classification_to_row_with_flags(self, row: int, classification):
        original_apply_classification_to_row(self, row, classification)
        self.refresh_review_flags_for_row(row)
        self.apply_priority_for_row(row)

    def refresh_review_flags(self):
        for row in range(self.table.rowCount()):
            self.refresh_review_flags_for_row(row)

    def refresh_review_flags_for_row(self, row: int):
        if row < 0 or row >= self.table.rowCount():
            return
        row_data = {}
        for col, header in enumerate(headers):
            if header == REVIEW_FLAGS_HEADER:
                continue
            item = self.table.item(row, col)
            row_data[header] = item.text() if item else ""
        flags = audit_report.build_flags(row_data)
        self.table.setItem(row, headers.index(REVIEW_FLAGS_HEADER), QTableWidgetItem("; ".join(flags)))

    def row_as_dict(self, row: int) -> dict[str, str]:
        data: dict[str, str] = {}
        for col, header in enumerate(headers):
            item = self.table.item(row, col)
            data[header] = item.text() if item else ""
        return data

    def apply_priority_for_row(self, row: int):
        if row < 0 or row >= self.table.rowCount():
            return
        result = priority.compute_priority(self.row_as_dict(row))
        priority_col = headers.index(priority.PRIORITY_HEADER)
        self.table.setItem(row, priority_col, QTableWidgetItem(result.label))
        color = QColor(priority.COLOR_HEX.get(result.color_name, priority.COLOR_HEX["none"]))
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item is None:
                item = QTableWidgetItem("")
                self.table.setItem(row, col, item)
            item.setBackground(color)
            item.setToolTip(result.reason)

    def apply_priority_highlights(self):
        for row in range(self.table.rowCount()):
            self.apply_priority_for_row(row)
        self.table.resizeColumnsToContents()
        self.log("Applied priority highlights to document table.")

    def mark_selected_reviewed(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No selection", "Select a row first.")
            return
        self.table.setItem(row, headers.index("Status"), QTableWidgetItem("Reviewed"))
        self.refresh_review_flags_for_row(row)
        self.apply_priority_for_row(row)
        self.update_dashboard_metrics()

    def mark_selected_ignored(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No selection", "Select a row first.")
            return
        self.table.setItem(row, headers.index("Status"), QTableWidgetItem("Ignored"))
        self.refresh_review_flags_for_row(row)
        self.apply_priority_for_row(row)
        self.update_dashboard_metrics()

    def generate_audit_report(self, silent: bool = False):
        self.refresh_review_flags()
        self.apply_priority_highlights()
        rows = self.table_rows_as_dicts()
        summary = audit_report.export_audit_csv(rows)
        self.log(
            f"Generated audit report: {summary.report_path} | rows={summary.total_rows}, flagged={summary.flagged_rows}, payable_rows={summary.positive_amount_rows}, total=${summary.total_amount:,.2f}"
        )
        if not silent:
            QMessageBox.information(
                self,
                "Audit Report Generated",
                "Audit report saved locally.\n\n"
                f"Rows: {summary.total_rows}\n"
                f"Flagged rows: {summary.flagged_rows}\n"
                f"Positive payable rows: {summary.positive_amount_rows}\n"
                f"Total payable amount: ${summary.total_amount:,.2f}\n\n"
                f"{summary.report_path}",
            )
        return summary

    def learn_vendors_from_session(self, silent: bool = False):
        self.refresh_review_flags()
        rows = self.table_rows_as_dicts()
        removed, _compact_path = vendor_store.compact_learned_database()
        count, path = vendor_store.learn_from_rows(rows)
        self.log(f"Learned vendor database updated. New/updated vendors: {count}. Removed weak learned vendors: {removed}. Path: {path}")
        if not silent:
            QMessageBox.information(
                self,
                "Vendor Learning Complete",
                f"New/updated learned vendors: {count}\nRemoved weak learned vendors: {removed}\n\nSaved locally:\n{path}\n\nThis keeps only compact vendor hints, not OCR text or PDFs.",
            )
        return count, removed, path

    def collect_vendor_candidates_from_session(self, silent: bool = False):
        self.refresh_review_flags()
        rows = self.table_rows_as_dicts()
        added, updated, rejected, path = vendor_candidates.collect_from_rows(rows)
        self.log(f"Vendor candidates updated. Added: {added}. Updated: {updated}. Rejected junk: {rejected}. Path: {path}")
        if not silent:
            QMessageBox.information(
                self,
                "Vendor Candidates Updated",
                f"Added candidates: {added}\nUpdated candidates: {updated}\nRejected junk: {rejected}\n\nSaved locally:\n{path}\n\nCandidates are inactive until promoted.",
            )
        return added, updated, rejected, path

    def show_vendor_candidates(self):
        self.text_preview.setPlainText(vendor_candidates.summary())
        self.log("Displayed vendor candidates in inspector.")

    def clean_vendor_candidates(self):
        removed, path = vendor_candidates.clean_rejected_candidates()
        self.text_preview.setPlainText(vendor_candidates.summary())
        self.log(f"Cleaned rejected vendor candidates. Removed: {removed}. Path: {path}")
        QMessageBox.information(self, "Candidates Cleaned", f"Removed rejected junk candidates: {removed}\n\nSaved locally:\n{path}")

    def clear_vendor_candidates(self):
        confirm = QMessageBox.question(
            self,
            "Clear Vendor Candidates",
            "Clear all vendor candidates?\n\nThis only clears inactive candidate hints. It does not remove learned vendors, sessions, scans, PDFs, or audit reports.",
        )
        if confirm != QMessageBox.Yes:
            return
        removed, path = vendor_candidates.clear_candidates(include_rejected=True)
        self.text_preview.setPlainText(vendor_candidates.summary())
        self.log(f"Cleared vendor candidates. Removed: {removed}. Path: {path}")
        QMessageBox.information(self, "Candidates Cleared", f"Removed candidates: {removed}\n\nSaved locally:\n{path}")

    def promote_vendor_candidates(self):
        confirm = QMessageBox.question(
            self,
            "Promote Vendor Candidates",
            "Promote all active vendor candidates into the learned vendor database?\n\nOnly do this after reviewing the candidate list.",
        )
        if confirm != QMessageBox.Yes:
            return
        promoted, path = vendor_candidates.promote_all_candidates()
        self.log(f"Promoted vendor candidates: {promoted}. Learned vendor file: {path}")
        QMessageBox.information(self, "Candidates Promoted", f"Promoted: {promoted}\n\nSaved locally:\n{path}")

    def show_vendor_database(self):
        self.text_preview.setPlainText(vendor_store.database_summary())
        self.log("Displayed vendor database summary in inspector.")

    def open_local_folder(self):
        path = session_store.app_data_dir()
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))
        self.log(f"Opened local folder: {path}")

    def classify_unclassified_documents(self):
        rows = []
        for row in range(self.table.rowCount()):
            doc_type = cell_text(self, row, "Type")
            sender = cell_text(self, row, "Sender")
            confidence = cell_text(self, row, "Confidence").lower()
            if not doc_type or "unknown" in doc_type.lower() or not sender or confidence in ("", "low"):
                rows.append(row)
        self._batch_classify_rows(rows, "Classify Unclassified")

    def classify_flagged_documents(self):
        self.refresh_review_flags()
        rows = []
        for row in range(self.table.rowCount()):
            flags = cell_text(self, row, REVIEW_FLAGS_HEADER)
            if flags:
                rows.append(row)
        self._batch_classify_rows(rows, "Classify Flagged")

    def batch_classify_rows(self, rows: list[int], title: str):
        if not rows:
            QMessageBox.information(self, title, "No matching rows found.")
            return
        confirm = QMessageBox.question(
            self,
            title,
            f"Classify {len(rows)} row(s)?\n\nThis reads PDF text and updates table fields only. It does not modify source PDFs. You can cancel while it runs.",
        )
        if confirm != QMessageBox.Yes:
            return

        progress = QProgressDialog(f"{title}...", "Cancel", 0, len(rows), self)
        progress.setWindowTitle("MailScan Review Quality")
        progress.setWindowModality(Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        completed = 0
        failed = 0
        for index, row in enumerate(rows):
            if progress.wasCanceled():
                break
            self.table.selectRow(row)
            pdf = pdf_path_for_row(self, row)
            progress.setLabelText(f"{title} {index + 1} of {len(rows)}: {pdf.name if pdf else 'missing path'}")
            QApplication.processEvents()
            result = classify_row(self, row, update_preview=False)
            if result:
                completed += 1
                self.refresh_review_flags_for_row(row)
                self.apply_priority_for_row(row)
            else:
                failed += 1
            progress.setValue(index + 1)
            QApplication.processEvents()

        progress.close()
        self.normalize_info_amount_cells()
        self.refresh_review_flags()
        self.apply_priority_highlights()
        self.update_dashboard_metrics()
        self.log(f"{title} finished. Completed: {completed}, failed/skipped: {failed}.")
        QMessageBox.information(self, title, f"Completed: {completed}\nFailed/skipped: {failed}")

    def update_classify_button_state_with_review(self):
        original_update_classify_button_state(self)
        has_rows = self.table.rowCount() > 0
        for name in [
            "classify_unclassified_button", "classify_flagged_button", "generate_audit_button",
            "learn_vendors_button", "collect_candidates_button", "promote_candidates_button",
            "clean_candidates_button", "clear_candidates_button", "apply_priority_button",
            "mark_reviewed_button", "mark_ignored_button",
        ]:
            if hasattr(self, name):
                getattr(self, name).setEnabled(has_rows)
        for name in ["show_vendors_button", "show_candidates_button"]:
            if hasattr(self, name):
                getattr(self, name).setEnabled(True)

    main_window_cls._documents_tab = documents_tab_with_review_tools
    main_window_cls.populate_table_from_rows = populate_table_from_rows_with_flags
    main_window_cls.apply_classification_to_row = apply_classification_to_row_with_flags
    main_window_cls.refresh_review_flags = refresh_review_flags
    main_window_cls.refresh_review_flags_for_row = refresh_review_flags_for_row
    main_window_cls.row_as_dict = row_as_dict
    main_window_cls.apply_priority_for_row = apply_priority_for_row
    main_window_cls.apply_priority_highlights = apply_priority_highlights
    main_window_cls.mark_selected_reviewed = mark_selected_reviewed
    main_window_cls.mark_selected_ignored = mark_selected_ignored
    main_window_cls.generate_audit_report = generate_audit_report
    main_window_cls.learn_vendors_from_session = learn_vendors_from_session
    main_window_cls.collect_vendor_candidates_from_session = collect_vendor_candidates_from_session
    main_window_cls.show_vendor_candidates = show_vendor_candidates
    main_window_cls.clean_vendor_candidates = clean_vendor_candidates
    main_window_cls.clear_vendor_candidates = clear_vendor_candidates
    main_window_cls.promote_vendor_candidates = promote_vendor_candidates
    main_window_cls.show_vendor_database = show_vendor_database
    main_window_cls.open_local_folder = open_local_folder
    main_window_cls.classify_unclassified_documents = classify_unclassified_documents
    main_window_cls.classify_flagged_documents = classify_flagged_documents
    main_window_cls._batch_classify_rows = batch_classify_rows
    main_window_cls.update_classify_button_state = update_classify_button_state_with_review
