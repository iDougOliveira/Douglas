from __future__ import annotations

import base64
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from templates_data import RANK_TEMPLATES_B64, SUIT_TEMPLATES_B64


RANK_SHAPE = (32, 32)
SUIT_SHAPE = (28, 28)
RANK_ORDER = "AKQJT98765432"
SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}


@dataclass(frozen=True)
class CardReading:
    code: str
    rank_score: float
    suit_score: float
    match_score: float


@dataclass(frozen=True)
class RegionReading:
    cards: tuple[CardReading, ...]
    slot_count: int
    occupied_slots: tuple[bool, ...]
    uncertain: bool

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(card.code for card in self.cards)


def _decode_templates(
    data: dict[str, list[str]],
    shape: tuple[int, int],
) -> dict[str, list[np.ndarray]]:
    total = shape[0] * shape[1]
    result: dict[str, list[np.ndarray]] = {}
    for label, items in data.items():
        decoded = []
        for item in items:
            raw = base64.b64decode(item)
            bits = np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:total]
            decoded.append(bits.reshape(shape).astype(np.uint8) * 255)
        result[label] = decoded
    return result


RANK_TEMPLATES = _decode_templates(RANK_TEMPLATES_B64, RANK_SHAPE)
SUIT_TEMPLATES = _decode_templates(SUIT_TEMPLATES_B64, SUIT_SHAPE)


def card_text(code: str) -> str:
    if not code or len(code) < 2:
        return "?"
    rank = "10" if code[0] == "T" else code[0]
    return rank + SUIT_SYMBOLS.get(code[1], "?")


def _similarity(a: np.ndarray, b: np.ndarray) -> float:
    aa = a > 0
    bb = b > 0
    inter = int(np.logical_and(aa, bb).sum())
    union = int(np.logical_or(aa, bb).sum())
    total = int(aa.sum() + bb.sum())
    if union == 0 or total == 0:
        return 0.0
    iou = inter / union
    dice = (2.0 * inter) / total
    return (iou + dice) / 2.0


