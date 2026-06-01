from pathlib import Path

from mailscan2026 import NEW_FEATURE_TABS, __version__
from mailscan2026.core import document_classifier, ocr_analysis, session_store, wiki_content
from mailscan2026.ui.main_window import MainWindow, StartupProgress

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


SOURCE_PDF_COLUMN = 8
HEADERS = [
    "Status", "Category", "Sender", "Type", "Amount", "Due Date",
    "Confidence", "Needs Review", "Source PDF", "Notes"
]
DASHBOARD_METRIC_TEXT = {
    "Documents": "0",
    "Needs Review": "0",
    "Total Amount": "—",
    "Next Due": "—",
    "Last Import": "—",
}


def apply_new_feature_tab_markers(window: MainWindow) -> None:
    """Add a one-version red-dot marker to tabs listed in NEW_FEATURE_TABS."""
    if not NEW_FEATURE_TABS or not hasattr(window, "tabs"):
        return

    for index in range(window.tabs.count()):
        tab_name = window.tabs.tabText(index).replace(" 🔴", "")
        if tab_name in NEW_FEATURE_TABS:
            window.tabs.setTabText(index, f"{tab_name} 🔴")
            window.tabs.setTabToolTip(index, "New feature added in this version")


def install_wiki_patch() -> None:
    """Add an in-app mini wiki tab for feature list, history, and roadmap."""
    original_build_ui = MainWindow._build_ui

    def build_ui_with_wiki(self: MainWindow):
        original_build_ui(self)
        wiki_tab = QWidget()
        layout = QVBoxLayout(wiki_tab)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(wiki_content.WIKI_TEXT)
        layout.addWidget(text)
        self.tabs.addTab(wiki_tab, "Wiki")

    MainWindow._build_ui = build_ui_with_wiki


def install_ocr_summary_patch() -> None:
    """Install the smarter OCR summary and bill/info classification."""

    def extract_selected_pdf_text(self: MainWindow):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No selection", "Select a document first.")
            return
        result = _classify_row(self, row, update_preview=True)
        if result:
            self.log(f"Classified and extracted OCR preview from: {result['pdf']}")

    MainWindow.extract_selected_pdf_text = extract_selected_pdf_text


def install_session_patch() -> None:
    """Add local-only save/load/clear session controls to the Documents table."""

    original_documents_tab = MainWindow._documents_tab
    original_run_startup_checks = MainWindow.run_startup_checks
    original_import_ocr_pdfs = MainWindow.import_ocr_pdfs

    def documents_tab_with_session(self: MainWindow):
        widget = original_documents_tab(self)

        self.save_session_button = QPushButton("Save Session")
        self.save_session_button.clicked.connect(self.save_review_session)
        self.load_session_button = QPushButton("Load Session")
        self.load_session_button.clicked.connect(self.load_review_session)
        self.clear_session_button = QPushButton("Clear Session")
        self.clear_session_button.clicked.connect(self.clear_review_session)
        self.classify_selected_button = QPushButton("Classify Selected")
        self.classify_selected_button.clicked.connect(self.classify_selected_document)
        self.classify_selected_button.setEnabled(False)
        self.classify_all_button = QPushButton("Classify All")
        self.classify_all_button.clicked.connect(self.classify_all_documents)
        self.classify_all_button.setToolTip("Classify rows one at a time with a progress bar and cancel option.")
        self.session_status_label = QPushButton("Session: local only")
        self.session_status_label.setEnabled(False)
        self.session_status_label.setToolTip(str(session_store.session_path()))

        session_row = QHBoxLayout()
        session_row.addWidget(self.save_session_button)
        session_row.addWidget(self.load_session_button)
        session_row.addWidget(self.clear_session_button)
        session_row.addWidget(self.classify_selected_button)
        session_row.addWidget(self.classify_all_button)
        session_row.addWidget(self.session_status_label)
        session_row.addStretch()
        widget.layout().addLayout(session_row)

        self.table.itemSelectionChanged.connect(self.update_dashboard_metrics)
        return widget

    def import_ocr_pdfs_with_metrics(self: MainWindow):
        original_import_ocr_pdfs(self)
        self.normalize_info_amount_cells()
        self.update_dashboard_metrics()
        self.update_classify_button_state()

    def run_startup_checks_with_session(self: MainWindow):
        original_run_startup_checks(self)
        self.update_session_status()
        info = session_store.session_info()
        if info.exists and info.row_count:
            self.load_review_session(silent=True)
        else:
            self.update_dashboard_metrics()

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
        self.update_classify_button_state()
        self.normalize_info_amount_cells()
        self.update_dashboard_metrics()

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
            self.update_dashboard_metrics()
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
    MainWindow.import_ocr_pdfs = import_ocr_pdfs_with_metrics
    MainWindow.run_startup_checks = run_startup_checks_with_session
    MainWindow.table_rows_as_dicts = table_rows_as_dicts
    MainWindow.populate_table_from_rows = populate_table_from_rows
    MainWindow.save_review_session = save_review_session
    MainWindow.load_review_session = load_review_session
    MainWindow.clear_review_session = clear_review_session
    MainWindow.update_session_status = update_session_status


