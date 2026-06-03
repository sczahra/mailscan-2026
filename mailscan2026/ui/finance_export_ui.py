from __future__ import annotations

import os

from PySide6.QtWidgets import QCheckBox, QGroupBox, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout

from mailscan2026.core import finance_export


def install_finance_export_tools(main_window_cls) -> None:
    """Add finance-ready CSV/XLSX export controls to Documents and Finance tabs."""
    original_documents_tab = main_window_cls._documents_tab
    original_finance_tab = main_window_cls._finance_tab

    def documents_tab_with_finance_export(self):
        widget = original_documents_tab(self)
        row = QHBoxLayout()
        self.export_finance_button = QPushButton("Export Finance")
        self.export_finance_button.setToolTip("Export finance-ready CSV and XLSX files from the current table.")
        self.export_finance_button.clicked.connect(lambda: self.export_finance_reviewed(False))
        self.export_reviewed_finance_button = QPushButton("Export Reviewed")
        self.export_reviewed_finance_button.setToolTip("Export only rows marked Reviewed.")
        self.export_reviewed_finance_button.clicked.connect(lambda: self.export_finance_reviewed(True))
        row.addWidget(self.export_finance_button)
        row.addWidget(self.export_reviewed_finance_button)
        row.addStretch()
        widget.layout().insertLayout(3, row)
        return widget

    def finance_tab_with_exports(self):
        widget = original_finance_tab(self)
        layout = widget.layout()
        box = QGroupBox("Finance Export")
        box_layout = QVBoxLayout(box)
        self.finance_reviewed_only_checkbox = QCheckBox("Export reviewed rows only")
        self.finance_reviewed_only_checkbox.setChecked(False)
        export_button = QPushButton("Generate Finance CSV/XLSX")
        export_button.clicked.connect(lambda: self.export_finance_reviewed(self.finance_reviewed_only_checkbox.isChecked()))
        open_button = QPushButton("Open Export Folder")
        open_button.clicked.connect(self.open_finance_export_folder)
        box_layout.addWidget(self.finance_reviewed_only_checkbox)
        box_layout.addWidget(export_button)
        box_layout.addWidget(open_button)
        layout.insertWidget(1, box)
        return widget

    def export_finance_reviewed(self, reviewed_only: bool = False):
        if self.table.rowCount() == 0:
            self.load_review_session(silent=True)
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "No rows", "No mail rows are loaded yet.")
            return None
        if hasattr(self, "refresh_review_flags"):
            self.refresh_review_flags()
        if hasattr(self, "apply_priority_highlights"):
            self.apply_priority_highlights()
        rows = self.table_rows_as_dicts()
        summary = finance_export.export_finance_files(rows, reviewed_only=reviewed_only)
        message = (
            "Finance export complete.\n\n"
            f"Rows available: {summary.total_rows}\n"
            f"Rows exported: {summary.exported_rows}\n"
            f"Payable rows: {summary.payable_rows}\n"
            f"Payable total: ${summary.payable_total:,.2f}\n\n"
            f"CSV:\n{summary.csv_path}\n\n"
            f"Excel:\n{summary.xlsx_path}"
        )
        self.text_preview.setPlainText(message)
        self.log(message)
        QMessageBox.information(self, "Finance Export Complete", message)
        return summary

    def open_finance_export_folder(self):
        folder = finance_export.session_store.app_data_dir() / "exports"
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))
        self.log(f"Opened finance export folder: {folder}")

    main_window_cls._documents_tab = documents_tab_with_finance_export
    main_window_cls._finance_tab = finance_tab_with_exports
    main_window_cls.export_finance_reviewed = export_finance_reviewed
    main_window_cls.open_finance_export_folder = open_finance_export_folder
