from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
    QSplitter,
)


APP_TITLE = "MailScan 2026"
SOURCE_PDF_COLUMN = 8


class MainWindow(QMainWindow):
    def __init__(self, progress: Callable[[int, str], None] | None = None):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} - Desktop Skeleton")
        self.resize(1180, 780)

        self.repo_root = Path(__file__).resolve().parents[2]
        self.scan_root = Path("E:/Scans")

        self._progress(progress, 10, "Building interface...")
        self._build_ui()
        self._progress(progress, 45, "Applying vintage utility theme...")
        self._apply_theme()
        self._progress(progress, 70, "Preparing startup checks...")

        self.log("MailScan 2026 skeleton loaded.")
        self.log("Manual-first mode: no automatic scanning, OCR, moving, or deleting.")

        # Run after the window is visible so startup feels responsive.
        QTimer.singleShot(250, self.run_startup_checks)

    def _progress(self, callback: Callable[[int, str], None] | None, value: int, label: str):
        if callback:
            callback(value, label)

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)

        header = QHBoxLayout()
        title = QLabel("MailScan 2026")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("Local-first scanned mail utility")
        subtitle.setObjectName("SubtitleLabel")
        header.addWidget(title)
        header.addWidget(subtitle)
        header.addStretch()

        self.git_status_label = QLabel("Git: checking...")
        self.git_status_label.setObjectName("StatusPill")
        self.git_status_label.setToolTip("Repository status is checked at startup. MailScan does not push, pull, or change Git automatically.")
        header.addWidget(self.git_status_label)

        self.btn_import = QPushButton("Import OCR PDFs")
        self.btn_import.clicked.connect(self.import_ocr_pdfs)

        self.btn_scan = QPushButton("Scan")
        self.btn_scan.setEnabled(False)
        self.btn_scan.setToolTip("Coming soon: NAPS2 scanner integration")

        self.btn_ocr = QPushButton("OCR")
        self.btn_ocr.setEnabled(False)
        self.btn_ocr.setToolTip("Coming soon: OCRmyPDF batch integration")

        self.btn_export = QPushButton("Export")
        self.btn_export.setEnabled(False)
        self.btn_export.setToolTip("Coming soon: review workbook export from edited table")

        header.addWidget(self.btn_import)
        header.addWidget(self.btn_scan)
        header.addWidget(self.btn_ocr)
        header.addWidget(self.btn_export)

        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._dashboard_tab(), "Dashboard")
        self.tabs.addTab(self._documents_tab(), "Documents")
        self.tabs.addTab(self._import_tab(), "Import")
        self.tabs.addTab(self._scan_tab(), "Scan")
        self.tabs.addTab(self._ocr_tab(), "OCR")
        self.tabs.addTab(self._search_tab(), "Search")
        self.tabs.addTab(self._finance_tab(), "Finance")
        self.tabs.addTab(self._settings_tab(), "Settings")
        layout.addWidget(self.tabs)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(130)
        layout.addWidget(QLabel("Log"))
        layout.addWidget(self.log_box)

        self.setCentralWidget(root)

    def _dashboard_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        row = QHBoxLayout()
        for label, value in [
            ("Documents", "0"),
            ("Needs Review", "0"),
            ("Total Amount", "$0.00"),
            ("Next Due", "--"),
            ("Last Import", "--"),
        ]:
            box = QGroupBox(label)
            box_layout = QVBoxLayout(box)
            big = QLabel(value)
            big.setObjectName("MetricValue")
            box_layout.addWidget(big)
            row.addWidget(box)
        layout.addLayout(row)

        note = QLabel("Dashboard charts are planned. Import data first from the Documents or Import tab.")
        note.setAlignment(Qt.AlignCenter)
        layout.addWidget(note, stretch=1)
        return w

    def _documents_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "Status", "Category", "Sender", "Type", "Amount", "Due Date",
            "Confidence", "Needs Review", "Source PDF", "Notes"
        ])
        self.table.itemSelectionChanged.connect(self.update_selected_document_summary)
        left_layout.addWidget(self.table)

        buttons = QHBoxLayout()
        self.open_pdf_button = QPushButton("Open Selected PDF")
        self.open_pdf_button.clicked.connect(self.open_selected_pdf)
        self.open_folder_button = QPushButton("Open Containing Folder")
        self.open_folder_button.clicked.connect(self.open_selected_folder)
        self.extract_text_button = QPushButton("Extract Text Preview")
        self.extract_text_button.clicked.connect(self.extract_selected_pdf_text)
        self.save_edits_button = QPushButton("Save Edits")
        self.save_edits_button.setEnabled(False)
        self.save_edits_button.setToolTip("Coming soon: save edited review fields")

        for button in [self.open_pdf_button, self.open_folder_button, self.extract_text_button]:
            button.setEnabled(False)
            buttons.addWidget(button)
        buttons.addWidget(self.save_edits_button)
        buttons.addStretch()
        left_layout.addLayout(buttons)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        inspector_box = QGroupBox("Document Inspector")
        inspector_layout = QVBoxLayout(inspector_box)
        self.selected_pdf_label = QLabel("No document selected.")
        self.selected_pdf_label.setWordWrap(True)
        inspector_layout.addWidget(self.selected_pdf_label)
        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        self.text_preview.setPlaceholderText("Select a PDF and click Extract Text Preview.")
        inspector_layout.addWidget(self.text_preview)
        right_layout.addWidget(inspector_box)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        return w

    def _import_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        info = QLabel(
            "Import Mode reads existing *_OCR.pdf files from your scan archive.\n"
            "It does not move, delete, or modify source PDFs."
        )
        layout.addWidget(info)

        btn = QPushButton("Choose Folder and Preview OCR PDFs")
        btn.clicked.connect(self.import_ocr_pdfs)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _scan_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        label = QLabel("Scan integration placeholder. Planned backend: NAPS2.Console.exe.")
        layout.addWidget(label)
        btn = QPushButton("Scan with NAPS2 - Coming Soon")
        btn.setEnabled(False)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _ocr_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        label = QLabel("OCR integration placeholder. Planned backend: OCRmyPDF + Tesseract + Ghostscript.")
        layout.addWidget(label)
        btn = QPushButton("OCR Selected RAW Folder - Coming Soon")
        btn.setEnabled(False)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _search_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        label = QLabel("Search/index tools placeholder. Planned: rebuild _SEARCH_TEXT and open DocFetcher.")
        layout.addWidget(label)
        btn = QPushButton("Rebuild Search Text - Coming Soon")
        btn.setEnabled(False)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _finance_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        label = QLabel("Finance dashboard placeholder. Planned: review rows, rules, exports, summaries.")
        layout.addWidget(label)
        btn = QPushButton("Generate Dashboard - Coming Soon")
        btn.setEnabled(False)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _settings_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        box = QGroupBox("Paths")
        form = QFormLayout(box)

        self.scan_root_edit = QLineEdit(str(self.scan_root))
        browse = QPushButton("Browse")
        browse.clicked.connect(self.choose_scan_root)

        row = QHBoxLayout()
        row.addWidget(self.scan_root_edit)
        row.addWidget(browse)
        form.addRow("Scan root", row)

        self.repo_root_edit = QLineEdit(str(self.repo_root))
        self.repo_root_edit.setReadOnly(True)
        form.addRow("Repo root", self.repo_root_edit)

        layout.addWidget(box)

        safety = QGroupBox("Safety")
        safety_layout = QVBoxLayout(safety)
        safety_layout.addWidget(QLabel("MailScan should never move, delete, or modify source scans unless explicitly enabled in a future version."))
        safety_layout.addWidget(QLabel("Startup Git checks are read-only. MailScan does not push, pull, commit, or stage files automatically."))
        layout.addWidget(safety)
        layout.addStretch()
        return w

    def choose_scan_root(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose scan root", str(self.scan_root))
        if folder:
            self.scan_root = Path(folder)
            self.scan_root_edit.setText(folder)
            self.log(f"Scan root set to: {folder}")

    def import_ocr_pdfs(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder to scan for *_OCR.pdf", str(self.scan_root))
        if not folder:
            return

        root = Path(folder)
        pdfs = [
            p for p in root.rglob("*_OCR.pdf")
            if "00_RAW" not in p.parts
            and "_OCR_FAILED" not in p.parts
            and "_SEARCH_TEXT" not in p.parts
            and "_EXPORTS" not in p.parts
        ]

        self.table.setRowCount(0)
        for pdf in pdfs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                "Imported",
                self._guess_category(pdf),
                "",
                "",
                "",
                "",
                "0",
                "Yes",
                str(pdf),
                "",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

        self.table.resizeColumnsToContents()
        self._set_document_buttons_enabled(self.table.rowCount() > 0)
        self.log(f"Preview imported {len(pdfs)} OCR PDFs from {root}")
        QMessageBox.information(self, "Import Preview", f"Found {len(pdfs)} OCR PDFs.\nNo files were modified.")

    def _guess_category(self, pdf: Path) -> str:
        known = {"Bills", "Medical", "Car", "Mail", "Misc", "Taxes"}
        for part in reversed(pdf.parts):
            if part in known:
                return part
        return ""

    def _set_document_buttons_enabled(self, enabled: bool):
        for button in [self.open_pdf_button, self.open_folder_button, self.extract_text_button]:
            button.setEnabled(enabled)

    def selected_pdf_path(self) -> Path | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, SOURCE_PDF_COLUMN)
        if not item or not item.text().strip():
            return None
        return Path(item.text().strip())

    def update_selected_document_summary(self):
        pdf = self.selected_pdf_path()
        if not pdf:
            self.selected_pdf_label.setText("No document selected.")
            self._set_document_buttons_enabled(False)
            return
        self._set_document_buttons_enabled(True)
        size_text = ""
        if pdf.exists():
            size_text = f"\nSize: {pdf.stat().st_size / (1024 * 1024):.2f} MB"
        self.selected_pdf_label.setText(f"Selected PDF:\n{pdf}{size_text}")

    def open_selected_pdf(self):
        pdf = self.selected_pdf_path()
        if not pdf:
            QMessageBox.information(self, "No selection", "Select a document first.")
            return
        if not pdf.exists():
            QMessageBox.warning(self, "File not found", f"Could not find:\n{pdf}")
            return
        os.startfile(str(pdf))
        self.log(f"Opened PDF: {pdf}")

    def open_selected_folder(self):
        pdf = self.selected_pdf_path()
        if not pdf:
            QMessageBox.information(self, "No selection", "Select a document first.")
            return
        folder = pdf.parent
        if not folder.exists():
            QMessageBox.warning(self, "Folder not found", f"Could not find:\n{folder}")
            return
        os.startfile(str(folder))
        self.log(f"Opened folder: {folder}")

    def extract_selected_pdf_text(self):
        pdf = self.selected_pdf_path()
        if not pdf:
            QMessageBox.information(self, "No selection", "Select a document first.")
            return
        if not pdf.exists():
            QMessageBox.warning(self, "File not found", f"Could not find:\n{pdf}")
            return

        self.text_preview.setPlainText("Extracting text preview...")
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
            chunks: list[str] = []
            max_pages = min(page_count, 5)
            for index in range(max_pages):
                page = doc[index]
                text = page.get_text("text") or ""
                chunks.append(f"===== PAGE {index + 1} of {page_count} =====\n{text.strip()}")
            doc.close()

            preview = "\n\n".join(chunks).strip()
            if not preview:
                preview = "No extractable text found in the first pages. The PDF may be image-only or OCR quality may be poor."
            if page_count > max_pages:
                preview += f"\n\n[Preview limited to first {max_pages} pages of {page_count}.]"
            self.text_preview.setPlainText(preview)
            self.log(f"Extracted text preview from: {pdf}")
        except Exception as exc:
            self.text_preview.setPlainText(f"Could not extract text preview.\n\n{exc}")
            self.log(f"Text extraction failed for {pdf}: {exc}")

    def run_startup_checks(self):
        self.log("Startup check: scanning local Git status...")
        report = self._git_status_report()
        self.log(report["details"])
        self.git_status_label.setText(report["label"])
        self.git_status_label.setToolTip(report["tooltip"])
        self.git_status_label.setProperty("gitState", report["state"])
        self.git_status_label.style().unpolish(self.git_status_label)
        self.git_status_label.style().polish(self.git_status_label)

    def _git_status_report(self) -> dict[str, str]:
        if not (self.repo_root / ".git").exists():
            return {
                "state": "missing",
                "label": "Git: not a repo",
                "tooltip": f"No .git folder found at {self.repo_root}",
                "details": f"Git status: no .git folder found at {self.repo_root}",
            }

        if not self._command_exists("git"):
            return {
                "state": "missing",
                "label": "Git: not found",
                "tooltip": "Git is not available on PATH.",
                "details": "Git status: git command not found on PATH.",
            }

        branch = self._run_git(["branch", "--show-current"])
        status = self._run_git(["status", "--short"])
        upstream = self._run_git(["status", "-sb"])
        remote = self._run_git(["remote", "-v"])

        branch_text = branch.strip() or "unknown"
        status_lines = [line for line in status.splitlines() if line.strip()]
        upstream_first = upstream.splitlines()[0].strip() if upstream.strip() else ""

        if status.startswith("ERROR:") or branch.startswith("ERROR:"):
            return {
                "state": "dirty",
                "label": "Git: check failed",
                "tooltip": "Startup Git check failed. See log.",
                "details": f"Git status check failed.\n{branch}\n{status}",
            }

        if status_lines:
            state = "dirty"
            label = f"Git: {len(status_lines)} change(s)"
            detail = "Git status: local changes found.\n"
        else:
            state = "clean"
            label = "Git: clean"
            detail = "Git status: working tree clean.\n"

        detail += f"Branch: {branch_text}\n"
        if upstream_first:
            detail += f"Tracking: {upstream_first}\n"
        if remote.strip():
            detail += "Remote configured.\n"

        return {
            "state": state,
            "label": label,
            "tooltip": detail.strip(),
            "details": detail.strip(),
        }

    def _command_exists(self, command: str) -> bool:
        try:
            completed = subprocess.run(
                [command, "--version"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
            return completed.returncode == 0
        except Exception:
            return False

    def _run_git(self, args: list[str]) -> str:
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=8,
                shell=False,
            )
            output = (completed.stdout or "").strip()
            error = (completed.stderr or "").strip()
            if completed.returncode != 0:
                return f"ERROR: {error or output or completed.returncode}"
            return output
        except Exception as exc:
            return f"ERROR: {exc}"

    def log(self, message: str):
        self.log_box.append(message)

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #d8d5cc;
                color: #111;
                font-family: "Segoe UI", "Tahoma", sans-serif;
                font-size: 10pt;
            }
            #TitleLabel {
                font-size: 18pt;
                font-weight: bold;
                color: #111;
            }
            #SubtitleLabel {
                color: #444;
                padding-left: 12px;
            }
            #StatusPill {
                background: #f7f5ee;
                border: 1px solid #777;
                border-radius: 8px;
                padding: 3px 9px;
                color: #222;
            }
            #StatusPill[gitState="clean"] {
                background: #dfead2;
                border-color: #728c58;
            }
            #StatusPill[gitState="dirty"] {
                background: #f0dfbd;
                border-color: #9c7a3a;
            }
            #StatusPill[gitState="missing"] {
                background: #e8caca;
                border-color: #a06464;
            }
            QPushButton {
                background: #e9e7df;
                border: 1px solid #777;
                border-radius: 3px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background: #f4f2ea;
            }
            QPushButton:disabled {
                color: #888;
                background: #c7c4bc;
                border-color: #aaa;
            }
            QGroupBox {
                border: 1px solid #8a8780;
                margin-top: 8px;
                padding: 8px;
                background: #e3e0d8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px;
            }
            #MetricValue {
                font-size: 18pt;
                font-weight: bold;
            }
            QTabWidget::pane {
                border: 1px solid #777;
                background: #ddd9cf;
            }
            QTabBar::tab {
                background: #c9c6bd;
                border: 1px solid #777;
                padding: 6px 12px;
            }
            QTabBar::tab:selected {
                background: #eeeae0;
            }
            QTableWidget, QTextEdit, QLineEdit {
                background: #f7f5ee;
                border: 1px solid #777;
                selection-background-color: #9db7d5;
            }
        """)


class StartupProgress:
    def __init__(self):
        self.dialog = QProgressDialog("Starting MailScan 2026...", "", 0, 100)
        self.dialog.setWindowTitle("MailScan 2026")
        self.dialog.setCancelButton(None)
        self.dialog.setWindowModality(Qt.ApplicationModal)
        self.dialog.setMinimumDuration(0)
        self.dialog.setValue(0)
        self.dialog.show()
        QApplication.processEvents()

    def update(self, value: int, label: str):
        self.dialog.setLabelText(label)
        self.dialog.setValue(value)
        QApplication.processEvents()

    def finish(self):
        self.dialog.setValue(100)
        self.dialog.close()
        QApplication.processEvents()
