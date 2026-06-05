from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget


WORKFLOW_TAB_NAMES = ["Inbox", "Review", "Correct", "Vendors"]


def install_workflow_tabs(main_window_cls) -> None:
    """Keep workflow helper tabs available internally, but hide them from normal users."""
    original_build_ui = main_window_cls._build_ui

    def build_ui_with_workflow_tabs(self):
        original_build_ui(self)
        add_workflow_tabs(self)
        self.tabs.currentChanged.connect(lambda _index: refresh_workflow_tab_text(self))

    main_window_cls._build_ui = build_ui_with_workflow_tabs


def add_workflow_tabs(window) -> None:
    tabs = window.tabs
    insert_at = tab_index(tabs, "Documents")
    if insert_at < 0:
        insert_at = 1

    tabs.insertTab(insert_at, build_inbox_tab(window), "Inbox")
    tabs.insertTab(insert_at + 1, build_review_tab(window), "Review")
    tabs.insertTab(insert_at + 2, build_correct_tab(window), "Correct")
    tabs.insertTab(insert_at + 3, build_vendors_tab(window), "Vendors")

    docs_index = tab_index(tabs, "Documents")
    if docs_index >= 0:
        tabs.setTabText(docs_index, "Advanced")
        tabs.setTabToolTip(docs_index, "Power-user table and diagnostic controls. Normal users can ignore this tab.")

    for name in WORKFLOW_TAB_NAMES:
        index = tab_index(tabs, name)
        if index >= 0:
            tabs.setTabToolTip(index, workflow_tooltip(name))
            try:
                tabs.setTabVisible(index, False)
            except AttributeError:
                pass


def build_inbox_tab(window) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.addWidget(section_label("Inbox", "Start here: import/load scans, then identify mail."))

    row = QHBoxLayout()
    row.addWidget(action_button("Identify Mail", lambda: run_action(window, "identify_mail"), "Run the normal mail workflow."))
    row.addWidget(action_button("Import OCR PDFs", lambda: run_action(window, "import_ocr_pdfs"), "Import existing OCR PDFs."))
    row.addWidget(action_button("Load Session", lambda: run_action(window, "load_review_session"), "Load the local saved review session."))
    row.addStretch()
    layout.addLayout(row)

    window.inbox_summary_text = QTextEdit()
    window.inbox_summary_text.setReadOnly(True)
    window.inbox_summary_text.setPlainText("No mail rows loaded yet. Start with Import OCR PDFs or Load Session.")
    layout.addWidget(window.inbox_summary_text, stretch=1)
    return tab


def build_review_tab(window) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.addWidget(section_label("Review", "Work through urgent, payable, and review-needed mail."))

    nav_row = QHBoxLayout()
    nav_row.addWidget(action_button("Next Urgent", lambda: jump_and_show_advanced(window, "jump_to_next_priority", "Urgent"), "Jump to next urgent row."))
    nav_row.addWidget(action_button("Next Review", lambda: jump_and_show_advanced(window, "jump_to_next_priority", "Review"), "Jump to next review row."))
    nav_row.addWidget(action_button("Next Payable", lambda: jump_and_show_advanced(window, "jump_to_next_payable"), "Jump to next payable row."))
    nav_row.addWidget(action_button("Mark Reviewed", lambda: run_action(window, "mark_selected_reviewed"), "Mark current row reviewed."))
    nav_row.addWidget(action_button("Mark Ignored", lambda: run_action(window, "mark_selected_ignored"), "Mark current row ignored."))
    nav_row.addStretch()
    layout.addLayout(nav_row)

    filter_row = QHBoxLayout()
    for name in ["All", "Urgent", "Due Soon", "Review", "Payable", "Info", "Reviewed", "Ignored"]:
        filter_row.addWidget(action_button(name, lambda n=name: apply_filter_and_show(window, n), f"Filter documents by {name}."))
    filter_row.addStretch()
    layout.addLayout(filter_row)

    window.review_summary_text = QTextEdit()
    window.review_summary_text.setReadOnly(True)
    window.review_summary_text.setPlainText("Load mail, then use Next Urgent or Next Review to move through the pile.")
    layout.addWidget(window.review_summary_text, stretch=1)
    return tab


def build_correct_tab(window) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.addWidget(section_label("Correct", "Use this tab as a clean doorway to the correction panel."))

    row = QHBoxLayout()
    row.addWidget(action_button("Open Correction Panel", lambda: show_advanced_tab(window), "Open Advanced where the correction panel lives."))
    row.addWidget(action_button("Save Correction", lambda: run_action(window, "save_selected_row_correction"), "Save the current correction fields."))
    row.addWidget(action_button("Learn Sender", lambda: run_action(window, "learn_selected_corrected_sender"), "Learn the corrected sender."))
    row.addWidget(action_button("Add Alias", lambda: run_action(window, "add_selected_filename_alias"), "Add filename alias for corrected sender."))
    row.addStretch()
    layout.addLayout(row)

    window.correct_summary_text = QTextEdit()
    window.correct_summary_text.setReadOnly(True)
    window.correct_summary_text.setPlainText("Select a row, then open the correction panel to edit sender, amount, due date, type, and notes.")
    layout.addWidget(window.correct_summary_text, stretch=1)
    return tab


