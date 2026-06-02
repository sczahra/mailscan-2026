from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from mailscan2026.core import session_store, vendor_store


CANDIDATE_FILE = "vendor_candidates.json"
MAX_CANDIDATES = 2000
MAX_ALIASES_PER_CANDIDATE = 25


@dataclass
class VendorCandidate:
    name: str
    category: str = "Unsorted"
    aliases: list[str] = field(default_factory=list)
    count: int = 0
    status: str = "candidate"
    reason: str = ""


def candidate_path() -> Path:
    return session_store.app_data_dir() / CANDIDATE_FILE


def load_candidates() -> list[VendorCandidate]:
    path = candidate_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    candidates: list[VendorCandidate] = []
    for item in data.get("candidates", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        candidates.append(VendorCandidate(
            name=name,
            category=str(item.get("category", "Unsorted")),
            aliases=[str(a) for a in item.get("aliases", []) if str(a).strip()][:MAX_ALIASES_PER_CANDIDATE],
            count=int(item.get("count", 0) or 0),
            status=str(item.get("status", "candidate")),
            reason=str(item.get("reason", "")),
        ))
    return candidates[:MAX_CANDIDATES]


def save_candidates(candidates: list[VendorCandidate]) -> Path:
    session_store.ensure_app_data_dir()
    candidates = sorted(candidates, key=lambda c: (-c.count, c.name.lower()))[:MAX_CANDIDATES]
    payload = {
        "schema": 1,
        "note": "Local vendor candidates only. Safe to delete. Do not commit .local.",
        "max_candidates": MAX_CANDIDATES,
        "candidates": [
            {
                "name": c.name,
                "category": c.category,
                "aliases": c.aliases[:MAX_ALIASES_PER_CANDIDATE],
                "count": c.count,
                "status": c.status,
                "reason": c.reason,
            }
            for c in candidates
        ],
    }
    path = candidate_path()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def collect_from_rows(rows: list[dict[str, str]]) -> tuple[int, int, Path]:
    existing = {vendor_store.normalize_key(c.name): c for c in load_candidates()}
    seed_keys = {vendor_store.normalize_key(v.name) for v in vendor_store.SEED_VENDORS}
    learned_keys = {vendor_store.normalize_key(v.name) for v in vendor_store.load_learned_vendors()}
    added = 0
    updated = 0

    for row in rows:
        sender = str(row.get("Sender", "")).strip()
        category = str(row.get("Category", "Unsorted")).strip() or "Unsorted"
        flags = str(row.get("Review Flags", "")).lower()
        notes = str(row.get("Notes", "")).lower()
        doc_type = str(row.get("Type", "")).lower()
        source = str(row.get("Source PDF", "")).strip()

        reason = candidate_reason(sender, flags, notes, doc_type)
        if not reason:
            continue

        key = vendor_store.normalize_key(sender)
        if not key or key in seed_keys or key in learned_keys:
            continue
        if vendor_store.should_reject_vendor_name(sender):
            # Keep obvious junk out entirely. Candidates are for plausible-but-untrusted vendors.
            continue

        if key not in existing:
            existing[key] = VendorCandidate(name=sender, category=category, count=0, reason=reason)
            added += 1
        else:
            updated += 1
            if reason not in existing[key].reason:
                existing[key].reason = "; ".join(x for x in [existing[key].reason, reason] if x)
        existing[key].count += 1

        if source:
            alias = vendor_store.normalize_key(Path(source).stem.replace("_OCR", ""))
            aliases_norm = [vendor_store.normalize_key(a) for a in existing[key].aliases]
            if alias and alias not in aliases_norm:
                existing[key].aliases.append(alias)

    path = save_candidates(list(existing.values()))
    return added, updated, path


def candidate_reason(sender: str, flags: str, notes: str, doc_type: str) -> str:
    if not sender or len(sender) < 4:
        return ""
    if "likely wrong sender" in flags:
        return ""
    if "manual sender review" in notes or "guessed from filename" in notes or "guessed from ocr line" in notes:
        return "Needs sender review"
    if "unknown" in doc_type:
        return "Unknown type but reusable sender"
    if "low confidence" in flags:
        return "Low confidence sender"
    return ""


def promote_all_candidates() -> tuple[int, Path]:
    candidates = load_candidates()
    learned = {vendor_store.normalize_key(v.name): v for v in vendor_store.load_learned_vendors()}
    promoted = 0
    for c in candidates:
        if c.status == "ignored" or vendor_store.should_reject_vendor_name(c.name):
            continue
        key = vendor_store.normalize_key(c.name)
        if not key:
            continue
        if key not in learned:
            learned[key] = vendor_store.Vendor(name=c.name, category=c.category, aliases=[], source="learned", count=0)
            promoted += 1
        learned[key].count += max(1, c.count)
        for alias in c.aliases:
            alias_key = vendor_store.normalize_key(alias)
            if alias_key and alias_key not in [vendor_store.normalize_key(a) for a in learned[key].aliases]:
                learned[key].aliases.append(alias_key)
        c.status = "promoted"
    learned_path = vendor_store.save_learned_vendors(list(learned.values()))
    save_candidates(candidates)
    return promoted, learned_path


def summary() -> str:
    candidates = load_candidates()
    lines = [
        "Vendor Candidates",
        "=================",
        f"Candidates: {len(candidates)} / {MAX_CANDIDATES}",
        f"Local candidate file: {candidate_path()}",
        "",
    ]
    if not candidates:
        lines.append("No vendor candidates yet.")
    for c in candidates:
        lines.append(f"- {c.name} [{c.category}] count={c.count} status={c.status} reason={c.reason} aliases: {', '.join(c.aliases[:5])}")
    return "\n".join(lines)