def _normalize_component_mask(
    crop: np.ndarray,
    out_shape: tuple[int, int],
    *,
    keep_two: bool,
) -> np.ndarray:
    if crop.size == 0:
        return np.zeros(out_shape, dtype=np.uint8)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    mask = (gray < 205).astype(np.uint8) * 255
    if mask.shape[0] > 0:
        mask[:1, :] = 0
    if mask.shape[1] > 1:
        mask[:, :1] = 0
        mask[:, -1:] = 0

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    components: list[tuple[int, int, int, int, int, int]] = []
    for idx in range(1, count):
        x, y, width, height, area = (int(v) for v in stats[idx])
        if area >= 4:
            components.append((area, idx, x, y, width, height))

    if not components:
        return np.zeros(out_shape, dtype=np.uint8)

    components.sort(reverse=True)
    keep_ids = [components[0][1]]
    if keep_two and len(components) > 1:
        area1 = components[0][0]
        area2, idx2, x2, y2, _w2, h2 = components[1]
        if area2 / max(area1, 1) > 0.28 and y2 < 10 and h2 >= 8 and x2 < 16:
            keep_ids.append(idx2)

    selected = np.isin(labels, keep_ids).astype(np.uint8) * 255
    ys, xs = np.where(selected > 0)
    if not len(xs):
        return np.zeros(out_shape, dtype=np.uint8)

    glyph = selected[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    height, width = glyph.shape
    side = max(height, width) + 4
    canvas = np.zeros((side, side), dtype=np.uint8)
    oy = (side - height) // 2
    ox = (side - width) // 2
    canvas[oy:oy + height, ox:ox + width] = glyph
    return cv2.resize(
        canvas,
        (out_shape[1], out_shape[0]),
        interpolation=cv2.INTER_NEAREST,
    )


def _rank_glyph(card: np.ndarray) -> np.ndarray:
    height, width = card.shape[:2]
    crop = card[0:min(20, height), 1:min(20, width)]
    return _normalize_component_mask(crop, RANK_SHAPE, keep_two=True)


def _suit_glyph(card: np.ndarray) -> np.ndarray:
    height, width = card.shape[:2]
    crop = card[min(18, height):min(40, height), 1:min(15, width)]
    return _normalize_component_mask(crop, SUIT_SHAPE, keep_two=False)


def _is_red(card: np.ndarray) -> bool:
    height, width = card.shape[:2]
    roi = card[1:min(40, height), 1:min(14, width)]
    if roi.size == 0:
        return False
    blue, green, red = cv2.split(roi)
    red_pixels = (
        (red.astype(np.int16) - green.astype(np.int16) > 45)
        & (red.astype(np.int16) - blue.astype(np.int16) > 45)
        & (red > 110)
    )
    return float(red_pixels.mean()) > 0.02


def _best_template(
    glyph: np.ndarray,
    labels: list[str],
    bank: dict[str, list[np.ndarray]],
) -> tuple[str, float, float]:
    scored: list[tuple[float, str]] = []
    for label in labels:
        templates = bank.get(label, [])
        score = max(
            (_similarity(glyph, template) for template in templates),
            default=0.0,
        )
        scored.append((score, label))
    scored.sort(reverse=True)
    best_score, best_label = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    return best_label, best_score, best_score - second_score


def _recognize_card(card: np.ndarray) -> CardReading | None:
    rank, rank_score, rank_margin = _best_template(
        _rank_glyph(card),
        list(RANK_ORDER),
        RANK_TEMPLATES,
    )
    suit_labels = ["H", "D"] if _is_red(card) else ["S", "C"]
    suit, suit_score, suit_margin = _best_template(
        _suit_glyph(card),
        suit_labels,
        SUIT_TEMPLATES,
    )

    # Scores are template-match scores, not probabilities.
    if rank_score < 0.42 or rank_margin < 0.025:
        return None
    if suit_score < 0.48 or suit_margin < 0.025:
        return None

    return CardReading(
        code=rank + suit,
        rank_score=rank_score,
        suit_score=suit_score,
        match_score=(rank_score + suit_score) / 2.0,
    )


def _extract_slots(
    image_bgr: np.ndarray,
    slot_count: int,
) -> tuple[list[np.ndarray | None], tuple[bool, ...]]:
    height, width = image_bgr.shape[:2]
    if width < slot_count * 10 or height < 20:
        return [None] * slot_count, tuple(False for _ in range(slot_count))

    white = np.all(image_bgr > 170, axis=2)
    white_per_column = white.sum(axis=0)
    threshold = max(6, int(height * 0.22))

    slots: list[np.ndarray | None] = []
    occupied: list[bool] = []

    for index in range(slot_count):
        left = round(index * width / slot_count)
        right = round((index + 1) * width / slot_count)
        local = np.where(white_per_column[left:right] > threshold)[0]

        if len(local) == 0:
            slots.append(None)
            occupied.append(False)
            continue

        first = left + int(local[0])
        if first - left > (right - left) * 0.55:
            slots.append(None)
            occupied.append(False)
            continue

        x0 = max(0, first - 1)
        card_width = min(59, width - x0)
        slots.append(image_bgr[:, x0:x0 + card_width])
        occupied.append(True)

    return slots, tuple(occupied)


def recognize_region(image: Image.Image, slot_count: int) -> RegionReading:
    rgb = np.asarray(image.convert("RGB"))
    image_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    slots, occupied = _extract_slots(image_bgr, slot_count)

    readings: list[CardReading] = []
    uncertain = False
    seen_gap = False

    for present, slot in zip(occupied, slots):
        if not present:
            seen_gap = True
            continue

        if seen_gap:
            # Hole cards and community cards fill from left to right.
            uncertain = True

        assert slot is not None
        reading = _recognize_card(slot)
        if reading is None:
            uncertain = True
            continue
        readings.append(reading)

    if sum(occupied) != len(readings):
        uncertain = True

    return RegionReading(
        cards=tuple(readings),
        slot_count=slot_count,
        occupied_slots=occupied,
        uncertain=uncertain,
    )


def recognize_hand(image: Image.Image) -> RegionReading:
    return recognize_region(image, 2)


def recognize_board(image: Image.Image) -> RegionReading:
    return recognize_region(image, 5)


def street_from_board(reading: RegionReading) -> str:
    count = sum(reading.occupied_slots)
    if reading.uncertain:
        return "INCERTO"
    if count == 0:
        return "PRÉ-FLOP"
    if count == 3:
        return "FLOP"
    if count == 4:
        return "TURN"
    if count == 5:
        return "RIVER"
    return "TRANSIÇÃO"