def build_vendors_tab(window) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.addWidget(section_label("Vendors", "Review learned vendors and candidates without crowding the main mail table."))

    row = QHBoxLayout()
    row.addWidget(action_button("Show Vendor DB", lambda: run_text_action(window, "show_vendor_database"), "Show vendor database summary."))
    row.addWidget(action_button("Show Candidates", lambda: run_text_action(window, "show_vendor_candidates"), "Show vendor candidates."))
    row.addWidget(action_button("Collect Candidates", lambda: run_text_action(window, "collect_vendor_candidates_from_session"), "Collect candidates from loaded rows."))
    row.addWidget(action_button("Clean Candidates", lambda: run_text_action(window, "clean_vendor_candidates"), "Remove rejected candidate junk."))
    row.addWidget(action_button("Promote Candidates", lambda: run_text_action(window, "promote_vendor_candidates"), "Promote active candidates after review."))
    row.addStretch()
    layout.addLayout(row)

    window.vendor_summary_text = QTextEdit()
    window.vendor_summary_text.setReadOnly(True)
    window.vendor_summary_text.setPlainText("Vendor tools live here. Candidate promotion should still be reviewed carefully.")
    layout.addWidget(window.vendor_summary_text, stretch=1)
    return tab


def section_label(title: str, subtitle: str) -> QGroupBox:
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    label = QLabel(subtitle)
    label.setWordWrap(True)
    layout.addWidget(label)
    return box


def action_button(text: str, callback, tooltip: str = "") -> QPushButton:
    button = QPushButton(text)
    button.clicked.connect(callback)
    if tooltip:
        button.setToolTip(tooltip)
    return button


def run_action(window, method_name: str, *args) -> None:
    method = getattr(window, method_name, None)
    if method:
        method(*args)
    refresh_workflow_tab_text(window)
    if hasattr(window, "refresh_home_summary"):
        window.refresh_home_summary()
    if hasattr(window, "update_dashboard_metrics"):
        window.update_dashboard_metrics()


def run_text_action(window, method_name: str) -> None:
    run_action(window, method_name)
    text = getattr(window, "text_preview", None)
    vendor_text = getattr(window, "vendor_summary_text", None)
    if text is not None and vendor_text is not None:
        vendor_text.setPlainText(text.toPlainText())


def tab_index(tabs, exact_name: str) -> int:
    for index in range(tabs.count()):
        label = tabs.tabText(index).replace(" 🔴", "")
        if label == exact_name:
            return index
    return -1


def workflow_tooltip(name: str) -> str:
    return {
        "Inbox": "Hidden helper tab. Home is the normal start screen.",
        "Review": "Hidden helper tab. Home and Review Attention Items are the normal path.",
        "Correct": "Hidden helper tab. Advanced contains correction tools.",
        "Vendors": "Hidden helper tab. Vendor tools will move into Advanced settings later.",
    }.get(name, "MailScan workflow tab")


def show_advanced_tab(window) -> None:
    index = tab_index(window.tabs, "Advanced")
    if index < 0:
        index = tab_index(window.tabs, "Documents / Advanced")
    if index < 0:
        index = tab_index(window.tabs, "Documents")
    if index >= 0:
        window.tabs.setCurrentIndex(index)


def jump_and_show_advanced(window, method_name: str, *args) -> None:
    show_advanced_tab(window)
    method = getattr(window, method_name, None)
    if method:
        method(*args)
    refresh_workflow_tab_text(window)


def apply_filter_and_show(window, filter_name: str) -> None:
    show_advanced_tab(window)
    if hasattr(window, "apply_table_filter"):
        window.apply_table_filter(filter_name)
    refresh_workflow_tab_text(window)


def refresh_workflow_tab_text(window) -> None:
    summary = build_workflow_summary(window)
    for attr in ["inbox_summary_text", "review_summary_text", "correct_summary_text", "vendor_summary_text"]:
        widget = getattr(window, attr, None)
        if widget is not None and not widget.hasFocus():
            widget.setPlainText(summary)


def build_workflow_summary(window) -> str:
    if not hasattr(window, "table") or window.table.rowCount() == 0:
        return "No mail rows loaded yet. Start from Home with Import Mail or Identify Mail."
    counts = {}
    headers = {}
    for col in range(window.table.columnCount()):
        item = window.table.horizontalHeaderItem(col)
        if item:
            headers[item.text()] = col
    for row in range(window.table.rowCount()):
        priority = cell_text(window, headers, row, "Priority") or "Unknown"
        counts[priority] = counts.get(priority, 0) + 1
    lines = [
        "MailScan workflow summary",
        "=========================",
        f"Loaded documents: {window.table.rowCount()}",
        "",
        "Priority counts:",
    ]
    for name in ["Urgent", "Due Soon", "Review", "Info", "Reviewed", "Ignored", "Payable", "Unknown"]:
        if counts.get(name, 0):
            lines.append(f"- {name}: {counts[name]}")
    lines.extend([
        "",
        "Tip: Home is the normal workflow. Use Advanced only when you need every internal control.",
    ])
    return "\n".join(lines)


def cell_text(window, headers: dict[str, int], row: int, header: str) -> str:
    if header not in headers:
        return ""
    item = window.table.item(row, headers[header])
    return item.text().strip() if item else ""
