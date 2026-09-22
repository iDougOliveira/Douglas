from __future__ import annotations

"""OCR isolated from card recognition.

This module only estimates how many seats are active by looking for explicit
PokerStars inactive-seat labels such as "Ausente" and "Lugar Vazio".
It never imports or modifies the card recognizer.
"""

from collections import defaultdict
import math
import unicodedata


def fold_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.upper().split())


def is_inactive_label(text: str) -> bool:
    folded = fold_text(text)
    # PokerStars has a local control "Ausente na próxima mão"; it is not a
    # seat state and must never reduce the table count.
    if "PROXIMA" in folded and "MAO" in folded:
        return False
    if "FICAR DE FORA" in folded:
        return False
    return "AUSENT" in folded or "VAZIO" in folded


def cluster_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Merge OCR fragments that belong to the same seat label."""
    clusters: list[list[tuple[float, float]]] = []
    for point in points:
        for cluster in clusters:
            cx = sum(p[0] for p in cluster) / len(cluster)
            cy = sum(p[1] for p in cluster) / len(cluster)
            if abs(point[0] - cx) <= 0.13 and abs(point[1] - cy) <= 0.12:
                cluster.append(point)
                break
        else:
            clusters.append([point])
    return [
        (
            sum(p[0] for p in cluster) / len(cluster),
            sum(p[1] for p in cluster) / len(cluster),
        )
        for cluster in clusters
    ]


def infer_player_count(max_seats: int, inactive_count: int) -> int | None:
    try:
        max_seats = int(max_seats)
        inactive_count = int(inactive_count)
    except (TypeError, ValueError):
        return None
    if not 2 <= max_seats <= 10:
        return None
    if inactive_count < 0 or inactive_count > max_seats:
        return None
    active = max_seats - inactive_count
    return active if 2 <= active <= 10 else None


def _perimeter_line(cx: float, cy: float, width: float, height: float) -> bool:
    if width <= 0 or height <= 0:
        return False
    nx = cx / width
    ny = cy / height
    # Ignore the central felt/board and the very bottom controls/chat. Seat
    # labels live around the table perimeter.
    if ny >= 0.87:
        return False
    return nx <= 0.37 or nx >= 0.63 or ny <= 0.30 or ny >= 0.60


def analyze_table(image, max_seats: int = 9) -> dict:
    """OCR one calibrated table crop and estimate active seats.

    The count is deliberately conservative: it subtracts only explicit
    "Ausente"/"Lugar Vazio" labels from the configured maximum seats.
    """
    try:
        max_seats = int(max_seats)
    except (TypeError, ValueError):
        return {"valid": False, "error": "Máximo de lugares inválido."}
    if not 2 <= max_seats <= 10:
        return {"valid": False, "error": "Máximo de lugares deve ficar entre 2 e 10."}

    # Lazy import keeps the pure helpers testable in CI without requiring the
    # Windows OCR dependencies at import time.
    import numeric_ocr

    if not numeric_ocr.available():
        return {
            "valid": False,
            "error": numeric_ocr.OCR_ERROR or "Tesseract indisponível",
        }

    processed = numeric_ocr.preprocess(image, scale=2)
    pytesseract = numeric_ocr.pytesseract
    data = pytesseract.image_to_data(
        processed,
        config="--oem 3 --psm 11",
        lang="eng",
        output_type=pytesseract.Output.DICT,
    )

    width, height = processed.size
    grouped: dict[tuple[int, int, int], list[dict]] = defaultdict(list)
    evidence_words = 0

    count = len(data.get("text", []))
    for i in range(count):
        text = str(data["text"][i] or "").strip()
        if not text:
            continue
        try:
            confidence = float(data["conf"][i])
        except (TypeError, ValueError):
            confidence = -1
        if confidence < 18:
            continue

        left = int(data["left"][i])
        top = int(data["top"][i])
        w = int(data["width"][i])
        h = int(data["height"][i])
        cx = left + w / 2
        cy = top + h / 2
        if not _perimeter_line(cx, cy, width, height):
            continue

        evidence_words += 1
        key = (
            int(data.get("block_num", [0] * count)[i]),
            int(data.get("par_num", [0] * count)[i]),
            int(data.get("line_num", [i] * count)[i]),
        )
        grouped[key].append(
            {"text": text, "left": left, "top": top, "width": w, "height": h}
        )

    lines: list[dict] = []
    inactive_points: list[tuple[float, float]] = []
    for words in grouped.values():
        words.sort(key=lambda item: item["left"])
        line_text = " ".join(item["text"] for item in words)
        left = min(item["left"] for item in words)
        top = min(item["top"] for item in words)
        right = max(item["left"] + item["width"] for item in words)
        bottom = max(item["top"] + item["height"] for item in words)
        cx = (left + right) / 2
        cy = (top + bottom) / 2
        lines.append({"text": line_text, "x": cx / width, "y": cy / height})
        if is_inactive_label(line_text):
            inactive_points.append((cx / width, cy / height))

    inactive_clusters = cluster_points(inactive_points)
    inactive_count = min(len(inactive_clusters), max_seats)
    player_count = infer_player_count(max_seats, inactive_count)

    # Do not publish a count from a crop where OCR effectively saw no seat
    # text. This prevents a blank/covered window from becoming max_seats.
    min_evidence = max(2, min(5, max_seats // 2))
    valid = player_count is not None and evidence_words >= min_evidence

    confidence = "alta" if evidence_words >= max(5, max_seats) else "média"
    raw = " | ".join(line["text"] for line in lines)[:320]

    return {
        "valid": valid,
        "player_count": player_count if valid else None,
        "max_seats": max_seats,
        "inactive_seats": inactive_count,
        "inactive_points": [
            [round(float(x), 4), round(float(y), 4)]
            for x, y in inactive_clusters[:10]
        ],
        "evidence_words": evidence_words,
        "confidence": confidence if valid else "baixa",
        "raw_text": raw,
    }