def install_classification_patch() -> None:
    def apply_classification_to_row(self: MainWindow, row: int, classification: document_classifier.Classification):
        if row < 0:
            return
        updates = {
            "Category": classification.category,
            "Sender": classification.sender,
            "Type": classification.doc_type,
            "Amount": classification.amount if classification.is_bill else "—",
            "Due Date": classification.due_date,
            "Confidence": classification.confidence,
            "Needs Review": classification.needs_review,
            "Notes": classification.notes,
        }
        for header, value in updates.items():
            col = HEADERS.index(header)
            self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()

    def apply_classification_to_selected_row(self: MainWindow, classification: document_classifier.Classification):
        self.apply_classification_to_row(self.table.currentRow(), classification)

    def classify_selected_document(self: MainWindow):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No selection", "Select a document first.")
            return
        _classify_row(self, row, update_preview=True)
        self.update_dashboard_metrics()

    def classify_all_documents(self: MainWindow):
        total = self.table.rowCount()
        if total == 0:
            QMessageBox.information(self, "No documents", "Import OCR PDFs first.")
            return

        confirm = QMessageBox.question(
            self,
            "Classify All Documents",
            f"Classify {total} document(s) one at a time?\n\nThis reads PDF text and updates table fields only. It does not modify source PDFs. You can cancel while it runs.",
        )
        if confirm != QMessageBox.Yes:
            return

        progress = QProgressDialog("Classifying documents...", "Cancel", 0, total, self)
        progress.setWindowTitle("MailScan Batch Classification")
        progress.setWindowModality(Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        completed = 0
        failed = 0
        for row in range(total):
            if progress.wasCanceled():
                break
            self.table.selectRow(row)
            pdf = _pdf_path_for_row(self, row)
            progress.setLabelText(f"Classifying {row + 1} of {total}: {pdf.name if pdf else 'missing path'}")
            QApplication.processEvents()
            result = _classify_row(self, row, update_preview=False)
            if result:
                completed += 1
            else:
                failed += 1
            progress.setValue(row + 1)
            QApplication.processEvents()

        progress.close()
        self.normalize_info_amount_cells()
        self.update_dashboard_metrics()
        self.update_session_status()
        self.log(f"Batch classification finished. Completed: {completed}, failed/skipped: {failed}.")
        QMessageBox.information(
            self,
            "Batch Classification Complete",
            f"Completed: {completed}\nFailed/skipped: {failed}\n\nReview fields before relying on them.",
        )

    def update_classify_button_state(self: MainWindow):
        has_rows = self.table.rowCount() > 0
        if hasattr(self, "classify_selected_button"):
            self.classify_selected_button.setEnabled(has_rows and self.table.currentRow() >= 0)
        if hasattr(self, "classify_all_button"):
            self.classify_all_button.setEnabled(has_rows)

    def normalize_info_amount_cells(self: MainWindow):
        for row in range(self.table.rowCount()):
            amount_item = self.table.item(row, HEADERS.index("Amount"))
            type_item = self.table.item(row, HEADERS.index("Type"))
            notes_item = self.table.item(row, HEADERS.index("Notes"))
            amount = amount_item.text().strip() if amount_item else ""
            doc_type = type_item.text().lower().strip() if type_item else ""
            notes = notes_item.text().lower().strip() if notes_item else ""
            info_like = any(word in doc_type or word in notes for word in ["info", "notice", "usps", "mail", "no payable"])
            if info_like and amount in ("", "$0.00", "0", "0.00"):
                self.table.setItem(row, HEADERS.index("Amount"), QTableWidgetItem("—"))

    def update_dashboard_metrics(self: MainWindow):
        labels = _find_metric_labels(self)
        rows = self.table.rowCount() if hasattr(self, "table") else 0
        review_count = 0
        bill_count = 0
        total_amount = 0.0
        due_dates: list[str] = []

        if hasattr(self, "table"):
            for row in range(self.table.rowCount()):
                needs = _cell_text(self, row, "Needs Review").lower()
                amount_text = _cell_text(self, row, "Amount")
                due_text = _cell_text(self, row, "Due Date")
                doc_type = _cell_text(self, row, "Type").lower()
                notes = _cell_text(self, row, "Notes").lower()
                if needs in ("yes", "true", "1"):
                    review_count += 1
                amount_value = _parse_amount(amount_text)
                if amount_value is not None:
                    bill_count += 1
                    total_amount += amount_value
                    if due_text:
                        due_dates.append(due_text)
                elif any(word in doc_type or word in notes for word in ["informational", "notice", "usps", "no payable"]):
                    pass

        values = {
            "Documents": str(rows),
            "Needs Review": str(review_count),
            "Total Amount": f"${total_amount:,.2f}" if bill_count else "—",
            "Next Due": sorted(due_dates)[0] if due_dates else "—",
            "Last Import": f"{rows} docs" if rows else "—",
        }
        for label, value in values.items():
            if label in labels:
                labels[label].setText(value)
        self.update_classify_button_state()

    MainWindow.apply_classification_to_row = apply_classification_to_row
    MainWindow.apply_classification_to_selected_row = apply_classification_to_selected_row
    MainWindow.classify_selected_document = classify_selected_document
    MainWindow.classify_all_documents = classify_all_documents
    MainWindow.update_classify_button_state = update_classify_button_state
    MainWindow.normalize_info_amount_cells = normalize_info_amount_cells
    MainWindow.update_dashboard_metrics = update_dashboard_metrics


def _classify_row(window: MainWindow, row: int, update_preview: bool) -> dict[str, object] | None:
    pdf = _pdf_path_for_row(window, row)
    if not pdf or not pdf.exists():
        if update_preview:
            QMessageBox.warning(window, "File not found", f"Could not find:\n{pdf}")
        return None

    if update_preview:
        window.text_preview.setPlainText("Extracting OCR summary, bill/info logic, and text preview...")
        QApplication.processEvents()

    try:
        import fitz
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
            if update_preview and index < max_pages:
                raw_page_chunks.append(f"===== PAGE {index + 1} of {page_count} =====\n{clean_text}")
        doc.close()

        full_text = "\n".join(page_texts)
        summary = ocr_analysis.build_summary(
            pdf=pdf,
            page_count=page_count,
            preview_pages=max_pages,
            page_texts=page_texts,
            page_word_counts=page_word_counts,
        )
        classification = document_classifier.classify_document(pdf, full_text, summary.document_type)
        window.apply_classification_to_row(row, classification)

        if update_preview:
            summary_text = ocr_analysis.render_summary(summary)
            classification_text = _render_classification(classification)
            raw_preview = "\n\n".join(raw_page_chunks).strip()
            if not raw_preview:
                raw_preview = "No extractable text found in the first pages. The PDF may be image-only or OCR quality may be poor."
            if page_count > max_pages:
                raw_preview += f"\n\n[Preview limited to first {max_pages} pages of {page_count}.]"
            window.text_preview.setPlainText(
                f"{summary_text}\n\n{classification_text}\n\n{'=' * 80}\nRAW OCR TEXT PREVIEW\n{'=' * 80}\n\n{raw_preview}"
            )

        return {"pdf": pdf, "classification": classification}
    except Exception as exc:
        if update_preview:
            window.text_preview.setPlainText(f"Could not extract text preview.\n\n{exc}")
        window.log(f"Classification failed for {pdf}: {exc}")
        return None


def _render_classification(classification: document_classifier.Classification) -> str:
    amount = classification.amount if classification.is_bill and classification.amount else "— informational / no payable amount detected"
    return "\n".join([
        "BILL / INFORMATIONAL CLASSIFICATION",
        "=" * 80,
        f"Category: {classification.category}",
        f"Sender / Entity: {classification.sender}",
        f"Type: {classification.doc_type}",
        f"Bill vs Info: {'Bill / payable' if classification.is_bill else 'Informational / no payable amount'}",
        f"Amount: {amount}",
        f"Due Date: {classification.due_date or '—'}",
        f"Confidence: {classification.confidence}",
        f"Needs Review: {classification.needs_review}",
        f"Notes: {classification.notes}",
    ])


def _selected_pdf_path(window: MainWindow) -> Path | None:
    return _pdf_path_for_row(window, window.table.currentRow())


def _pdf_path_for_row(window: MainWindow, row: int) -> Path | None:
    if row < 0:
        return None
    item = window.table.item(row, SOURCE_PDF_COLUMN)
    if not item or not item.text().strip():
        return None
    return Path(item.text().strip())


def _cell_text(window: MainWindow, row: int, header: str) -> str:
    col = HEADERS.index(header)
    item = window.table.item(row, col)
    return item.text().strip() if item else ""


def _parse_amount(text: str) -> float | None:
    cleaned = text.strip().replace("$", "").replace(",", "")
    if cleaned in ("", "—", "-", "0", "0.00"):
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def _find_metric_labels(window: MainWindow) -> dict[str, object]:
    labels: dict[str, object] = {}
    if not hasattr(window, "tabs"):
        return labels
    dashboard = window.tabs.widget(0)
    if not dashboard:
        return labels
    for group in dashboard.findChildren(object):
        try:
            title = group.title()
        except Exception:
            continue
        if title in DASHBOARD_METRIC_TEXT:
            children = group.findChildren(object)
            for child in children:
                try:
                    if child.objectName() == "MetricValue":
                        labels[title] = child
                        break
                except Exception:
                    pass
    return labels


def run_app():
    install_wiki_patch()
    install_ocr_summary_patch()
    install_session_patch()
    install_classification_patch()

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
