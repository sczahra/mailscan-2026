from pathlib import Path

from mailscan2026 import NEW_FEATURE_TABS, __version__
from mailscan2026.core import ocr_analysis
from mailscan2026.ui.main_window import MainWindow, StartupProgress

from PySide6.QtWidgets import QApplication, QMessageBox


SOURCE_PDF_COLUMN = 8


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
