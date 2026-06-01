from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


LOCAL_DIR_NAME = ".local"
SESSION_FILE_NAME = "review_session.json"


@dataclass(frozen=True)
class SessionInfo:
    path: Path
    exists: bool
    row_count: int = 0
    saved_at: str = ""


def repo_root() -> Path:
    # session_store.py -> core -> mailscan2026 -> repo root
    return Path(__file__).resolve().parents[2]


def app_data_dir() -> Path:
    # Keep local/private data inside the project folder, but under .local
    # so Git ignores it and it stays off GitHub.
    return repo_root() / LOCAL_DIR_NAME


def session_path() -> Path:
    return app_data_dir() / SESSION_FILE_NAME


def ensure_app_data_dir() -> Path:
    path = app_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_info() -> SessionInfo:
    path = session_path()
    if not path.exists():
        return SessionInfo(path=path, exists=False)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("rows", [])
        return SessionInfo(
            path=path,
            exists=True,
            row_count=len(rows) if isinstance(rows, list) else 0,
            saved_at=str(data.get("saved_at", "")),
        )
    except Exception:
        return SessionInfo(path=path, exists=True)


def save_session(rows: list[dict[str, str]]) -> Path:
    ensure_app_data_dir()
    payload = {
        "app": "MailScan 2026",
        "schema": 1,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "storage": "repo-local .local folder",
        "rows": rows,
    }
    path = session_path()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_session() -> list[dict[str, str]]:
    path = session_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows", [])
    if not isinstance(rows, list):
        return []
    clean_rows: list[dict[str, str]] = []
    for row in rows:
        if isinstance(row, dict):
            clean_rows.append({str(k): str(v) for k, v in row.items()})
    return clean_rows


def clear_session() -> bool:
    path = session_path()
    if path.exists():
        path.unlink()
        return True
    return False
