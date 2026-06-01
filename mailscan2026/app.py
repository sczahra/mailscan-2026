from mailscan2026 import NEW_FEATURE_TABS, __version__
from mailscan2026.ui.main_window import MainWindow, StartupProgress

from PySide6.QtWidgets import QApplication


def apply_new_feature_tab_markers(window: MainWindow) -> None:
    """Add a one-version red-dot marker to tabs listed in NEW_FEATURE_TABS."""
    if not NEW_FEATURE_TABS or not hasattr(window, "tabs"):
        return

    for index in range(window.tabs.count()):
        tab_name = window.tabs.tabText(index).replace(" 🔴", "")
        if tab_name in NEW_FEATURE_TABS:
            window.tabs.setTabText(index, f"{tab_name} 🔴")
            window.tabs.setTabToolTip(index, "New feature added in this version")


def run_app():
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
