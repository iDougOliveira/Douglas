from __future__ import annotations

import re
from PIL import Image

from numeric_ocr import OCR_ERROR, ocr_text


def _decimal(token: str) -> float | None:
    token = str(token or "").strip().replace(" ", "")
    token = token.replace(",", ".")
    token = re.sub(r"[^0-9.]", "", token)
    if not token:
        return None
    if token.count(".") > 1:
        parts = token.split(".")
        token = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(token)
    except ValueError:
        return None


def _chips(token: str) -> float | None:
    raw = str(token or "").strip().upper().replace(" ", "")
    mult = 1.0
    if raw.endswith("K"):
        mult = 1_000.0
        raw = raw[:-1]
    elif raw.endswith("M"):
        mult = 1_000_000.0
        raw = raw[:-1]
    value = _decimal(raw)
    return None if value is None else value * mult


def parse_tournament_hud_text(text: str) -> dict:
    raw = " ".join(str(text or "").replace("\n", " ").split())
    normalized = (
        raw.replace("O", "0")
        .replace("o", "0")
        .replace("º", "o")
        .replace("°", "o")
        .replace("|", "/")
    )

    result = {
        "valid": False,
        "rank": None,
        "remaining": None,
        "avg_stack_bb": None,
        "small_blind": None,
        "big_blind": None,
        "ante": None,
        "level_seconds": None,
        "raw_text": raw[:400],
    }

    rank_match = re.search(
        r"\b(\d{1,5})\s*[oª]?\s*(?:de|/ )?\s*(\d{1,6})\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if rank_match and "de" in normalized.lower():
        rank = int(rank_match.group(1))
        remaining = int(rank_match.group(2))
        if 1 <= rank <= remaining <= 1_000_000:
            result["rank"] = rank
            result["remaining"] = remaining

    avg_match = re.search(
        r"m[eé]dia\D{0,8}(\d{1,6}(?:[.,]\d{1,2})?)\s*bb\b",
        raw,
        flags=re.IGNORECASE,
    )
    if avg_match:
        result["avg_stack_bb"] = _decimal(avg_match.group(1))

    blinds_match = re.search(
        r"(?<!\d)(\d[\d.,]*\s*[kKmM]?)\s*/\s*"
        r"(\d[\d.,]*\s*[kKmM]?)"
        r"(?:\s*\(\s*(\d[\d.,]*\s*[kKmM]?)\s*\))?",
        raw,
    )
    if blinds_match:
        sb = _chips(blinds_match.group(1))
        bb = _chips(blinds_match.group(2))
        ante = _chips(blinds_match.group(3)) if blinds_match.group(3) else None
        if sb is not None and bb is not None and 0 < sb <= bb:
            result["small_blind"] = sb
            result["big_blind"] = bb
            result["ante"] = ante

    time_match = re.search(r"\b(\d{1,2}):(\d{2})\b", raw)
    if time_match:
        minutes = int(time_match.group(1))
        seconds = int(time_match.group(2))
        if 0 <= minutes <= 99 and 0 <= seconds <= 59:
            result["level_seconds"] = minutes * 60 + seconds

    useful = sum(
        result[key] is not None
        for key in ("remaining", "avg_stack_bb", "big_blind", "level_seconds")
    )
    result["valid"] = useful >= 2
    return result


def analyze_tournament_hud(image: Image.Image) -> dict:
    if OCR_ERROR:
        return {"valid": False, "error": OCR_ERROR, "raw_text": ""}
    text = ocr_text(image, numeric_only=False, multiline=True)
    return parse_tournament_hud_text(text)
