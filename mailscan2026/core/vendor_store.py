from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from mailscan2026.core import session_store


LEARNED_VENDOR_FILE = "vendors_learned.json"
MAX_LEARNED_VENDORS = 500
MAX_ALIASES_PER_VENDOR = 20


@dataclass
class Vendor:
    name: str
    category: str = "Unsorted"
    aliases: list[str] = field(default_factory=list)
    source: str = "seed"
    count: int = 0


SEED_VENDORS: list[Vendor] = [
    Vendor("United States Postal Service", "Mail", ["usps", "united states postal", "ps form 3849", "redelivery"]),
    Vendor("Three Oaks Propane", "Bills", ["3oaks", "3 oaks", "three oaks", "propane", "3OAKS_OCR"]),
    Vendor("Hill Davis", "Bills", ["hill davis", "hilldavis", "HILLDAVIS_OCR"]),
    Vendor("Mission Lane", "Bills", ["mission lane", "mission lane llc"]),
    Vendor("Chase", "Bills", ["chase", "jpmorgan chase", "jp morgan"]),
    Vendor("Sentara", "Medical", ["sentara", "senta ra"]),
    Vendor("Guardian", "Medical", ["guardian", "guardian life", "guardian life insurance"]),
    Vendor("Labcorp", "Medical", ["labcorp", "laboratory corporation of america"]),
    Vendor("Subaru Motors Finance", "Car", ["subaru", "subaru motors finance"]),
    Vendor("Farmville Social Services", "Misc", ["socialservices", "social services", "department of social services", "medicaid"]),
    Vendor("Dominion Energy", "Bills", ["dominion", "dominion energy", "dominion power"]),
    Vendor("Appomattox River Water Authority", "Bills", ["appomattox river water", "water authority"]),
    Vendor("Verizon", "Bills", ["verizon", "verizon wireless"]),
    Vendor("Xfinity", "Bills", ["xfinity", "comcast"]),
    Vendor("T-Mobile", "Bills", ["t-mobile", "tmobile"]),
    Vendor("AT&T", "Bills", ["at&t", "att ", "at t"]),
    Vendor("Capital One", "Bills", ["capital one", "capitalone"]),
    Vendor("Synchrony", "Bills", ["synchrony", "synchrony bank"]),
    Vendor("Wells Fargo", "Bills", ["wells fargo"]),
    Vendor("Bank of America", "Bills", ["bank of america", "bofa"]),
    Vendor("Citi", "Bills", ["citibank", "citi ", "citicards"]),
    Vendor("Discover", "Bills", ["discover", "discover card"]),
    Vendor("American Express", "Bills", ["american express", "amex"]),
    Vendor("Progressive", "Bills", ["progressive", "progressive insurance"]),
    Vendor("GEICO", "Bills", ["geico"]),
    Vendor("State Farm", "Bills", ["state farm"]),
    Vendor("Allstate", "Bills", ["allstate"]),
    Vendor("Nationwide", "Bills", ["nationwide"]),
    Vendor("Anthem", "Medical", ["anthem", "blue cross", "blue shield", "bcbs"]),
    Vendor("Aetna", "Medical", ["aetna"]),
    Vendor("Cigna", "Medical", ["cigna"]),
    Vendor("UnitedHealthcare", "Medical", ["unitedhealthcare", "united healthcare", "uhc"]),
    Vendor("Humana", "Medical", ["humana"]),
    Vendor("Quest Diagnostics", "Medical", ["quest diagnostics", "quest"]),
]


def learned_vendor_path() -> Path:
    return session_store.app_data_dir() / LEARNED_VENDOR_FILE


def normalize_key(text: str) -> str:
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def all_vendors() -> list[Vendor]:
    return [*SEED_VENDORS, *load_learned_vendors()]


