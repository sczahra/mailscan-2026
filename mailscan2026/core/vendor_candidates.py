from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from mailscan2026.core import session_store, vendor_store


CANDIDATE_FILE = "vendor_candidates.json"
MAX_CANDIDATES = 2000
MAX_ALIASES_PER_CANDIDATE = 25
MIN_QUALITY_SCORE = 45


@dataclass
class VendorCandidate:
    name: str
    category: str = "Unsorted"
    aliases: list[str] = field(default_factory=list)
    count: int = 0
    status: str = "candidate"
    reason: str = ""
    quality_score: int = 0


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
        score = int(item.get("quality_score", quality_score(name)) or 0)
        status = str(item.get("status", "candidate"))
        if status == "candidate" and (score < MIN_QUALITY_SCORE or is_gibberish_candidate(name)):
            status = "rejected_junk"
        candidates.append(VendorCandidate(
            name=name,
            category=str(item.get("category", "Unsorted")),
            aliases=[str(a) for a in item.get("aliases", []) if str(a).strip()][:MAX_ALIASES_PER_CANDIDATE],
            count=int(item.get("count", 0) or 0),
            status=status,
            reason=str(item.get("reason", "")),
            quality_score=score,
        ))
    return candidates[:MAX_CANDIDATES]


def save_candidates(candidates: list[VendorCandidate]) -> Path:
    session_store.ensure_app_data_dir()
    candidates = sorted(candidates, key=lambda c: (c.status != "candidate", -c.quality_score, -c.count, c.name.lower()))[:MAX_CANDIDATES]
    payload = {
        "schema": 1,
        "note": "Local vendor candidates only. Safe to delete. Do not commit .local.",
        "max_candidates": MAX_CANDIDATES,
        "min_quality_score": MIN_QUALITY_SCORE,
        "candidates": [
            {
                "name": c.name,
                "category": c.category,
                "aliases": c.aliases[:MAX_ALIASES_PER_CANDIDATE],
                "count": c.count,
                "status": c.status,
                "reason": c.reason,
                "quality_score": c.quality_score,
            }
            for c in candidates
        ],
    }
    path = candidate_path()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def collect_from_rows(rows: list[dict[str, str]]) -> tuple[int, int, int, Path]:
    existing = {vendor_store.normalize_key(c.name): c for c in load_candidates()}
    seed_keys = {vendor_store.normalize_key(v.name) for v in vendor_store.SEED_VENDORS}
    learned_keys = {vendor_store.normalize_key(v.name) for v in vendor_store.load_learned_vendors()}
    added = 0
    updated = 0
    rejected = 0

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
        score = quality_score(sender)
        if vendor_store.should_reject_vendor_name(sender) or score < MIN_QUALITY_SCORE or is_gibberish_candidate(sender):
            rejected += 1
            if key and key not in existing:
                existing[key] = VendorCandidate(
                    name=sender,
                    category=category,
                    count=1,
                    status="rejected_junk",
                    reason="Auto-rejected candidate junk",
                    quality_score=score,
                )
            elif key in existing:
                existing[key].status = "rejected_junk"
                existing[key].quality_score = score
            continue

        if key not in existing:
            existing[key] = VendorCandidate(name=sender, category=category, count=0, reason=reason, quality_score=score)
            added += 1
        else:
            updated += 1
            existing[key].quality_score = max(existing[key].quality_score, score)
            if reason not in existing[key].reason:
                existing[key].reason = "; ".join(x for x in [existing[key].reason, reason] if x)
        existing[key].count += 1

        if source:
            alias = vendor_store.normalize_key(Path(source).stem.replace("_OCR", ""))
            aliases_norm = [vendor_store.normalize_key(a) for a in existing[key].aliases]
            if alias and alias not in aliases_norm:
                existing[key].aliases.append(alias)

    path = save_candidates(list(existing.values()))
    return added, updated, rejected, path


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


def quality_score(name: str) -> int:
    value = name.strip()
    if not value:
        return 0
    letters = re.findall(r"[A-Za-z]", value)
    upper = re.findall(r"[A-Z]", value)
    lower = re.findall(r"[a-z]", value)
    digits = re.findall(r"\d", value)
    words = re.findall(r"[A-Za-z]+", value)
    score = 50

    if len(value) < 4 or len(value) > 55:
        score -= 30
    if len(words) >= 2:
        score += 15
    if len(words) == 1 and len(words[0]) >= 6:
        score += 5
    if not letters:
        score -= 40
    if digits:
        score -= min(30, len(digits) * 8)
    if len(upper) > len(lower) * 2 and len(upper) > 5:
        score -= 20
    if re.search(r"[(){}\[\]|_]", value):
        score -= 25
    if re.search(r"[A-Za-z]{10,}", value):
        score -= 15
    if vowel_ratio(value) < 0.18:
        score -= 20
    if consonant_run(value) >= 5:
        score -= 20
    if re.search(r"\b(?:llc|inc|corp|company|bank|services|service|finance|medical|health|insurance|propane|energy|water|wireless|diagnostics)\b", value, re.IGNORECASE):
        score += 20
    return max(0, min(100, score))


def is_gibberish_candidate(name: str) -> bool:
    value = name.strip()
    key = vendor_store.normalize_key(value)
    if not key:
        return True
    if re.search(r"[(){}\[\]|_]", value):
        return True
    if vowel_ratio(value) < 0.15 and len(value) > 8:
        return True
    if consonant_run(value) >= 5:
        return True
    if re.search(r"[a-z][A-Z]{2,}[a-z]", value):
        return True
    if re.search(r"\b(?:pssd|dpu|ipi|bint|scoatm)\b", key):
        return True
    return False


def vowel_ratio(text: str) -> float:
    letters = re.findall(r"[A-Za-z]", text.lower())
    if not letters:
        return 0.0
    vowels = [ch for ch in letters if ch in "aeiou"]
    return len(vowels) / len(letters)


def consonant_run(text: str) -> int:
    best = 0
    current = 0
    for ch in text.lower():
        if ch.isalpha() and ch not in "aeiou":
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def promote_all_candidates() -> tuple[int, Path]:
    candidates = load_candidates()
    learned = {vendor_store.normalize_key(v.name): v for v in vendor_store.load_learned_vendors()}
    promoted = 0
    for c in candidates:
        if c.status != "candidate" or vendor_store.should_reject_vendor_name(c.name) or c.quality_score < MIN_QUALITY_SCORE:
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


def clear_candidates(include_rejected: bool = True) -> tuple[int, Path]:
    candidates = load_candidates()
    if include_rejected:
        removed = len(candidates)
        kept: list[VendorCandidate] = []
    else:
        kept = [c for c in candidates if c.status != "rejected_junk"]
        removed = len(candidates) - len(kept)
    path = save_candidates(kept)
    return removed, path


def clean_rejected_candidates() -> tuple[int, Path]:
    return clear_candidates(include_rejected=False)


def summary() -> str:
    candidates = load_candidates()
    active = [c for c in candidates if c.status == "candidate"]
    rejected = [c for c in candidates if c.status == "rejected_junk"]
    lines = [
        "Vendor Candidates",
        "=================",
        f"Active candidates: {len(active)} / {MAX_CANDIDATES}",
        f"Rejected junk kept for review: {len(rejected)}",
        f"Local candidate file: {candidate_path()}",
        "",
    ]
    if not candidates:
        lines.append("No vendor candidates yet.")
    for c in candidates:
        lines.append(f"- {c.name} [{c.category}] count={c.count} status={c.status} score={c.quality_score} reason={c.reason} aliases: {', '.join(c.aliases[:5])}")
    return "\n".join(lines)
