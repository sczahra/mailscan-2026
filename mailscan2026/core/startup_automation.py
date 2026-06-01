from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QGroupBox, QLabel, QMessageBox, QPushButton, QTableWidgetItem, QVBoxLayout

from mailscan2026.core import session_store, settings_store


def install_startup_automation_tools(main_window_cls, headers: list[str], classify_row: Callable) -> None:
    """Add saveable automation preferences and safe startup automation."""
    original_settings_tab = main_window_cls._settings_tab

    def settings_tab_with_automation(self):
        widget = original_settings_tab(self)
        layout = widget.layout()

        prefs = settings_store.load_preferences()
        box = QGroupBox("Startup Automation")
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(QLabel("These preferences are saved locally in .local/preferences.json. Source PDFs are still never modified."))

        self.pref_auto_load_session = QCheckBox("Auto-load saved review session on app start")
        self.pref_auto_load_session.setChecked(prefs.auto_load_session_on_start)

        self.pref_auto_import = QCheckBox("Auto-import OCR PDFs from Scan Root on app start")
        self.pref_auto_import.setChecked(prefs.auto_import_scan_root_on_start)
        self.pref_auto_import.setToolTip("Reads *_OCR.pdf files from the Scan Root only. Does not OCR, move, delete, or modify source files.")

        self.pref_auto_classify = QCheckBox("Auto-classify unclassified rows on app start")
        self.pref_auto_classify.setChecked(prefs.auto_classify_unclassified_on_start)
        self.pref_auto_classify.setToolTip("Classifies only blank/Unknown/Low-confidence rows after session/import loads.")

        self.pref_auto_preview = QCheckBox("Auto-extract preview for first selected document on app start")
        self.pref_auto_preview.setChecked(prefs.auto_extract_first_preview_on_start)
        self.pref_auto_preview.setToolTip("Shows one preview only. Does not store full OCR text.")

        self.pref_auto_audit = QCheckBox("Auto-generate audit report on app start")
        self.pref_auto_audit.setChecked(prefs.auto_generate_audit_on_start)

        save_button = QPushButton("Save Startup Preferences")
        save_button.clicked.connect(self.save_startup_preferences)

        for checkbox in [
            self.pref_auto_load_session,
            self.pref_auto_import,
            self.pref_auto_classify,
            self.pref_auto_preview,
            self.pref_auto_audit,
        ]:
            box_layout.addWidget(checkbox)
        box_layout.addWidget(save_button)
        layout.addWidget(box)
        return widget

    def save_startup_preferences(self):
        prefs = settings_store.Preferences(
            auto_load_session_on_start=self.pref_auto_load_session.isChecked(),
            auto_import_scan_root_on_start=self.pref_auto_import.isChecked(),
            auto_classify_unclassified_on_start=self.pref_auto_classify.isChecked(),
            auto_extract_first_preview_on_start=self.pref_auto_preview.isChecked(),
            auto_generate_audit_on_start=self.pref_auto_audit.isChecked(),
        )
        path = settings_store.save_preferences(prefs)
        self.log(f"Saved startup preferences: {path}")
        QMessageBox.information(self, "Preferences Saved", f"Saved locally:\n\n{path}")

    def run_startup_checks_with_preferences(self):
        self.log("Startup check: scanning local Git status...")
        report = self._git_status_report()
        self.log(report["details"])
        self.git_status_label.setText(report["label"])
        self.git_status_label.setToolTip(report["tooltip"])
        self.git_status_label.setProperty("gitState", report["state"])
        self.git_status_label.style().unpolish(self.git_status_label)
        self.git_status_label.style().polish(self.git_status_label)

        self.update_session_status()
        prefs = settings_store.load_preferences()
        self.log(f"Startup automation preferences loaded from: {settings_store.settings_path()}")

        loaded_or_imported = False
        info = session_store.session_info()
        if prefs.auto_load_session_on_start and info.exists and info.row_count:
            self.load_review_session(silent=True)
            loaded_or_imported = True
        elif prefs.auto_import_scan_root_on_start:
            loaded_or_imported = self.import_scan_root_silently()

        if loaded_or_imported:
            self.normalize_info_amount_cells()
            if hasattr(self, "refresh_review_flags"):
                self.refresh_review_flags()
            self.update_dashboard_metrics()

        if prefs.auto_classify_unclassified_on_start and self.table.rowCount() > 0:
            QTimer.singleShot(500, self.auto_classify_unclassified_safely)

        if prefs.auto_extract_first_preview_on_start and self.table.rowCount() > 0:
            QTimer.singleShot(900, self.auto_extract_first_preview_safely)

        if prefs.auto_generate_audit_on_start and self.table.rowCount() > 0:
            QTimer.singleShot(1200, self.auto_generate_audit_safely)

    def import_scan_root_silently(self) -> bool:
        root = Path(str(self.scan_root_edit.text()).strip()) if hasattr(self, "scan_root_edit") else self.scan_root
        if not root.exists():
            self.log(f"Auto-import skipped. Scan root not found: {root}")
            return False
        pdfs = [
            p for p in root.rglob("*_OCR.pdf")
            if "00_RAW" not in p.parts
            and "_OCR_FAILED" not in p.parts
            and "_SEARCH_TEXT" not in p.parts
            and "_EXPORTS" not in p.parts
        ]
        self.table.setRowCount(0)
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        for pdf in pdfs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = {
                "Status": "Imported",
                "Category": self._guess_category(pdf),
                "Sender": "",
                "Type": "",
                "Amount": "",
                "Due Date": "",
                "Confidence": "",
                "Needs Review": "Yes",
                "Source PDF": str(pdf),
                "Notes": "",
                "Review Flags": "",
            }
            for col, header in enumerate(headers):
                self.table.setItem(row, col, QTableWidgetItem(values.get(header, "")))
        self.table.resizeColumnsToContents()
        if self.table.rowCount() > 0:
            self.table.selectRow(0)
        self._set_document_buttons_enabled(self.table.rowCount() > 0)
        self.log(f"Auto-imported {len(pdfs)} OCR PDF(s) from scan root: {root}")
        return True

    def auto_classify_unclassified_safely(self):
        rows: list[int] = []
        for row in range(self.table.rowCount()):
            doc_type = _cell_text_by_headers(self, headers, row, "Type")
            sender = _cell_text_by_headers(self, headers, row, "Sender")
            confidence = _cell_text_by_headers(self, headers, row, "Confidence").lower()
            if not doc_type or "unknown" in doc_type.lower() or not sender or confidence in ("", "low"):
                rows.append(row)
        if not rows:
            self.log("Auto-classify skipped. No unclassified rows found.")
            return
        self.log(f"Auto-classifying {len(rows)} unclassified row(s).")
        self._batch_classify_rows(rows, "Auto-classify Unclassified")

    def auto_extract_first_preview_safely(self):
        if self.table.rowCount() <= 0:
            return
        self.table.selectRow(0)
        self.extract_selected_pdf_text()
        self.log("Auto-extracted first document preview.")

    def auto_generate_audit_safely(self):
        if hasattr(self, "generate_audit_report"):
            self.generate_audit_report()
            self.log("Auto-generated audit report.")

    main_window_cls._settings_tab = settings_tab_with_automation
    main_window_cls.save_startup_preferences = save_startup_preferences
    main_window_cls.run_startup_checks = run_startup_checks_with_preferences
    main_window_cls.import_scan_root_silently = import_scan_root_silently
    main_window_cls.auto_classify_unclassified_safely = auto_classify_unclassified_safely
    main_window_cls.auto_extract_first_preview_safely = auto_extract_first_preview_safely
    main_window_cls.auto_generate_audit_safely = auto_generate_audit_safely


def _cell_text_by_headers(window, headers: list[str], row: int, header: str) -> str:
    if header not in headers:
        return ""
    item = window.table.item(row, headers.index(header))
    return item.text().strip() if item else ""
