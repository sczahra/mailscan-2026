from mailscan2026 import __version__
from mailscan2026.ui.main_window import MainWindow, StartupProgress

from PySide6.QtWidgets import QApplication


def run_app():
    app = QApplication([])
    app.setApplicationName("MailScan 2026")
    app.setApplicationVersion(__version__)

    progress = StartupProgress()
    progress.update(5, "Starting application...")
    window = MainWindow(progress.update)
    window.setWindowTitle(f"MailScan 2026 v{__version__} - Desktop Skeleton")
    progress.update(90, "Opening window...")
    window.show()
    progress.finish()
    app.exec()


if __name__ == "__main__":
    run_app()
