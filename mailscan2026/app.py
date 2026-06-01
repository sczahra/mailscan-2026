from pathlib import Path

from mailscan2026 import NEW_FEATURE_TABS, __version__
from mailscan2026.core import ocr_analysis, session_store
from mailscan2026.ui.main_window import MainWindow, StartupProgress

from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox, QPushButton, QTableWidgetItem


SOURCE_PDF_COLUMN = 8
HEADERS = [
    "Status", "Category", "Sender", "Type", "Amount", "Due Date",
    "Confidence", "Needs Review", "Source PDF", "Notes"
]


def apply_new_feature_tab_markers(window: MainWindow) -> None:
    """Add a one-version red-dot marker to tabs listed in NEW_FEATURE_TABS."""
    if not NEW_FEATURE_TABS or not hasattr(window, "tabs"):
        return

    for index in range(window.tabs.count()):
        tab_name = window.tabs.tabText(index).replace(" 🔴", "")
        if tab_name in NEW_FEATURE_TABS:
            window.tabs.setTabText(index, f"{tab_name} 🔴")
            window.tabs.setTabToolTip(index, "New feature added in this version")


def install_ocr_summary_patch() -> None:
    """Install the v0.4.2 smarter OCR summary without rewriting the whole UI module."""

    def extract_selected_pdf_text(self: MainWindow):
        pdf = _selected_pdf_path(self)
        if not pdf:
            QMessageBox.information(self, "No selection", "Select a document first.")
            return
        if not pdf.exists():
            QMessageBox.warning(self, "File not found", f"Could not find:\n{pdf}")
            return

        self.text_preview.setPlainText("Extracting smarter OCR summary and text preview...")
        QApplication.processEvents()

        try:
            import fitz
        except Exception as exc:
            self.text_preview.setPlainText("PyMuPDF is not available. Install requirements and try again.")
            self.log(f"Text extraction unavailable: {exc}")
            return

        try:
            doc = fitz.open(pdf)
            page_count = doc.page_count
            page_texts: list[str] = []
            page_word_counts: list[int] = []
            raw_page_chunks: list[str] = []
            max_pages = min(page_count, 5)

            for index in range(page_count):
                page = doc[index]
                text = page.get_text("text") or ""
                clean_text = text.strip()
                page_texts.append(clean_text)
                page_word_counts.append(ocr_analysis.count_words(clean_text))
                if index < max_pages:
                    raw_page_chunks.append(f"===== PAGE {index + 1} of {page_count} =====\n{clean_text}")
            doc.close()

            summary = ocr_analysis.build_summary(
                pdf=pdf,
                page_count=page_count,
                preview_pages=max_pages,
                page_texts=page_texts,
                page_word_counts=page_word_counts,
            )
            summary_text = ocr_analysis.render_summary(summary)

            raw_preview = "\n\n".join(raw_page_chunks).strip()
            if not raw_preview:
                raw_preview = "No extractable text found in the first pages. The PDF may be image-only or OCR quality may be poor."
            if page_count > max_pages:
                raw_preview += f"\n\n[Preview limited to first {max_pages} pages of {page_count}.]"

            self.text_preview.setPlainText(
                f"{summary_text}\n\n{'=' * 80}\nRAW OCR TEXT PREVIEW\n{'=' * 80}\n\n{raw_preview}"
            )
            self.log(f"Extracted smarter OCR summary and text preview from: {pdf}")
        except Exception as exc:
            self.text_preview.setPlainText(f"Could not extract text preview.\n\n{exc}")
            self.log(f"Text extraction failed for {pdf}: {exc}")

    MainWindow.extract_selected_pdf_text = extract_selected_pdf_text


