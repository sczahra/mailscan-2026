from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OcrSummary:
    source_name: str
    source_folder: str
    page_count: int
    preview_pages: int
    total_words: int
    quality: str
    blank_pages: list[int]
    low_text_pages: list[int]
    duplex_pattern: str
    document_type: str
    tracking_numbers: list[str]
    likely_dates: list[str]
    suspicious_dates: list[str]
    amounts: list[str]
    names: list[str]
    addresses: list[str]


def count_words(text: str) -> int:
    return len(re.findall(r"\b[A-Za-z0-9][A-Za-z0-9'/-]*\b", text))


def estimate_ocr_quality(total_words: int, page_count: int, low_text_pages: list[int]) -> str:
    if page_count <= 0 or total_words == 0:
        return "Weak / image-only"

    words_per_page = total_words / page_count
    low_ratio = len(low_text_pages) / page_count

    if words_per_page >= 80 and low_ratio <= 0.30:
        return "Good"
    if words_per_page >= 25 and low_ratio <= 0.60:
        return "Fair"
    return "Weak / needs review"


def detect_duplex_pattern(page_count: int, blank_pages: list[int]) -> str:
    if page_count < 4 or not blank_pages:
        return "None detected"

    even_pages = set(range(2, page_count + 1, 2))
    odd_pages = set(range(1, page_count + 1, 2))
    blank_set = set(blank_pages)

    even_blank_ratio = len(blank_set & even_pages) / max(len(even_pages), 1)
    odd_blank_ratio = len(blank_set & odd_pages) / max(len(odd_pages), 1)

    if even_blank_ratio >= 0.75 and odd_blank_ratio <= 0.25:
        return "Likely blank backsides from duplex scanning"
    if odd_blank_ratio >= 0.75 and even_blank_ratio <= 0.25:
        return "Likely alternating blank pages from duplex scanning"
    return "Mixed blank pages"


def detect_document_type(text: str) -> str:
    lower = text.lower()

    usps_signals = [
        "united states postal service",
        "unitep states postat service",
        "usps tracking",
        "ps form 3849",
        "we missed you",
        "final notice",
        "redelivery",
    ]
    if sum(1 for signal in usps_signals if signal in lower) >= 2:
        return "USPS Notice / Certified Mail Notice"

    if "amount due" in lower and ("due date" in lower or "payment" in lower):
        return "Bill / Statement"

    if "explanation of benefits" in lower or "patient" in lower or "insurance" in lower:
        return "Medical / Insurance"

    if "tax" in lower and ("irs" in lower or "department of taxation" in lower):
        return "Tax / Government"

    return "Unknown"


def find_tracking_numbers(text: str) -> list[str]:
    matches = re.findall(r"\b(?:9\d{19,21}|\d{20,22})\b", text)
    return unique_limited(matches, 10)


def find_dates(text: str) -> tuple[list[str], list[str]]:
    patterns = [
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    ]

    raw_matches: list[str] = []
    for pattern in patterns:
        raw_matches.extend(re.findall(pattern, text, flags=re.IGNORECASE))

    matches = unique_limited(raw_matches, 20)
    likely: list[str] = []
    suspicious: list[str] = []

    years = [_extract_year(value) for value in matches]
    years = [year for year in years if year is not None]
    common_year = _most_common_year(years)

    for value in matches:
        year = _extract_year(value)
        if year is None:
            likely.append(value)
            continue
        if common_year and abs(year - common_year) >= 2:
            suspicious.append(value)
        elif year < 1990 or year > 2100:
            suspicious.append(value)
        else:
            likely.append(value)

    return unique_limited(likely, 12), unique_limited(suspicious, 8)


