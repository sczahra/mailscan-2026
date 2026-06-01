from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from mailscan2026.core import session_store


SETTINGS_FILE_NAME = "preferences.json"


@dataclass
class Preferences:
    auto_load_session_on_start: bool = True
    auto_import_scan_root_on_start: bool = False
    auto_classify_unclassified_on_start: bool = False
    auto_extract_first_preview_on_start: bool = False
    auto_generate_audit_on_start: bool = False


def settings_path() -> Path:
    return session_store.app_data_dir() / SETTINGS_FILE_NAME


def load_preferences() -> Preferences:
    path = settings_path()
    if not path.exists():
        return Preferences()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return Preferences()

    prefs = Preferences()
    for key in asdict(prefs).keys():
        if key in data:
            setattr(prefs, key, bool(data[key]))
    return prefs


def save_preferences(prefs: Preferences) -> Path:
    session_store.ensure_app_data_dir()
    path = settings_path()
    path.write_text(json.dumps(asdict(prefs), indent=2), encoding="utf-8")
    return path
