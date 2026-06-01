from __future__ import annotations

import os
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox, QProgressDialog, QPushButton, QTableWidgetItem

from mailscan2026.core import audit_report, session_store, vendor_store


REVIEW_FLAGS_HEADER = "Review Flags"


def install_review_quality_tools(
    main_window_cls,
    headers: list[str],
    classify_row: Callable,
    pdf_path_for_row: Callable,
    cell_text: Callable,
) -> None:
    """Patch review-quality tools into the current development UI."""
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
        self.show_vendors_button = QPushButton("Show Vendor DB")
        self.show_vendors_button.clicked.connect(self.show_vendor_database)
        self.open_local_folder_button = QPushButton("Open Local Folder")
        self.open_local_folder_button.clicked.connect(self.open_local_folder)

        review_row = QHBoxLayout()
        review_row.addWidget(self.classify_unclassified_button)
        review_row.addWidget(self.classify_flagged_button)
        review_row.addWidget(self.generate_audit_button)
        review_row.addWidget(self.learn_vendors_button)
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

    def apply_classification_to_row_with_flags(self, row: int, classification):
        original_apply_classification_to_row(self, row, classification)
        self.refresh_review_flags_for_row(row)

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

    def generate_audit_report(self):
        self.refresh_review_flags()
        rows = self.table_rows_as_dicts()
        summary = audit_report.export_audit_csv(rows)
        self.log(
            f"Generated audit report: {summary.report_path} | rows={summary.total_rows}, flagged={summary.flagged_rows}, payable_rows={summary.positive_amount_rows}, total=${summary.total_amount:,.2f}"
        )
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

    def learn_vendors_from_session(self):
        self.refresh_review_flags()
        rows = self.table_rows_as_dicts()
        count, path = vendor_store.learn_from_rows(rows)
        self.log(f"Learned vendor database updated. New/updated vendors: {count}. Path: {path}")
        QMessageBox.information(
            self,
            "Vendor Learning Complete",
            f"New/updated learned vendors: {count}\n\nSaved locally:\n{path}\n\nThis keeps only compact vendor hints, not OCR text or PDFs.",
        )

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
            else:
                failed += 1
            progress.setValue(index + 1)
            QApplication.processEvents()

        progress.close()
        self.normalize_info_amount_cells()
        self.refresh_review_flags()
        self.update_dashboard_metrics()
        self.log(f"{title} finished. Completed: {completed}, failed/skipped: {failed}.")
        QMessageBox.information(self, title, f"Completed: {completed}\nFailed/skipped: {failed}")

    def update_classify_button_state_with_review(self):
        original_update_classify_button_state(self)
        has_rows = self.table.rowCount() > 0
        for name in ["classify_unclassified_button", "classify_flagged_button", "generate_audit_button", "learn_vendors_button"]:
            if hasattr(self, name):
                getattr(self, name).setEnabled(has_rows)
        if hasattr(self, "show_vendors_button"):
            self.show_vendors_button.setEnabled(True)

    main_window_cls._documents_tab = documents_tab_with_review_tools
    main_window_cls.populate_table_from_rows = populate_table_from_rows_with_flags
    main_window_cls.apply_classification_to_row = apply_classification_to_row_with_flags
    main_window_cls.refresh_review_flags = refresh_review_flags
    main_window_cls.refresh_review_flags_for_row = refresh_review_flags_for_row
    main_window_cls.generate_audit_report = generate_audit_report
    main_window_cls.learn_vendors_from_session = learn_vendors_from_session
    main_window_cls.show_vendor_database = show_vendor_database
    main_window_cls.open_local_folder = open_local_folder
    main_window_cls.classify_unclassified_documents = classify_unclassified_documents
    main_window_cls.classify_flagged_documents = classify_flagged_documents
    main_window_cls._batch_classify_rows = batch_classify_rows
    main_window_cls.update_classify_button_state = update_classify_button_state_with_review