def install_session_patch() -> None:
    """Add local-only save/load/clear session controls to the Documents table."""

    original_documents_tab = MainWindow._documents_tab
    original_run_startup_checks = MainWindow.run_startup_checks

    def documents_tab_with_session(self: MainWindow):
        widget = original_documents_tab(self)

        self.save_session_button = QPushButton("Save Session")
        self.save_session_button.clicked.connect(self.save_review_session)
        self.load_session_button = QPushButton("Load Session")
        self.load_session_button.clicked.connect(self.load_review_session)
        self.clear_session_button = QPushButton("Clear Session")
        self.clear_session_button.clicked.connect(self.clear_review_session)
        self.session_status_label = QPushButton("Session: local only")
        self.session_status_label.setEnabled(False)
        self.session_status_label.setToolTip(str(session_store.session_path()))

        session_row = QHBoxLayout()
        session_row.addWidget(self.save_session_button)
        session_row.addWidget(self.load_session_button)
        session_row.addWidget(self.clear_session_button)
        session_row.addWidget(self.session_status_label)
        session_row.addStretch()
        widget.layout().addLayout(session_row)

        return widget

    def run_startup_checks_with_session(self: MainWindow):
        original_run_startup_checks(self)
        self.update_session_status()
        info = session_store.session_info()
        if info.exists and info.row_count:
            self.load_review_session(silent=True)

    def table_rows_as_dicts(self: MainWindow) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row in range(self.table.rowCount()):
            data: dict[str, str] = {}
            for col, header in enumerate(HEADERS):
                item = self.table.item(row, col)
                data[header] = item.text() if item else ""
            rows.append(data)
        return rows

    def populate_table_from_rows(self: MainWindow, rows: list[dict[str, str]]):
        self.table.setRowCount(0)
        for row_data in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, header in enumerate(HEADERS):
                value = row_data.get(header, "")
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        if self.table.rowCount() > 0:
            self.table.selectRow(0)
        self._set_document_buttons_enabled(self.table.rowCount() > 0)

    def save_review_session(self: MainWindow):
        rows = self.table_rows_as_dicts()
        path = session_store.save_session(rows)
        self.update_session_status()
        self.log(f"Saved local review session with {len(rows)} row(s): {path}")
        QMessageBox.information(self, "Session Saved", f"Saved {len(rows)} row(s) locally.\n\n{path}")

    def load_review_session(self: MainWindow, silent: bool = False):
        try:
            rows = session_store.load_session()
        except Exception as exc:
            self.log(f"Could not load local review session: {exc}")
            if not silent:
                QMessageBox.warning(self, "Load Failed", f"Could not load local review session.\n\n{exc}")
            return

        if not rows:
            self.update_session_status()
            if not silent:
                QMessageBox.information(self, "No Session", "No saved local review session was found.")
            return

        self.populate_table_from_rows(rows)
        self.update_session_status()
        self.log(f"Loaded local review session with {len(rows)} row(s).")
        if not silent:
            QMessageBox.information(self, "Session Loaded", f"Loaded {len(rows)} row(s) from local session.")

    def clear_review_session(self: MainWindow):
        confirm = QMessageBox.question(
            self,
            "Clear Local Session",
            "Clear the saved local review session?\n\nThis does not delete or modify source PDFs.",
        )
        if confirm != QMessageBox.Yes:
            return
        removed = session_store.clear_session()
        self.update_session_status()
        self.log("Cleared local review session." if removed else "No local review session existed to clear.")

    def update_session_status(self: MainWindow):
        if not hasattr(self, "session_status_label"):
            return
        info = session_store.session_info()
        if info.exists:
            text = f"Session: {info.row_count} row(s)"
            if info.saved_at:
                text += f" saved {info.saved_at}"
        else:
            text = "Session: none saved"
        self.session_status_label.setText(text)
        self.session_status_label.setToolTip(str(info.path))

    MainWindow._documents_tab = documents_tab_with_session
    MainWindow.run_startup_checks = run_startup_checks_with_session
    MainWindow.table_rows_as_dicts = table_rows_as_dicts
    MainWindow.populate_table_from_rows = populate_table_from_rows
    MainWindow.save_review_session = save_review_session
    MainWindow.load_review_session = load_review_session
    MainWindow.clear_review_session = clear_review_session
    MainWindow.update_session_status = update_session_status


def _selected_pdf_path(window: MainWindow) -> Path | None:
    row = window.table.currentRow()
    if row < 0:
        return None
    item = window.table.item(row, SOURCE_PDF_COLUMN)
    if not item or not item.text().strip():
        return None
    return Path(item.text().strip())


def run_app():
    install_ocr_summary_patch()
    install_session_patch()

    app = QApplication([])
    app.setApplicationName("MailScan 2026")
    app.setApplicationVersion(__version__)

    progress = StartupProgress()
    progress.update(5, "Starting application...")
    window = MainWindow(progress.update)
    window.setWindowTitle(f"MailScan 2026 v{__version__} - Desktop Skeleton")
    apply_new_feature_tab_markers(window)
    progress.update(90, "Opening window...")
    window.show()
    progress.finish()
    app.exec()


if __name__ == "__main__":
    run_app()
