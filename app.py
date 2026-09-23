#!/usr/bin/env python3
"""PokerCoach Local - study/review tool. Standard-library only."""

from __future__ import annotations

import hashlib
import hmac
import http.cookies
import ipaddress
import json
import strategy
import os
import secrets
import sqlite3
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
VERSION = (ROOT / "VERSION").read_text().strip() if (ROOT / "VERSION").exists() else "dev"
DB_PATH = Path(os.getenv("POKERCOACH_DB", ROOT / "data" / "pokercoach.db"))
HOST = os.getenv("POKERCOACH_HOST", "0.0.0.0")
PORT = int(os.getenv("POKERCOACH_PORT", "8765"))
PASSWORD_HASH = os.getenv("POKERCOACH_PASSWORD_HASH", "")
SESSION_SECRET = os.getenv("POKERCOACH_SESSION_SECRET", secrets.token_hex(32))

POSITION_ORDER = strategy.POSITIONS

VISION_LOCK = threading.Lock()
VISION_STATES: dict[str, dict] = {}
VISION_CONFIG_LOCK = threading.Lock()
VISION_CONFIG = {"table_max_seats": 9}
VISION_TTL_SECONDS = 3.0
VISION_STREETS = {"AGUARDANDO", "PRÉ-FLOP", "FLOP", "TURN", "RIVER", "INCERTO", "TRANSIÇÃO"}


def vision_config_snapshot() -> dict:
    with VISION_CONFIG_LOCK:
        return dict(VISION_CONFIG)


