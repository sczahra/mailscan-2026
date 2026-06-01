from __future__ import annotations

from mailscan2026 import __version__


WIKI_TEXT = f"""
MailScan 2026 Mini Wiki
=======================
Current version: v{__version__}

Purpose
-------
MailScan 2026 is a local-first desktop utility for reviewing OCR-scanned mail, bills, notices, and documents.

Safety Rules
------------
- Source PDFs are never moved, deleted, renamed, or modified by default.
- Local/private session data lives in the project .local folder.
- .local is ignored by Git and should never be pushed to GitHub.
- Financial/scanned/private data should never be committed.
- Batch actions must be manual, visible, cancellable, and paced.

Current Workflow
----------------
1. OCR scans outside the app, currently using your working OCR workflow.
2. Import existing *_OCR.pdf files.
3. Select a document.
4. Extract text preview / classify selected.
5. Review the table fields manually.
6. Save local session to .local/review_session.json.

Feature List
------------
Dashboard
- Shows document count.
- Shows needs-review count.
- Shows total amount only when real bill amounts are detected.
- Shows a dash instead of $0.00 when documents are informational only.

Documents
- Import OCR PDFs.
- Open selected PDF.
- Open containing folder.
- Extract OCR/text preview.
- Show OCR quality summary.
- Detect blank/low-text pages.
- Detect likely duplex blank backsides.
- Guess document type.
- Detect possible tracking/article numbers.
- Detect possible dates and suspicious OCR dates.
- Detect possible people/entities and addresses.
- Classify bill vs informational.
- Fill review table fields for selected document.
- Save/load/clear local review session.
- Batch classify all rows with a progress dialog and cancel option.

Import
- Manual import only.
- Reads existing OCR PDFs.
- Does not modify source files.

Scan
- Placeholder only.
- Planned backend: NAPS2.

OCR
- Placeholder only.
- Planned backend: OCRmyPDF/Tesseract/Ghostscript.

Search
- Placeholder only.
- Planned future: local text index and/or DocFetcher integration.

Finance
- Placeholder only.
- Planned future: review exports, workbook/dashboard output, and rule-based summaries.

Wiki
- In-app feature list, change log, safety notes, and roadmap.

Change Log
----------
v0.7.0
- Added in-app Wiki tab.
- Added full feature list and change log inside the app.
- Added batch classify all rows with progress and cancel support.
- Kept batch work manual and paced to avoid cooking the computer.

v0.6.0
- Added bill vs informational classification.
- Informational documents show Amount as a dash, not $0.00.
- Dashboard total shows a dash when there are no payable bills.
- Added Classify Selected.

v0.5.0
- Added local review session save/load/clear.
- Session data originally used AppData, then was moved into the project .local folder.

v0.4.2
- Added smarter OCR summary.
- Added document type guess.
- Added blank-backside/duplex pattern detection.
- Added possible names/entities and addresses.
- Added suspicious date handling.

v0.4.1
- Added OCR quality summary.
- Added blank/low-text page detection.
- Added possible tracking numbers, dates, and dollar amount detection.

v0.4.0
- Activated Documents tab.
- Added Open Selected PDF.
- Added Open Containing Folder.
- Added Extract Text Preview.
- Added Document Inspector.

v0.3.3
- Added red-dot new-feature marker system.

v0.3.2
- Added visible version number in title bar.

v0.3.1
- Added startup progress and read-only Git status check.

v0.3.0
- Initial desktop GUI skeleton.
- Added tabs for Dashboard, Documents, Import, Scan, OCR, Search, Finance, and Settings.
- Added vintage utility visual direction.

Roadmap
-------
Near Term
- Improve batch classification speed and reliability.
- Add batch extract summary without storing full OCR text.
- Add editable review fields with validation.
- Add local rules/vendor editor.
- Add export to CSV/XLSX.

Medium Term
- Add OCR tab using existing OCR tools.
- Add Scan tab using NAPS2.
- Add search index / text cache in .local.
- Add per-document confidence warnings.

Long Term
- Package as a Windows desktop app.
- Support portable mode.
- Add backup/export/import of rules without including private document data.
- Consider porting the core logic to another UI framework if needed.

Batch Processing Notes
----------------------
Batch classification is intentionally paced.
It should process documents one at a time, keep the UI responsive, and allow canceling.
It should not save full extracted OCR text by default.
It should update only review fields and summary data.

Known Limitations
-----------------
- OCR quality depends heavily on scan quality.
- Classification is heuristic and must be reviewed.
- Dates may be OCR-misread.
- Amount detection is early and conservative.
- The app is still a development build, not a finished finance system.
""".strip()
