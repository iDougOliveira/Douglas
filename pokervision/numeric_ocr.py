from __future__ import annotations

import re
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None


COMMON_TESSERACT_PATHS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


def configure_tesseract() -> str | None:
    if pytesseract is None:
        return "pytesseract não instalado"
    exe = shutil.which("tesseract")
    if exe:
        pytesseract.pytesseract.tesseract_cmd = exe
        return None
    for path in COMMON_TESSERACT_PATHS:
        if path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(path)
            return None
    return "Tesseract OCR não instalado no Windows"


OCR_ERROR = configure_tesseract()


def available() -> bool:
    return OCR_ERROR is None


def preprocess(image: Image.Image, scale: int = 4) -> Image.Image:
    gray = np.asarray(image.convert("L"))
    gray = cv2.resize(
        gray,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC,
    )
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Poker clients normally draw light text on a dark table/UI. Tesseract is
    # more reliable with dark text on a white background.
    if float(gray.mean()) < 145:
        binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )[1]
    else:
        binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]

    binary = cv2.copyMakeBorder(
        binary, 20, 20, 20, 20,
        cv2.BORDER_CONSTANT,
        value=255,
    )
    return Image.fromarray(binary)


def ocr_text(
    image: Image.Image,
    *,
    numeric_only: bool = False,
    multiline: bool = False,
) -> str:
    if not available():
        raise RuntimeError(OCR_ERROR or "OCR indisponível")
    processed = preprocess(image)
    psm = 6 if multiline else 7
    config = f"--oem 3 --psm {psm}"
    if numeric_only:
        config += " -c tessedit_char_whitelist=0123456789.,/kKmM"
    text = pytesseract.image_to_string(
        processed,
        config=config,
        lang="eng",
    )
    return " ".join(text.replace("\n", " ").split())


def _number(token: str) -> float | None:
    token = token.strip().replace(" ", "")
    if not token:
        return None

    multiplier = 1.0
    if token[-1:].lower() == "k":
        multiplier = 1_000.0
        token = token[:-1]
    elif token[-1:].lower() == "m":
        multiplier = 1_000_000.0
        token = token[:-1]

    token = re.sub(r"[^0-9.,]", "", token)
    if not token:
        return None

    # Poker chip displays commonly use 1,250 or 1.250 as a thousands
    # separator. Preserve an actual decimal when the suffix is K/M.
    if "," in token and "." in token:
        last = max(token.rfind(","), token.rfind("."))
        integer = re.sub(r"[^0-9]", "", token[:last])
        fraction = re.sub(r"[^0-9]", "", token[last + 1:])
        normalized = integer + ("." + fraction if fraction else "")
    elif "," in token or "." in token:
        sep = "," if "," in token else "."
        pieces = token.split(sep)
        if len(pieces) > 2:
            normalized = "".join(pieces)
        elif len(pieces) == 2 and len(pieces[1]) == 3 and multiplier == 1:
            normalized = "".join(pieces)
        else:
            normalized = pieces[0] + ("." + pieces[1] if pieces[1] else "")
    else:
        normalized = token

    try:
        return float(normalized) * multiplier
    except ValueError:
        return None


def extract_numbers(text: str) -> list[float]:
    # Mild OCR corrections only inside numeric-looking tokens.
    cleaned = text.replace("O", "0").replace("o", "0")
    tokens = re.findall(r"\d[\d.,]*\s*[kKmM]?", cleaned)
    values = [_number(token) for token in tokens]
    return [value for value in values if value is not None]


def read_blinds(image: Image.Image) -> dict:
    text = ocr_text(image, numeric_only=False)
    normalized = (
        text.replace("O", "0")
        .replace("o", "0")
        .replace("|", "/")
    )

    slash = re.search(
        r"(\d[\d.,]*)\s*/\s*(\d[\d.,]*)",
        normalized,
    )
    values = extract_numbers(normalized)

    if slash:
        small = _number(slash.group(1))
        big = _number(slash.group(2))
    elif len(values) >= 2:
        small, big = values[0], values[1]
    else:
        return {"text": text, "small": None, "big": None, "ante": None}

    ante = None
    ante_match = re.search(
        r"ante\D*(\d[\d.,]*)",
        normalized,
        flags=re.IGNORECASE,
    )
    if ante_match:
        ante = _number(ante_match.group(1))
    elif len(values) >= 3:
        ante = values[-1]

    if small is not None and big is not None and small > big:
        small, big = big, small

    return {
        "text": text,
        "small": small,
        "big": big,
        "ante": ante,
    }


def read_single_number(image: Image.Image) -> dict:
    # Do not whitelist here: the BB suffix is valuable because some poker
    # clients already display stack/pot directly in big blinds.
    text = ocr_text(image, numeric_only=False)
    values = extract_numbers(text)
    return {
        "text": text,
        "value": values[0] if values else None,
        "unit": "bb" if re.search(r"\\bBB\\b", text, re.IGNORECASE) else "chips",
    }


def read_number_list(image: Image.Image) -> dict:
    text = ocr_text(image, numeric_only=False, multiline=True)
    return {
        "text": text,
        "values": extract_numbers(text),
        "unit": "bb" if re.search(r"\\bBB\\b", text, re.IGNORECASE) else "chips",
    }
