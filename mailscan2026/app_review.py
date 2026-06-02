from pathlib import Path

from mailscan2026 import NEW_FEATURE_TABS, __version__
from mailscan2026.core import branding, review_quality, startup_automation
from mailscan2026.ui import compact_layout, simplified_workflow
from mailscan2026.ui.main_window import MainWindow, StartupProgress

import mailscan2026.app as base_app
from mailscan2026.app import (
    HEADERS,
    _cell_text,
    _classify_row,
    apply_new_feature_tab_markers,
    install_classification_patch,
    install_ocr_summary_patch,
    install_session_patch,
    install_wiki_patch,
)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel


def _dynamic_pdf_path_for_row(window: MainWindow, row: int) -> Path | None:
    """Find Source PDF by header name so adding/reordering columns cannot break file actions."""
    if row < 0 or "Source PDF" not in HEADERS:
        return None
    source_col = HEADERS.index("Source PDF")
    item = window.table.item(row, source_col)
    if not item or not item.text().strip():
        return None
    return Path(item.text().strip())


def install_safe_column_patch() -> None:
    # _classify_row lives in mailscan2026.app and looks up _pdf_path_for_row from
    # that module's globals at runtime. Replacing it here fixes file actions without
    # relying on a fragile numeric column index.
    base_app._pdf_path_for_row = _dynamic_pdf_path_for_row


def install_branding_patch() -> None:
    original_build_ui = MainWindow._build_ui

    def build_ui_with_branding(self: MainWindow):
        original_build_ui(self)
        footer = QLabel(f'{branding.copyright_text()}   |   <a href="{branding.BUY_ME_A_COFFEE_URL}">Buy me a coffee</a>')
        footer.setOpenExternalLinks(True)
        footer.setTextInteractionFlags(Qt.TextBrowserInteraction)
        footer.setToolTip(branding.BUY_ME_A_COFFEE_URL)
        self.centralWidget().layout().addWidget(footer)

    MainWindow._build_ui = build_ui_with_branding


def run_app():
    install_wiki_patch()
    install_safe_column_patch()
    install_branding_patch()
    install_ocr_summary_patch()
    install_session_patch()
    install_classification_patch()
    review_quality.install_review_quality_tools(
        MainWindow,
        HEADERS,
        _classify_row,
        _dynamic_pdf_path_for_row,
        _cell_text,
    )
    simplified_workflow.install_identify_mail_workflow(
        MainWindow,
        HEADERS,
        _classify_row,
    )
    compact_layout.install_compact_documents_patch(MainWindow)
    startup_automation.install_startup_automation_tools(
        MainWindow,
        HEADERS,
        _classify_row,
    )

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
