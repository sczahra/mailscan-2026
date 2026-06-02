from __future__ import annotations

from PySide6.QtWidgets import QPushButton


BUTTON_LABELS = {
    "Classify Unclassified": "Classify Uncls",
    "Classify Flagged": "Flagged",
    "Generate Audit Report": "Audit",
    "Learn Vendors": "Learn",
    "Collect Candidates": "Collect",
    "Show Candidates": "Candidates",
    "Clean Candidates": "Clean",
    "Clear Candidates": "Clear",
    "Promote Candidates": "Promote",
    "Apply Highlights": "Highlight",
    "Mark Reviewed": "Reviewed",
    "Mark Ignored": "Ignored",
    "Show Vendor DB": "Vendors",
    "Open Local Folder": "Local Folder",
    "Open Containing Folder": "Open Folder",
    "Extract Text Preview": "Text Preview",
    "Open Selected PDF": "Open PDF",
}


def install_compact_documents_patch(main_window_cls) -> None:
    """Make the current development button-heavy Documents view fit smaller windows better."""
    original_documents_tab = main_window_cls._documents_tab

    def documents_tab_compact(self):
        widget = original_documents_tab(self)
        compact_buttons(widget)
        try:
            self.table.setMinimumWidth(520)
        except Exception:
            pass
        return widget

    main_window_cls._documents_tab = documents_tab_compact


def compact_buttons(widget) -> None:
    for button in widget.findChildren(QPushButton):
        original = button.text()
        if original in BUTTON_LABELS:
            button.setToolTip(original if not button.toolTip() else button.toolTip())
            button.setText(BUTTON_LABELS[original])
        button.setMaximumWidth(105)
        button.setMinimumWidth(72)
