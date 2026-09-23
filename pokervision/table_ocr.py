from __future__ import annotations

"""OCR isolated from card recognition.

This module only estimates how many seats are active by looking for explicit
PokerStars inactive-seat labels such as "Ausente" and "Lugar Vazio".
It never imports or modifies the card recognizer.
"""

from collections import defaultdict
import math
import re
import unicodedata


def fold_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.upper().split())


SEAT_LAYOUTS = {
    2: [(0.50, 0.88), (0.50, 0.11)],
    3: [(0.50, 0.88), (0.16, 0.28), (0.84, 0.28)],
    4: [(0.50, 0.88), (0.10, 0.50), (0.50, 0.10), (0.90, 0.50)],
    5: [(0.50, 0.88), (0.13, 0.66), (0.18, 0.20), (0.82, 0.20), (0.87, 0.66)],
    6: [(0.50, 0.88), (0.13, 0.68), (0.12, 0.29), (0.50, 0.10), (0.88, 0.29), (0.87, 0.68)],
    7: [(0.50, 0.88), (0.16, 0.72), (0.09, 0.43), (0.22, 0.16), (0.78, 0.16), (0.91, 0.43), (0.84, 0.72)],
    8: [(0.50, 0.88), (0.16, 0.72), (0.08, 0.45), (0.18, 0.18), (0.50, 0.09), (0.82, 0.18), (0.92, 0.45), (0.84, 0.72)],
    9: [(0.50, 0.88), (0.18, 0.73), (0.08, 0.49), (0.13, 0.24), (0.34, 0.10), (0.66, 0.10), (0.87, 0.24), (0.92, 0.49), (0.82, 0.73)],
    10: [(0.50, 0.88), (0.20, 0.75), (0.08, 0.56), (0.09, 0.31), (0.26, 0.13), (0.50, 0.08), (0.74, 0.13), (0.91, 0.31), (0.92, 0.56), (0.80, 0.75)],
}


def nearest_seat_index(x: float, y: float, max_seats: int) -> tuple[int | None, float]:
    layout = SEAT_LAYOUTS.get(int(max_seats), SEAT_LAYOUTS[9])
    best_index = None
    best_distance = float("inf")
    for index, (sx, sy) in enumerate(layout):
        distance = math.hypot(float(x) - sx, float(y) - sy)
        if distance < best_distance:
            best_index = index
            best_distance = distance
    return best_index, best_distance


def is_inactive_label(text: str) -> bool:
    folded = fold_text(text)
    # PokerStars has a local control "Ausente na próxima mão"; it is not a
    # seat state and must never reduce the table count.
    if "PROXIMA" in folded and "MAO" in folded:
        return False
    if "FICAR DE FORA" in folded:
        return False
    return "AUSENT" in folded or "VAZIO" in folded


def is_disconnected_label(text: str) -> bool:
    folded = fold_text(text)
    return "DESCONECT" in folded


def parse_stack_bb(text: str) -> float | None:
    folded = fold_text(text).replace(",", ".")
    match = re.search(r"(?<![0-9])(\d{1,5}(?:\.\d{1,2})?)\s*BB\b", folded)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value if 0 <= value <= 100000 else None


def plausible_name(text: str) -> bool:
    folded = fold_text(text)
    if not folded or len(folded) < 2 or len(folded) > 32:
        return False
    blocked = (
        "POTE", "JOGO RESPONSAVEL", "RECONHECIMENTO", "PROXIMA MAO",
        "BIG BLIND", "DESISTIR", "APOSTA", "AUMENTO", "PAGO",
        "MIN", "MAX", "BB", "ET",
    )
    if any(token in folded for token in blocked):
        return False
    if is_inactive_label(folded) or is_disconnected_label(folded):
        return False
    letters = sum(ch.isalpha() for ch in folded)
    return letters >= 2


def parse_action_text(text: str) -> str:
    folded = fold_text(text)
    if "ALL IN" in folded or "ALL-IN" in folded:
        return "ALL-IN"
    if "DESIST" in folded:
        return "FOLD"
    if "AUMENT" in folded or "RE-RAISE" in folded or "RERAISE" in folded:
        return "RAISE"
    if "PAGO" in folded or "PAGOU" in folded:
        return "CALL"
    if "APOST" in folded:
        return "BET"
    if "PASSO" in folded or "PASSOU" in folded:
        return "CHECK"
    return ""


