from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from mailscan2026.core import session_store, vendor_store


CATEGORY_CHOICES = ["Bills", "Medical", "Car", "Mail", "Misc", "Taxes", "Info", "Unsorted"]
TYPE_CHOICES = [
    "Bill / Payable",
    "Statement / Possible Balance",
    "Medical / Possible Payable",
    "Medical / Insurance Statement",
    "Informational / Notice",
    "Unknown / Needs Review",
]
STATUS_CHOICES = ["Imported", "Reviewed", "Ignored", "Needs Review", "Corrected"]


def install_manual_correction_tools(main_window_cls, headers: list[str]) -> None:
    """Add a simple correction panel that edits the selected document row."""
    original_documents_tab = main_window_cls._documents_tab

    def documents_tab_with_corrections(self):
        widget = original_documents_tab(self)
        panel = build_correction_panel(self)
        widget.layout().addWidget(panel)
        self.table.itemSelectionChanged.connect(self.load_selected_row_into_correction_panel)
        return widget

    def build_correction_panel(self) -> QWidget:
        box = QGroupBox("Manual Correction")
        outer = QVBoxLayout(box)

        top_row = QHBoxLayout()
        self.correction_summary_label = QLabel("Selected: none")
        self.correction_summary_label.setStyleSheet("font-weight: bold;")
        self.correction_expand_toggle = QCheckBox("Show full editor")
        self.correction_expand_toggle.setChecked(True)
        self.correction_expand_toggle.toggled.connect(self.set_correction_editor_visible)
        top_row.addWidget(self.correction_summary_label)
        top_row.addStretch()
        top_row.addWidget(self.correction_expand_toggle)
        outer.addLayout(top_row)

        self.correction_editor_widget = QWidget()
        editor_layout = QVBoxLayout(self.correction_editor_widget)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        grid = QGridLayout()
        self.correct_sender = QLineEdit()
        self.correct_category = QComboBox()
        self.correct_category.addItems(CATEGORY_CHOICES)
        self.correct_type = QComboBox()
        self.correct_type.addItems(TYPE_CHOICES)
        self.correct_amount = QLineEdit()
        self.correct_due_date = QLineEdit()
        self.correct_due_date.setPlaceholderText("MM/DD/YYYY")
        self.correct_status = QComboBox()
        self.correct_status.addItems(STATUS_CHOICES)

        grid.addWidget(QLabel("Sender"), 0, 0)
        grid.addWidget(self.correct_sender, 0, 1, 1, 3)
        grid.addWidget(QLabel("Category"), 1, 0)
        grid.addWidget(self.correct_category, 1, 1)
        grid.addWidget(QLabel("Type"), 1, 2)
        grid.addWidget(self.correct_type, 1, 3)
        grid.addWidget(QLabel("Amount"), 2, 0)
        grid.addWidget(self.correct_amount, 2, 1)
        grid.addWidget(QLabel("Due"), 2, 2)
        grid.addWidget(self.correct_due_date, 2, 3)
        grid.addWidget(QLabel("Status"), 3, 0)
        grid.addWidget(self.correct_status, 3, 1)
        editor_layout.addLayout(grid)

        self.correct_notes = QPlainTextEdit()
        self.correct_notes.setMaximumHeight(48)
        editor_layout.addWidget(QLabel("Notes"))
        editor_layout.addWidget(self.correct_notes)
        outer.addWidget(self.correction_editor_widget)

        button_row = QHBoxLayout()
        self.save_correction_button = QPushButton("Save")
        self.save_correction_button.setToolTip("Save the manual correction to the selected row and local session.")
        self.save_correction_button.clicked.connect(self.save_selected_row_correction)
        self.learn_corrected_sender_button = QPushButton("Learn")
        self.learn_corrected_sender_button.setToolTip("Learn this corrected sender into the local vendor database.")
        self.learn_corrected_sender_button.clicked.connect(self.learn_selected_corrected_sender)
        self.add_filename_alias_button = QPushButton("Add Alias")
        self.add_filename_alias_button.setToolTip("Add the selected PDF filename as an alias for the corrected sender.")
        self.add_filename_alias_button.clicked.connect(self.add_selected_filename_alias)
        self.reload_correction_button = QPushButton("Reload")
        self.reload_correction_button.setToolTip("Reload correction fields from the selected table row.")
        self.reload_correction_button.clicked.connect(self.load_selected_row_into_correction_panel)

        for button in [
            self.save_correction_button,
            self.learn_corrected_sender_button,
            self.add_filename_alias_button,
            self.reload_correction_button,
        ]:
            button.setMinimumWidth(80)
            button.setMaximumWidth(110)
            button_row.addWidget(button)
        button_row.addStretch()
        outer.addLayout(button_row)
        return box

    def set_correction_editor_visible(self, visible: bool) -> None:
        self.correction_editor_widget.setVisible(visible)
        self.correction_expand_toggle.setText("Hide full editor" if visible else "Show full editor")

    def load_selected_row_into_correction_panel(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.correct_sender.setText(cell_text(self, row, "Sender"))
        set_combo_text(self.correct_category, cell_text(self, row, "Category"))
        set_combo_text(self.correct_type, cell_text(self, row, "Type"))
        self.correct_amount.setText(cell_text(self, row, "Amount"))
        self.correct_due_date.setText(cell_text(self, row, "Due Date"))
        set_combo_text(self.correct_status, cell_text(self, row, "Status") or "Corrected")
        self.correct_notes.setPlainText(cell_text(self, row, "Notes"))
        self.update_correction_summary_label(row)

    def update_correction_summary_label(self, row: int) -> None:
        sender = cell_text(self, row, "Sender") or "Unknown sender"
        priority = cell_text(self, row, "Priority") or "No priority"
        doc_type = cell_text(self, row, "Type") or "Unknown type"
        amount = cell_text(self, row, "Amount") or "—"
        due = cell_text(self, row, "Due Date") or "—"
        self.correction_summary_label.setText(
            f"Selected: row {row + 1} | {priority} | {sender} | {doc_type} | {amount} | due {due}"
        )

    def save_selected_row_correction(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No selection", "Select a row before saving a correction.")
            return

        set_cell_text(self, row, "Sender", self.correct_sender.text().strip())
        set_cell_text(self, row, "Category", self.correct_category.currentText().strip())
        set_cell_text(self, row, "Type", self.correct_type.currentText().strip())
        set_cell_text(self, row, "Amount", self.correct_amount.text().strip())
        set_cell_text(self, row, "Due Date", self.correct_due_date.text().strip())
        set_cell_text(self, row, "Status", self.correct_status.currentText().strip() or "Corrected")

        notes = self.correct_notes.toPlainText().strip()
        if "Manual correction saved" not in notes:
            notes = (notes + " Manual correction saved.").strip()
        set_cell_text(self, row, "Notes", notes)
        set_cell_text(self, row, "Needs Review", "No" if self.correct_status.currentText() == "Reviewed" else "Yes")
        set_cell_text(self, row, "Confidence", "Manual")

        if hasattr(self, "refresh_review_flags_for_row"):
            self.refresh_review_flags_for_row(row)
        if hasattr(self, "apply_priority_for_row"):
            self.apply_priority_for_row(row)
        if hasattr(self, "update_dashboard_metrics"):
            self.update_dashboard_metrics()
        self.update_correction_summary_label(row)

        path = session_store.save_session(self.table_rows_as_dicts())
        if hasattr(self, "update_session_status"):
            self.update_session_status()
        self.log(f"Saved manual correction for row {row + 1}. Session saved: {path}")
        self.text_preview.setPlainText(
            "Correction saved.\n\n"
            f"Row: {row + 1}\n"
            f"Sender: {self.correct_sender.text().strip()}\n"
            f"Type: {self.correct_type.currentText()}\n"
            f"Amount: {self.correct_amount.text().strip() or '—'}\n"
            f"Due Date: {self.correct_due_date.text().strip() or '—'}\n\n"
            f"Session saved locally:\n{path}"
        )

    def learn_selected_corrected_sender(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No selection", "Select a corrected row first.")
            return
        self.save_selected_row_correction()
        rows = [row_as_dict(self, row)]
        count, path = vendor_store.learn_from_rows(rows)
        self.log(f"Learned corrected sender from row {row + 1}. New/updated: {count}. Path: {path}")
        QMessageBox.information(
            self,
            "Sender Learned",
            f"Learned/updated vendors: {count}\n\nSaved locally:\n{path}",
        )

    def add_selected_filename_alias(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No selection", "Select a corrected row first.")
            return
        sender = self.correct_sender.text().strip() or cell_text(self, row, "Sender")
        source = cell_text(self, row, "Source PDF")
        if not sender or not source:
            QMessageBox.information(self, "Missing info", "Sender or Source PDF is blank.")
            return

        from pathlib import Path

        alias = vendor_store.normalize_key(Path(source).stem.replace("_OCR", ""))
        learned = {vendor_store.normalize_key(v.name): v for v in vendor_store.load_learned_vendors()}
        key = vendor_store.normalize_key(sender)
        vendor = learned.get(key) or vendor_store.Vendor(
            name=sender,
            category=self.correct_category.currentText().strip() or "Unsorted",
            aliases=[],
            source="learned",
            count=0,
        )
        if alias and alias not in [vendor_store.normalize_key(a) for a in vendor.aliases]:
            vendor.aliases.append(alias)
        vendor.count += 1
        learned[key] = vendor
        path = vendor_store.save_learned_vendors(list(learned.values()))
        self.log(f"Added filename alias '{alias}' for sender '{sender}'. Path: {path}")
        QMessageBox.information(
            self,
            "Alias Added",
            f"Sender: {sender}\nAlias: {alias}\n\nSaved locally:\n{path}",
        )

    main_window_cls._documents_tab = documents_tab_with_corrections
    main_window_cls.set_correction_editor_visible = set_correction_editor_visible
    main_window_cls.load_selected_row_into_correction_panel = load_selected_row_into_correction_panel
    main_window_cls.update_correction_summary_label = update_correction_summary_label
    main_window_cls.save_selected_row_correction = save_selected_row_correction
    main_window_cls.learn_selected_corrected_sender = learn_selected_corrected_sender
    main_window_cls.add_selected_filename_alias = add_selected_filename_alias


def header_map(window) -> dict[str, int]:
    output = {}
    for col in range(window.table.columnCount()):
        item = window.table.horizontalHeaderItem(col)
        if item:
            output[item.text()] = col
    return output


def cell_text(window, row: int, header: str) -> str:
    mapping = header_map(window)
    if row < 0 or header not in mapping:
        return ""
    item = window.table.item(row, mapping[header])
    return item.text().strip() if item else ""


def set_cell_text(window, row: int, header: str, value: str) -> None:
    mapping = header_map(window)
    if row < 0 or header not in mapping:
        return
    from PySide6.QtWidgets import QTableWidgetItem

    window.table.setItem(row, mapping[header], QTableWidgetItem(value))


def row_as_dict(window, row: int) -> dict[str, str]:
    data: dict[str, str] = {}
    for header, col in header_map(window).items():
        item = window.table.item(row, col)
        data[header] = item.text().strip() if item else ""
    return data


def set_combo_text(combo: QComboBox, value: str) -> None:
    value = value.strip()
    if not value:
        return
    index = combo.findText(value)
    if index >= 0:
        combo.setCurrentIndex(index)
    else:
        combo.addItem(value)
        combo.setCurrentText(value)
