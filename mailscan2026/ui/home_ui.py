from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from mailscan2026.core import attention_engine


HOME_CARDS = [
    "Documents",
    "Bills",
    "Payable Total",
    "Needs Review",
    "Due Soon",
    "Urgent",
    "Balance Warnings",
    "Unclear Senders",
]


def install_home_ui(main_window_cls) -> None:
    """Add a simplified home-first interface for normal users."""
    original_build_ui = main_window_cls._build_ui

    def build_ui_with_home(self):
        original_build_ui(self)
        self.home_tab = build_home_tab(self)
        self.tabs.insertTab(0, self.home_tab, "Home")
        self.tabs.setTabToolTip(0, "Simple start screen: import, identify, review, export.")
        self.tabs.setCurrentIndex(0)

    def refresh_home_summary(self):
        rows = self.table_rows_as_dicts() if hasattr(self, "table_rows_as_dicts") else []
        summary = attention_engine.summarize_rows(rows)
        update_home_cards(self, summary)
        if hasattr(self, "home_summary_text"):
            self.home_summary_text.setPlainText(attention_engine.render_home_summary(summary))
        if hasattr(self, "home_next_step_label"):
            self.home_next_step_label.setText(attention_engine.next_step(summary))
        return summary

    main_window_cls._build_ui = build_ui_with_home
    main_window_cls.refresh_home_summary = refresh_home_summary


def build_home_tab(window) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)

    hero = QGroupBox("MailScan Home")
    hero_layout = QVBoxLayout(hero)
    title = QLabel("Scan. Identify. Review only what needs attention.")
    title.setStyleSheet("font-size: 18px; font-weight: bold;")
    subtitle = QLabel("MailScan keeps the detailed tools available, but this screen is the normal workflow.")
    subtitle.setWordWrap(True)
    hero_layout.addWidget(title)
    hero_layout.addWidget(subtitle)

    action_row = QHBoxLayout()
    action_row.addWidget(primary_button("Import Mail", lambda: home_action(window, "import_ocr_pdfs"), "Import OCR PDFs into MailScan."))
    action_row.addWidget(primary_button("Identify Mail", lambda: home_action(window, "identify_mail"), "Figure out sender, type, amount, due date, and attention status."))
    action_row.addWidget(primary_button("Review Attention Items", lambda: open_review_items(window), "Jump to review items that need attention."))
    action_row.addWidget(primary_button("Export Results", lambda: home_action(window, "export_finance_reviewed", False), "Export finance-ready CSV/XLSX files."))
    action_row.addStretch()
    hero_layout.addLayout(action_row)

    window.home_next_step_label = QLabel("Next step: Import OCR PDFs or load a saved session.")
    window.home_next_step_label.setWordWrap(True)
    window.home_next_step_label.setStyleSheet("font-weight: bold;")
    hero_layout.addWidget(window.home_next_step_label)
    layout.addWidget(hero)

    grid = QGridLayout()
    window.home_metric_labels = {}
    for index, name in enumerate(HOME_CARDS):
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(card)
        label = QLabel(name)
        label.setStyleSheet("font-weight: bold;")
        value = QLabel("—")
        value.setStyleSheet("font-size: 16px;")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        window.home_metric_labels[name] = value
        grid.addWidget(card, index // 4, index % 4)
    layout.addLayout(grid)

    layout.addWidget(QLabel("Attention Summary"))
    window.home_summary_text = QTextEdit()
    window.home_summary_text.setReadOnly(True)
    window.home_summary_text.setPlainText("No mail rows loaded yet. Start with Import Mail or Identify Mail after startup import.")
    layout.addWidget(window.home_summary_text, stretch=1)
    return tab


def primary_button(text: str, callback, tooltip: str) -> QPushButton:
    button = QPushButton(text)
    button.clicked.connect(callback)
    button.setToolTip(tooltip)
    button.setMinimumHeight(42)
    button.setMinimumWidth(145)
    return button


def home_action(window, method_name: str, *args) -> None:
    method = getattr(window, method_name, None)
    if method:
        method(*args)
    if hasattr(window, "refresh_home_summary"):
        window.refresh_home_summary()
    if hasattr(window, "update_dashboard_metrics"):
        window.update_dashboard_metrics()


def open_review_items(window) -> None:
    if hasattr(window, "apply_table_filter"):
        window.apply_table_filter("Review")
    index = tab_index(window.tabs, "Documents / Advanced")
    if index < 0:
        index = tab_index(window.tabs, "Documents")
    if index >= 0:
        window.tabs.setCurrentIndex(index)
    if hasattr(window, "refresh_home_summary"):
        window.refresh_home_summary()


def update_home_cards(window, summary: attention_engine.AttentionSummary) -> None:
    labels = getattr(window, "home_metric_labels", {})
    values = {
        "Documents": str(summary.document_count),
        "Bills": str(summary.bills_found),
        "Payable Total": f"${summary.payable_total:,.2f}" if summary.bills_found else "—",
        "Needs Review": str(summary.review_count),
        "Due Soon": str(summary.due_soon_count),
        "Urgent": str(summary.urgent_count),
        "Balance Warnings": str(len(summary.possible_updates) + len(summary.possible_duplicates)),
        "Unclear Senders": str(summary.unclear_senders),
    }
    for key, value in values.items():
        if key in labels:
            labels[key].setText(value)


def tab_index(tabs, exact_name: str) -> int:
    for index in range(tabs.count()):
        if tabs.tabText(index).replace(" 🔴", "") == exact_name:
            return index
    return -1