def load_learned_vendors() -> list[Vendor]:
    path = learned_vendor_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    vendors: list[Vendor] = []
    for item in data.get("vendors", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        aliases = [str(a) for a in item.get("aliases", []) if str(a).strip()]
        vendors.append(Vendor(
            name=name,
            category=str(item.get("category", "Unsorted")),
            aliases=aliases[:MAX_ALIASES_PER_VENDOR],
            source="learned",
            count=int(item.get("count", 0) or 0),
        ))
    return vendors[:MAX_LEARNED_VENDORS]


def save_learned_vendors(vendors: list[Vendor]) -> Path:
    session_store.ensure_app_data_dir()
    vendors = sorted(vendors, key=lambda v: (-v.count, v.name.lower()))[:MAX_LEARNED_VENDORS]
    payload = {
        "schema": 1,
        "note": "Local learned vendor hints only. Safe to delete. Do not commit .local.",
        "vendors": [
            {
                "name": v.name,
                "category": v.category,
                "aliases": v.aliases[:MAX_ALIASES_PER_VENDOR],
                "count": v.count,
            }
            for v in vendors
        ],
    }
    path = learned_vendor_path()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def match_vendor(text: str, pdf: Path | None = None, strong_only: bool = False) -> Vendor | None:
    haystacks = []
    if pdf is not None:
        haystacks.append(normalize_key(pdf.stem))
        haystacks.append(normalize_key(str(pdf.parent)))
    haystacks.append(normalize_key(text[:4000] if strong_only else text))

    best: tuple[int, Vendor] | None = None
    for vendor in all_vendors():
        keys = [vendor.name, *vendor.aliases]
        for raw_key in keys:
            key = normalize_key(raw_key)
            if not key or len(key) < 3:
                continue
            score = 0
            for index, haystack in enumerate(haystacks):
                if key in haystack:
                    # Filename/path hits matter, but exact early-text hits matter too.
                    score = max(score, 100 - index * 10 + min(len(key), 20))
            if score and (best is None or score > best[0]):
                best = (score, vendor)
    return best[1] if best else None


def learn_from_rows(rows: list[dict[str, str]]) -> tuple[int, Path]:
    learned = {normalize_key(v.name): v for v in load_learned_vendors()}
    seed_keys = {normalize_key(v.name) for v in SEED_VENDORS}
    added_or_updated = 0

    for row in rows:
        sender = str(row.get("Sender", "")).strip()
        category = str(row.get("Category", "Unsorted")).strip() or "Unsorted"
        flags = str(row.get("Review Flags", "")).lower()
        notes = str(row.get("Notes", "")).lower()
        doc_type = str(row.get("Type", "")).lower()
        source = str(row.get("Source PDF", "")).strip()

        if not sender or len(sender) < 4:
            continue
        if "likely wrong sender" in flags or "manual sender review" in notes:
            continue
        if "unknown" in doc_type:
            continue
        key = normalize_key(sender)
        if not key or key in seed_keys:
            continue
        if key not in learned:
            learned[key] = Vendor(name=sender, category=category, aliases=[], source="learned", count=0)
            added_or_updated += 1
        learned[key].count += 1
        if source:
            alias = normalize_key(Path(source).stem.replace("_OCR", ""))
            if alias and alias not in [normalize_key(a) for a in learned[key].aliases]:
                learned[key].aliases.append(alias)

    path = save_learned_vendors(list(learned.values()))
    return added_or_updated, path


def database_summary() -> str:
    learned = load_learned_vendors()
    lines = [
        "Vendor Database",
        "===============",
        f"Seed vendors: {len(SEED_VENDORS)}",
        f"Learned vendors: {len(learned)}",
        f"Local learned file: {learned_vendor_path()}",
        "",
        "Seed Vendors",
        "------------",
    ]
    for vendor in sorted(SEED_VENDORS, key=lambda v: (v.category, v.name)):
        lines.append(f"- {vendor.name} [{vendor.category}] aliases: {', '.join(vendor.aliases[:5])}")
    if learned:
        lines.extend(["", "Learned Vendors", "---------------"])
        for vendor in learned:
            lines.append(f"- {vendor.name} [{vendor.category}] count={vendor.count} aliases: {', '.join(vendor.aliases[:5])}")
    return "\n".join(lines)