def find_amounts(text: str) -> list[str]:
    matches = re.findall(r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?", text)
    return unique_limited(matches, 12)


def find_names(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates: list[str] = []

    skip_words = {
        "UNITED", "STATES", "POSTAL", "SERVICE", "TODAY", "SENDER", "NOTICE",
        "DELIVERY", "SECTION", "FARMVILLE", "ADDRESS", "SIGNATURE", "ARTICLE",
        "AMOUNT", "RETURN", "RECEIPT", "CUSTOMER", "REDLIVER", "REDELIVER",
    }

    for line in lines:
        clean = re.sub(r"[^A-Za-z .'-]", "", line).strip()
        clean = re.sub(r"\s+", " ", clean)
        words = clean.split()
        if not 2 <= len(words) <= 5:
            continue
        upper_words = [word.upper().strip(".'-") for word in words]
        if any(word in skip_words for word in upper_words):
            continue
        if sum(1 for word in words if word[:1].isupper()) < 2:
            continue
        if any(len(word) <= 1 for word in words):
            continue
        candidates.append(clean.upper())

    return unique_limited(candidates, 10)


def find_addresses(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    addresses: list[str] = []

    street_pattern = re.compile(
        r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+\s+(?:RD|ROAD|ST|STREET|AVE|AVENUE|DR|DRIVE|LN|LANE|CT|COURT|BLVD|WAY)\b",
        re.IGNORECASE,
    )
    city_state_zip_pattern = re.compile(r"\b[A-Z][A-Z .'-]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b")

    for index, line in enumerate(lines):
        street_match = street_pattern.search(line)
        if not street_match:
            continue
        street = street_match.group(0).upper()
        city_line = ""
        for lookahead in lines[index + 1:index + 4]:
            city_match = city_state_zip_pattern.search(lookahead.upper())
            if city_match:
                city_line = city_match.group(0).upper()
                break
        if city_line:
            addresses.append(f"{street}, {city_line}")
        else:
            addresses.append(street)

    return unique_limited(addresses, 10)


def build_summary(
    pdf: Path,
    page_count: int,
    preview_pages: int,
    page_texts: list[str],
    page_word_counts: list[int],
) -> OcrSummary:
    full_text = "\n".join(page_texts)
    total_words = sum(page_word_counts)
    low_text_pages = [i + 1 for i, count in enumerate(page_word_counts) if count < 8]
    blank_pages = [i + 1 for i, count in enumerate(page_word_counts) if count == 0]
    likely_dates, suspicious_dates = find_dates(full_text)

    return OcrSummary(
        source_name=pdf.name,
        source_folder=str(pdf.parent),
        page_count=page_count,
        preview_pages=preview_pages,
        total_words=total_words,
        quality=estimate_ocr_quality(total_words, page_count, low_text_pages),
        blank_pages=blank_pages,
        low_text_pages=low_text_pages,
        duplex_pattern=detect_duplex_pattern(page_count, blank_pages),
        document_type=detect_document_type(full_text),
        tracking_numbers=find_tracking_numbers(full_text),
        likely_dates=likely_dates,
        suspicious_dates=suspicious_dates,
        amounts=find_amounts(full_text),
        names=find_names(full_text),
        addresses=find_addresses(full_text),
    )


def render_summary(summary: OcrSummary) -> str:
    return "\n".join([
        "OCR / TEXT PREVIEW SUMMARY",
        "=" * 80,
        f"Source: {summary.source_name}",
        f"Folder: {summary.source_folder}",
        f"Pages: {summary.page_count}",
        f"Preview shown: first {summary.preview_pages} page(s)",
        f"Total extracted words: {summary.total_words}",
        f"OCR Quality: {summary.quality}",
        f"Document Type Guess: {summary.document_type}",
        f"Blank pages: {page_list_preview(summary.blank_pages)}",
        f"Low-text pages: {page_list_preview(summary.low_text_pages)}",
        f"Blank-page pattern: {summary.duplex_pattern}",
        "",
        value_list_preview("Possible tracking / article numbers", summary.tracking_numbers),
        "",
        value_list_preview("Possible dates", summary.likely_dates),
        "",
        value_list_preview("Suspicious OCR dates", summary.suspicious_dates),
        "",
        value_list_preview("Possible dollar amounts", summary.amounts),
        "",
        value_list_preview("Possible people / entities", summary.names),
        "",
        value_list_preview("Possible addresses", summary.addresses),
        "",
        "Note: This is a helper summary, not a final classification. Review the source PDF before relying on extracted details.",
    ])


def unique_limited(values: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        clean = " ".join(str(value).split())
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            output.append(clean)
        if len(output) >= limit:
            break
    return output


def page_list_preview(pages: list[int], limit: int = 12) -> str:
    if not pages:
        return "None detected"
    shown = ", ".join(str(page) for page in pages[:limit])
    if len(pages) > limit:
        shown += f", +{len(pages) - limit} more"
    return shown


def value_list_preview(label: str, values: list[str]) -> str:
    if not values:
        return f"{label}: None detected"
    lines = [f"{label}:"]
    lines.extend(f"- {value}" for value in values)
    return "\n".join(lines)


def _extract_year(value: str) -> int | None:
    match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", value)
    if match:
        return int(match.group(1))

    slash_match = re.search(r"\b\d{1,2}/\d{1,2}/(\d{2})\b", value)
    if slash_match:
        short_year = int(slash_match.group(1))
        return 2000 + short_year if short_year < 70 else 1900 + short_year

    return None


def _most_common_year(years: list[int]) -> int | None:
    if not years:
        return None
    counts: dict[int, int] = {}
    for year in years:
        counts[year] = counts.get(year, 0) + 1
    return max(counts, key=counts.get)
