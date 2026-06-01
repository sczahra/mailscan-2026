from mailscan2026 import NEW_FEATURE_TABS, __version__
from mailscan2026.core import review_quality
from mailscan2026.ui.main_window import MainWindow, StartupProgress

from mailscan2026.app import (
    HEADERS,
    _cell_text,
    _classify_row,
    _pdf_path_for_row,
    apply_new_feature_tab_markers,
    install_classification_patch,
    install_ocr_summary_patch,
    install_session_patch,
    install_wiki_patch,
)

from PySide6.QtWidgets import QApplication


def run_app():
    install_wiki_patch()
    install_ocr_summary_patch()
    install_session_patch()
    install_classification_patch()
    review_quality.install_review_quality_tools(
        MainWindow,
        HEADERS,
        _classify_row,
        _pdf_path_for_row,
        _cell_text,
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
