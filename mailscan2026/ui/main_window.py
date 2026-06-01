from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
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
)


APP_TITLE = "MailScan 2026"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} - Desktop Skeleton")
        self.resize(1180, 780)

        self.scan_root = Path("E:/Scans")
        self._build_ui()
        self._apply_theme()
        self.log("MailScan 2026 skeleton loaded.")
        self.log("Manual-first mode: no automatic scanning, OCR, moving, or deleting.")

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

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "Status", "Category", "Sender", "Type", "Amount", "Due Date",
            "Confidence", "Needs Review", "Source PDF", "Notes"
        ])
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        open_pdf = QPushButton("Open Selected PDF")
        open_pdf.setEnabled(False)
        save_edits = QPushButton("Save Edits")
        save_edits.setEnabled(False)
        buttons.addWidget(open_pdf)
        buttons.addWidget(save_edits)
        buttons.addStretch()
        layout.addLayout(buttons)

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

        layout.addWidget(box)

        safety = QGroupBox("Safety")
        safety_layout = QVBoxLayout(safety)
        safety_layout.addWidget(QLabel("MailScan should never move, delete, or modify source scans unless explicitly enabled in a future version."))
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

        self.log(f"Preview imported {len(pdfs)} OCR PDFs from {root}")
        QMessageBox.information(self, "Import Preview", f"Found {len(pdfs)} OCR PDFs.\nNo files were modified.")

    def _guess_category(self, pdf: Path) -> str:
        known = {"Bills", "Medical", "Car", "Mail", "Misc", "Taxes"}
        for part in reversed(pdf.parts):
            if part in known:
                return part
        return ""

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


def run_app():
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