def private_client(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
        return bool(ip.is_private or ip.is_loopback)
    except ValueError:
        return False


def valid_card_code(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 2:
        return False
    return value[0] in "AKQJT98765432" and value[1] in "SHDC"


def optional_nonnegative_number(value: object) -> float | None:
    if value is None or value == "":
        return None
    number = float(value)
    if number < 0:
        raise ValueError("Valor visual numérico inválido.")
    return number


def optional_int_range(
    value: object,
    minimum: int,
    maximum: int,
    label: str,
) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{label} inválido.")
    try:
        number = int(value)
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} inválido.")
    if number != numeric or not minimum <= number <= maximum:
        raise ValueError(f"{label} inválido.")
    return number


def normalized_points(value: object) -> list[list[float]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > 10:
        raise ValueError("Pontos de assentos inválidos.")
    clean = []
    for point in value:
        if (
            not isinstance(point, list)
            or len(point) != 2
        ):
            raise ValueError("Ponto de assento inválido.")
        x = float(point[0])
        y = float(point[1])
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError("Coordenada de assento inválida.")
        clean.append([x, y])
    return clean


def normalized_seat_observations(value: object) -> list[dict]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > 10:
        raise ValueError("Leituras de assentos inválidas.")
    clean = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Leitura de assento inválida.")
        x = float(item.get("x", -1))
        y = float(item.get("y", -1))
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError("Coordenada de assento inválida.")
        stack = optional_nonnegative_number(item.get("stack_bb"))
        status = str(item.get("status", "active"))
        if status not in {"active", "inactive", "disconnected"}:
            status = "active"
        clean.append({
            "x": x,
            "y": y,
            "name": str(item.get("name", ""))[:32],
            "stack_bb": stack,
            "status": status,
            "raw": str(item.get("raw", ""))[:80],
        })
    return clean


def normalize_vision_payload(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Estado visual inválido.")

    hand = data.get("hand", [])
    board = data.get("board", [])
    if not isinstance(hand, list) or len(hand) not in {0, 2}:
        raise ValueError("Mão visual inválida.")
    if not isinstance(board, list) or len(board) not in {0, 3, 4, 5}:
        raise ValueError("Board visual inválido.")
    if not all(valid_card_code(card) for card in [*hand, *board]):
        raise ValueError("Carta visual inválida.")
    if len(set([*hand, *board])) != len([*hand, *board]):
        raise ValueError("Carta duplicada no estado visual.")

    street = str(data.get("street", "AGUARDANDO"))
    if street not in VISION_STREETS:
        street = "INCERTO"

    table_stacks = data.get("table_stacks", [])
    if table_stacks is None:
        table_stacks = []
    if not isinstance(table_stacks, list) or len(table_stacks) > 10:
        raise ValueError("Stacks da mesa inválidos.")
    clean_stacks = [
        optional_nonnegative_number(value)
        for value in table_stacks
        if value is not None and value != ""
    ]

    table_stacks_bb = data.get("table_stacks_bb", [])
    if table_stacks_bb is None:
        table_stacks_bb = []
    if not isinstance(table_stacks_bb, list) or len(table_stacks_bb) > 10:
        raise ValueError("Stacks BB da mesa inválidos.")
    clean_stacks_bb = [
        optional_nonnegative_number(value)
        for value in table_stacks_bb
        if value is not None and value != ""
    ]

    blinds = data.get("blinds")
    clean_blinds = None
    if blinds is not None:
        if not isinstance(blinds, dict):
            raise ValueError("Blinds visuais inválidos.")
        clean_blinds = {
            "small": optional_nonnegative_number(blinds.get("small")),
            "big": optional_nonnegative_number(blinds.get("big")),
        }

    return {
        "version": str(data.get("version", ""))[:20],
        "running": bool(data.get("running", False)),
        "confirmed": bool(data.get("confirmed", False)),
        "hand": hand,
        "board": board,
        "street": street,
        "blinds": clean_blinds,
        "ante": optional_nonnegative_number(data.get("ante")),
        "hero_stack_chips": optional_nonnegative_number(data.get("hero_stack_chips")),
        "hero_stack_bb": optional_nonnegative_number(data.get("hero_stack_bb")),
        "table_stacks": clean_stacks,
        "table_stacks_bb": clean_stacks_bb,
        "effective_stack_bb": optional_nonnegative_number(data.get("effective_stack_bb")),
        "pot_chips": optional_nonnegative_number(data.get("pot_chips")),
        "pot_bb": optional_nonnegative_number(data.get("pot_bb")),
        "detected_player_count": optional_int_range(
            data.get("detected_player_count"), 2, 10, "Quantidade visual de jogadores"
        ),
        "inactive_seats": optional_int_range(
            data.get("inactive_seats"), 0, 10, "Quantidade de assentos inativos"
        ),
        "table_max_seats": optional_int_range(
            data.get("table_max_seats"), 2, 10, "Máximo visual de lugares"
        ),
        "table_scan_confidence": str(
            data.get("table_scan_confidence", "")
        )[:20],
        "table_scan_state": (
            str(data.get("table_scan_state", "disabled"))
            if str(data.get("table_scan_state", "disabled"))
            in {"disabled", "waiting", "partial", "confirmed", "error"}
            else "error"
        ),
        "table_scan_at": optional_nonnegative_number(data.get("table_scan_at")),
        "inactive_points": normalized_points(data.get("inactive_points", [])),
        "seat_observations": normalized_seat_observations(
            data.get("seat_observations", [])
        ),
        "updated_at": float(data.get("updated_at", 0) or 0),
    }


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS reviews (
              id INTEGER PRIMARY KEY, created_at INTEGER NOT NULL,
              mode TEXT NOT NULL, position TEXT NOT NULL, hand TEXT NOT NULL,
              stack_bb REAL NOT NULL, recommendation TEXT NOT NULL,
              details TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
              id INTEGER PRIMARY KEY, played_at TEXT NOT NULL,
              mode TEXT NOT NULL, stakes TEXT NOT NULL,
              buy_in REAL NOT NULL, cash_out REAL NOT NULL,
              notes TEXT NOT NULL DEFAULT ''
            );
            """
        )


def analyze(payload: dict) -> dict:
    result = strategy.decide(payload)
    result["input"] = payload
    if payload.get("record_review", True) is True:
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                "INSERT INTO reviews(created_at,mode,position,hand,stack_bb,recommendation,details) VALUES(?,?,?,?,?,?,?)",
                (int(time.time()), payload.get("mode", "cash"), result["position"],
                 result["hand"], float(payload.get("stack_bb", 100)), result["action"],
                 json.dumps(result, ensure_ascii=False)),
            )
    return result


def password_ok(password: str) -> bool:
    if not PASSWORD_HASH:
        return False
    try:
        salt, expected = PASSWORD_HASH.split("$", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 240_000).hex()
        return hmac.compare_digest(digest, expected)
    except ValueError:
        return False


def session_token(expiry: int) -> str:
    body = str(expiry)
    sig = hmac.new(SESSION_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return body + "." + sig


def valid_session(value: str) -> bool:
    try:
        expiry_s, sig = value.split(".", 1)
        expected = hmac.new(SESSION_SECRET.encode(), expiry_s.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected) and int(expiry_s) > int(time.time())
    except (ValueError, TypeError):
        return False


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def translate_path(self, path: str) -> str:
        relative = urlparse(path).path.lstrip("/") or "index.html"
        return str(STATIC / relative)

    def send_json(self, data, status=200, cookie: str | None = None):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 100_000:
            raise ValueError("Requisição muito grande.")
        return json.loads(self.rfile.read(length) or b"{}")

    def authenticated(self) -> bool:
        cookies = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookies.get("pc_session")
        return bool(morsel and valid_session(morsel.value))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self.send_json({"status": "ok", "version": VERSION})
        if path == "/api/vision/config":
            if not private_client(self.client_address[0]):
                return self.send_json({"error": "Origem não permitida"}, 403)
            return self.send_json(vision_config_snapshot())
        if path == "/api/vision/state":
            if not self.authenticated():
                return self.send_json({"error": "Não autorizado"}, 401)
            client_ip = self.client_address[0]
            with VISION_LOCK:
                stored = VISION_STATES.get(client_ip)
                state = dict(stored) if stored else None
            if not state or time.time() - state.get("_received_at", 0) > VISION_TTL_SECONDS:
                return self.send_json({"connected": False})
            state.pop("_received_at", None)
            state["connected"] = True
            return self.send_json(state)
        if path == "/api/summary":
            if not self.authenticated():
                return self.send_json({"error": "Não autorizado"}, 401)
            with sqlite3.connect(DB_PATH) as db:
                row = db.execute("SELECT COUNT(*), COALESCE(SUM(cash_out-buy_in),0), COALESCE(SUM(buy_in),0) FROM sessions").fetchone()
                recent = db.execute("SELECT played_at,mode,stakes,buy_in,cash_out,notes FROM sessions ORDER BY id DESC LIMIT 20").fetchall()
            return self.send_json({"sessions": row[0], "profit": row[1], "invested": row[2], "recent": recent})
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self.read_json()
            if path == "/api/vision/ingest":
                client_ip = self.client_address[0]
                if not private_client(client_ip):
                    return self.send_json({"error": "Origem visual não permitida"}, 403)
                state = normalize_vision_payload(data)
                state["_received_at"] = time.time()
                with VISION_LOCK:
                    VISION_STATES[client_ip] = state
                return self.send_json({
                    "ok": True,
                    "version": VERSION,
                    "config": vision_config_snapshot(),
                })
            if path == "/api/login":
                if not password_ok(str(data.get("password", ""))):
                    return self.send_json({"error": "Senha inválida"}, 401)
                expiry = int(time.time()) + 12 * 3600
                cookie = f"pc_session={session_token(expiry)}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200"
                return self.send_json({"ok": True}, cookie=cookie)
            if not self.authenticated():
                return self.send_json({"error": "Não autorizado"}, 401)
            if path == "/api/vision/config":
                max_seats = optional_int_range(
                    data.get("table_max_seats"),
                    2,
                    10,
                    "Capacidade da mesa",
                )
                if max_seats is None:
                    raise ValueError("Informe a capacidade da mesa.")
                with VISION_CONFIG_LOCK:
                    VISION_CONFIG["table_max_seats"] = max_seats
                return self.send_json(vision_config_snapshot())
            if path == "/api/analyze":
                return self.send_json(analyze(data))
            if path == "/api/session":
                values = (
                    str(data.get("played_at", "")), str(data.get("mode", "cash")),
                    str(data.get("stakes", "")), float(data.get("buy_in", 0)),
                    float(data.get("cash_out", 0)), str(data.get("notes", ""))[:500],
                )
                with sqlite3.connect(DB_PATH) as db:
                    db.execute("INSERT INTO sessions(played_at,mode,stakes,buy_in,cash_out,notes) VALUES(?,?,?,?,?,?)", values)
                return self.send_json({"ok": True})
            return self.send_json({"error": "Rota inexistente"}, 404)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.send_json({"error": str(exc)}, 400)

    def log_message(self, fmt, *args):
        print(time.strftime("%Y-%m-%d %H:%M:%S"), self.address_string(), fmt % args)


if __name__ == "__main__":
    init_db()
    print(f"PokerCoach Local em http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