def _nearest_inward_bet(
    sx: float,
    sy: float,
    all_lines: list[dict],
    stack_line: dict,
) -> float | None:
    """Find a BB amount between one seat plaque and the table center."""
    cx, cy = 0.50, 0.46
    vx, vy = cx - sx, cy - sy
    length = math.hypot(vx, vy)
    if length <= 0.01:
        return None
    ux, uy = vx / length, vy / length

    candidates = []
    for line in all_lines:
        if line is stack_line:
            continue
        text = str(line.get("text", ""))
        if "POTE" in fold_text(text):
            continue
        value = parse_stack_bb(text)
        if value is None:
            continue
        x, y = float(line["x"]), float(line["y"])
        dx, dy = x - sx, y - sy
        projection = dx * ux + dy * uy
        if projection <= 0.045 or projection >= min(0.34, length * 0.92):
            continue
        perpendicular = abs(dx * uy - dy * ux)
        if perpendicular > 0.085:
            continue
        candidates.append((projection + perpendicular * 1.8, value))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _nearby_action(
    sx: float,
    sy: float,
    all_lines: list[dict],
) -> str:
    candidates = []
    for line in all_lines:
        action = parse_action_text(str(line.get("text", "")))
        if not action:
            continue
        x, y = float(line["x"]), float(line["y"])
        dx, dy = x - sx, y - sy
        if abs(dx) <= 0.18 and abs(dy) <= 0.16:
            candidates.append((dx * dx + dy * dy, action))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def build_seat_observations(
    lines: list[dict],
    all_lines: list[dict] | None = None,
    max_seats: int = 9,
) -> list[dict]:
    """Extract seat stacks conservatively and pin them to physical seats.

    Names/actions are diagnostic only. Stack identity is based on the nearest
    physical seat, so dim/folded text cannot make another stack slide into it.
    """
    all_lines = all_lines or lines
    observations: list[dict] = []

    for line in lines:
        text = str(line.get("text", ""))
        folded = fold_text(text)
        stack = parse_stack_bb(text)
        action = parse_action_text(text)
        if stack is None and not action:
            continue
        if "POTE" in folded:
            continue

        sx = float(line["x"])
        sy = float(line["y"])
        seat_index, seat_distance = nearest_seat_index(sx, sy, max_seats)
        if seat_index is None or seat_distance > 0.145:
            continue

        name = ""
        if stack is not None:
            inline_name = re.sub(
                r"\d{1,5}(?:[.,]\d{1,2})?\s*BB\b",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip(" -|")
            if plausible_name(inline_name):
                name = inline_name

        if not name:
            candidates = []
            for candidate in lines:
                if candidate is line or not plausible_name(candidate["text"]):
                    continue
                dx = float(candidate["x"]) - sx
                dy = float(candidate["y"]) - sy
                if abs(dx) <= 0.15 and abs(dy) <= 0.13:
                    score = (dx * dx) + (dy * dy * 1.8)
                    candidates.append((score, candidate["text"]))
            if candidates:
                candidates.sort(key=lambda item: item[0])
                name = str(candidates[0][1]).strip()

        nearby_text = []
        for candidate in lines:
            dx = float(candidate["x"]) - sx
            dy = float(candidate["y"]) - sy
            if abs(dx) <= 0.14 and abs(dy) <= 0.12:
                nearby_text.append(str(candidate["text"]))
        joined = " ".join(nearby_text)
        status = "active"
        if is_inactive_label(joined):
            status = "inactive"
        elif is_disconnected_label(joined):
            status = "disconnected"

        bet_bb = _nearest_inward_bet(sx, sy, all_lines, line)
        detected_action = action or _nearby_action(sx, sy, all_lines)
        if detected_action == "ALL-IN":
            status = "active"

        observations.append({
            "seat_index": int(seat_index),
            "seat_distance": round(float(seat_distance), 4),
            "x": round(sx, 4),
            "y": round(sy, 4),
            "name": name[:32],
            "stack_bb": stack,
            "bet_bb": bet_bb,
            "action": detected_action or "unknown",
            "status": status,
            "raw": text[:80],
        })

    # Exactly one record per physical seat. Prefer a readable stack, then the
    # observation geometrically closest to that seat.
    by_seat: dict[int, dict] = {}
    for obs in observations:
        seat = int(obs["seat_index"])
        existing = by_seat.get(seat)
        if existing is None:
            by_seat[seat] = obs
            continue

        existing_has_stack = existing.get("stack_bb") is not None
        new_has_stack = obs.get("stack_bb") is not None
        replace = (
            (new_has_stack and not existing_has_stack)
            or (
                new_has_stack == existing_has_stack
                and float(obs["seat_distance"]) < float(existing["seat_distance"])
            )
        )
        if replace:
            keep = obs
            other = existing
        else:
            keep = existing
            other = obs

        if not keep.get("name") and other.get("name"):
            keep["name"] = other["name"]
        if keep.get("bet_bb") is None and other.get("bet_bb") is not None:
            keep["bet_bb"] = other["bet_bb"]
        if str(keep.get("action", "unknown")).upper() == "UNKNOWN":
            if str(other.get("action", "unknown")).upper() != "UNKNOWN":
                keep["action"] = other["action"]
        by_seat[seat] = keep

    return [by_seat[index] for index in sorted(by_seat)][:10]

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
        key = (
            int(data.get("block_num", [0] * count)[i]),
            int(data.get("par_num", [0] * count)[i]),
            int(data.get("line_num", [i] * count)[i]),
        )
        grouped[key].append(
            {"text": text, "left": left, "top": top, "width": w, "height": h}
        )

    all_lines: list[dict] = []
    for words in grouped.values():
        words.sort(key=lambda item: item["left"])
        line_text = " ".join(item["text"] for item in words)
        left = min(item["left"] for item in words)
        top = min(item["top"] for item in words)
        right = max(item["left"] + item["width"] for item in words)
        bottom = max(item["top"] + item["height"] for item in words)
        cx = (left + right) / 2
        cy = (top + bottom) / 2
        all_lines.append({
            "text": line_text,
            "x": cx / width,
            "y": cy / height,
        })

    lines = [
        line for line in all_lines
        if _perimeter_line(
            float(line["x"]) * width,
            float(line["y"]) * height,
            width,
            height,
        )
    ]
    evidence_words = sum(
        max(1, len(str(line["text"]).split()))
        for line in lines
    )
    inactive_points: list[tuple[float, float]] = []
    for line in lines:
        if is_inactive_label(line["text"]):
            inactive_points.append((float(line["x"]), float(line["y"])))

    inactive_clusters = cluster_points(inactive_points)
    inactive_seat_indices = []
    for x, y in inactive_clusters:
        seat_index, seat_distance = nearest_seat_index(x, y, max_seats)
        if (
            seat_index is not None
            and seat_distance <= 0.145
            and seat_index not in inactive_seat_indices
        ):
            inactive_seat_indices.append(int(seat_index))
    inactive_seat_indices.sort()
    inactive_count = min(len(inactive_seat_indices), max_seats)
    player_count = infer_player_count(max_seats, inactive_count)

    # Do not publish a count from a crop where OCR effectively saw no seat
    # text. This prevents a blank/covered window from becoming max_seats.
    min_evidence = max(2, min(5, max_seats // 2))
    valid = player_count is not None and evidence_words >= min_evidence

    confidence = "alta" if evidence_words >= max(5, max_seats) else "média"
    raw = " | ".join(line["text"] for line in lines)[:320]
    seat_observations = build_seat_observations(
        lines,
        all_lines,
        max_seats=max_seats,
    )
    table_pot_bb = None
    for line in all_lines:
        if "POTE" not in fold_text(str(line.get("text", ""))):
            continue
        value = parse_stack_bb(str(line.get("text", "")))
        if value is not None:
            table_pot_bb = value
            break

    return {
        "valid": valid,
        "player_count": player_count if valid else None,
        "max_seats": max_seats,
        "inactive_seats": inactive_count,
        "inactive_seat_indices": inactive_seat_indices,
        "inactive_points": [
            [round(float(x), 4), round(float(y), 4)]
            for x, y in inactive_clusters[:10]
        ],
        "seat_observations": seat_observations,
        "table_pot_bb": table_pot_bb,
        "evidence_words": evidence_words,
        "confidence": confidence if valid else "baixa",
        "raw_text": raw,
    }
