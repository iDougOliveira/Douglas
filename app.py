#!/usr/bin/env python3
"""PokerCoach Local - study/review tool. Standard-library only."""

from __future__ import annotations

import hashlib
import hmac
import http.cookies
import json
import os
import secrets
import sqlite3
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

RANKS = "23456789TJQKA"
POSITIONS = ["UTG", "UTG+1", "MP", "HJ", "CO", "BTN", "SB", "BB"]

# Simplified educational opening ranges. These are not solver/GTO outputs.
RFI = {
    "UTG": "77+ AJs+ KQs AQo+",
    "UTG+1": "66+ ATs+ KQs AJo+ KQo",
    "MP": "66+ ATs+ KJs+ QJs JTs AJo+ KQo",
    "HJ": "55+ A9s+ KTs+ QTs+ JTs T9s ATo+ KJo+ QJo",
    "CO": "44+ A7s+ K9s+ Q9s+ J9s+ T9s 98s ATo+ KJo+ QJo",
    "BTN": "22+ A2s+ K5s+ Q7s+ J7s+ T7s+ 97s+ 86s+ 75s+ 65s A8o+ K9o+ Q9o+ J9o+ T9o",
    "SB": "22+ A2s+ K5s+ Q7s+ J7s+ T7s+ 97s+ 86s+ 75s+ 65s A8o+ K9o+ Q9o+ J9o+ T9o",
    "BB": "22+ A2s+ K7s+ Q8s+ J8s+ T8s+ 98s 87s 76s A9o+ KTo+ QTo+ JTo",
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


def parse_range_token(token: str):
    plus = token.endswith("+")
    token = token.rstrip("+")
    suited = token.endswith("s")
    offsuit = token.endswith("o")
    core = token[:-1] if suited or offsuit else token
    if len(core) != 2:
        return []
    a, b = core
    if a == b:
        start = RANKS.index(a)
        return [r + r for r in RANKS[start:]] if plus else [core]
    if not plus:
        return [core + ("s" if suited else "o" if offsuit else "")]
    hi, low = RANKS.index(a), RANKS.index(b)
    out = []
    for idx in range(low, hi):
        suffix = "s" if suited else "o" if offsuit else ""
        out.append(a + RANKS[idx] + suffix)
    return out


def expand_range(text: str) -> set[str]:
    result: set[str] = set()
    for token in text.split():
        result.update(parse_range_token(token))
    return result


def normalize_hand(card1: str, card2: str) -> str:
    cards = [card1.strip().upper(), card2.strip().upper()]
    if any(len(c) != 2 or c[0] not in RANKS or c[1] not in "CDHS" for c in cards):
        raise ValueError("Use cartas como Ah, Ks, 9c ou Td.")
    if cards[0] == cards[1]:
        raise ValueError("As duas cartas não podem ser iguais.")
    r1, r2 = cards[0][0], cards[1][0]
    if r1 == r2:
        return r1 + r2
    if RANKS.index(r2) > RANKS.index(r1):
        cards.reverse()
        r1, r2 = cards[0][0], cards[1][0]
    return r1 + r2 + ("s" if cards[0][1] == cards[1][1] else "o")


def hand_tier(hand: str) -> int:
    premium = expand_range("JJ+ AKs AKo")
    strong = expand_range("88+ ATs+ KQs AQo+")
    playable = expand_range("22+ A2s+ K9s+ Q9s+ J9s+ T9s 98s ATo+ KJo+ QJo")
    if hand in premium:
        return 3
    if hand in strong:
        return 2
    if hand in playable:
        return 1
    return 0


def analyze(payload: dict) -> dict:
    if payload.get("completed_hand") is not True:
        raise ValueError("Confirme que esta é uma simulação ou mão já encerrada.")
    mode = str(payload.get("mode", "cash"))
    position = str(payload.get("position", "BTN")).upper()
    if position not in POSITIONS:
        raise ValueError("Posição inválida.")
    hand = normalize_hand(str(payload.get("card1", "")), str(payload.get("card2", "")))
    stack = float(payload.get("stack_bb", 100))
    pot = max(float(payload.get("pot_bb", 1.5)), 0.01)
    call = max(float(payload.get("call_bb", 0)), 0)
    last_raise = max(float(payload.get("last_raise_bb", 0)), 0)
    street = str(payload.get("street", "preflop"))
    situation = str(payload.get("situation", "unopened"))
    equity_raw = payload.get("estimated_equity")
    equity = float(equity_raw) / 100 if equity_raw not in (None, "") else None
    tier = hand_tier(hand)
    notes = []

    if street == "preflop":
        in_range = hand in expand_range(RFI[position])
        if situation == "unopened":
            if in_range:
                action = "RAISE"
                size = 2.2 if mode == "tournament" else 2.5
                if mode == "tournament" and stack < 15:
                    size = min(stack, 2.0)
                sizing = f"{size:.1f} BB"
                notes.append(f"A mão {hand} pertence ao range educacional de abertura do {position}.")
            else:
                action, sizing = "FOLD", "0 BB"
                notes.append(f"A mão {hand} está fora do range educacional de abertura do {position}.")
        else:
            if tier >= 3:
                action = "RAISE"
                multiplier = 4.0 if position in {"SB", "BB"} else 3.0
                size = min(stack, max(last_raise * multiplier, 7.5))
                sizing = f"{size:.1f} BB"
                notes.append("Faixa premium: candidato a 3-bet por valor.")
            elif tier >= 2 and call <= pot * 0.45:
                action, sizing = "CALL", f"{call:.1f} BB"
                notes.append("Faixa forte, mas a decisão real depende do range e posição do agressor.")
            else:
                action, sizing = "FOLD", "0 BB"
                notes.append("Contra ação anterior, a faixa recomendada fica mais restrita.")
    else:
        if equity is None:
            action, sizing = "REVISAR", "Informe a equity estimada"
            notes.append("No pós-flop, informe uma equity estimada para comparar com as pot odds.")
        else:
            pot_odds = call / (pot + call) if call else 0
            if call == 0:
                action = "BET" if equity >= 0.55 else "CHECK"
                bet = pot * (0.66 if equity >= 0.70 else 0.33)
                sizing = f"{bet:.1f} BB" if action == "BET" else "0 BB"
            elif equity >= pot_odds + 0.05:
                action, sizing = "CALL", f"{call:.1f} BB"
            else:
                action, sizing = "FOLD", "0 BB"
            notes.append(f"Pot odds: {pot_odds*100:.1f}% | Equity informada: {equity*100:.1f}%.")

    if mode == "tournament":
        if stack <= 10:
            notes.append("Stack crítico: priorize decisões push/fold; ICM não está calculado neste MVP.")
        elif stack <= 25:
            notes.append("Stack curto: evite linhas que comprometam muitas fichas sem plano.")

    result = {
        "hand": hand, "action": action, "sizing": sizing,
        "range": RFI[position], "notes": notes,
        "disclaimer": "Estimativa educacional para simulação/revisão; não é solução GTO nem garantia de lucro."
    }
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "INSERT INTO reviews(created_at,mode,position,hand,stack_bb,recommendation,details) VALUES(?,?,?,?,?,?,?)",
            (int(time.time()), mode, position, hand, stack, action, json.dumps(result, ensure_ascii=False)),
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
    def translate_path(self, path: str) -> str:
        relative = urlparse(path).path.lstrip("/") or "index.html"
        return str(STATIC / relative)

    def send_json(self, data, status=200, cookie: str | None = None):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
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
            if path == "/api/login":
                if not password_ok(str(data.get("password", ""))):
                    return self.send_json({"error": "Senha inválida"}, 401)
                expiry = int(time.time()) + 12 * 3600
                cookie = f"pc_session={session_token(expiry)}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200"
                return self.send_json({"ok": True}, cookie=cookie)
            if not self.authenticated():
                return self.send_json({"error": "Não autorizado"}, 401)
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
