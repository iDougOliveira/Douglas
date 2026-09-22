#!/usr/bin/env python3
import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

import app


class PokerCoachTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        app.DB_PATH = Path(cls.tmp.name) / "test.db"
        app.init_db()
        salt = bytes.fromhex("00" * 16)
        import hashlib
        digest = hashlib.pbkdf2_hmac("sha256", b"senha-teste", salt, 240_000).hex()
        app.PASSWORD_HASH = salt.hex() + "$" + digest
        app.SESSION_SECRET = "test-secret"
        cls.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        jar = http.cookiejar.CookieJar()
        cls.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    @classmethod
    def call(cls, path, data=None):
        body = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{cls.port}{path}", data=body,
            headers={"Content-Type": "application/json"},
        )
        return json.loads(cls.client.open(req).read())

    def test_end_to_end(self):
        self.assertEqual(self.call("/api/health")["status"], "ok")
        self.assertTrue(self.call("/api/login", {"password": "senha-teste"})["ok"])
        result = self.call("/api/analyze", {
            "completed_hand": True, "mode": "cash", "position": "BTN", "player_count": 6,
            "card1": "Ah", "card2": "Ks", "stack_bb": 100,
            "pot_bb": 1.5, "call_bb": 0, "last_raise_bb": 0,
            "street": "preflop", "situation": "unopened",
        })
        self.assertEqual(result["action"], "RAISE")
        self.assertEqual(result["hand"], "AKo")
        self.assertEqual(result["raise_to_bb"], 2.5)
        self.assertEqual(result["engine_version"], "3.8.1")
        self.assertTrue(self.call("/api/session", {
            "played_at": "2026-09-21", "mode": "cash", "stakes": "NL10",
            "buy_in": 10, "cash_out": 13.5, "notes": "teste",
        })["ok"])
        summary = self.call("/api/summary")
        self.assertEqual(summary["sessions"], 1)
        self.assertEqual(summary["profit"], 3.5)

    def test_table_formats_and_history(self):
        for count, positions in app.POSITION_ORDER.items():
            for position in positions:
                with self.subTest(count=count, position=position):
                    result = app.analyze({
                        "completed_hand": True, "player_count": count,
                        "position": position, "card1": "Ah", "card2": "As",
                    })
                    self.assertEqual(result["player_count"], count)
                    self.assertEqual(result["position"], position)
                    self.assertIn(result["action"], {"RAISE", "FOLD", "SEM AÇÃO"})
        import sqlite3
        with sqlite3.connect(app.DB_PATH) as db:
            details = json.loads(db.execute("SELECT details FROM reviews ORDER BY id DESC LIMIT 1").fetchone()[0])
        self.assertEqual(details["player_count"], 10)

    def test_incompatible_seats_and_counts(self):
        for count, position in [(2, "SB"), (2, "BTN"), (3, "UTG"), (6, "UTG+1"), (1, "BTN"), (11, "BTN"), (2.5, "BB"), (True, "BB")]:
            with self.subTest(count=count, position=position), self.assertRaises(ValueError):
                app.analyze({"completed_hand": True, "player_count": count, "position": position, "card1": "Ah", "card2": "As"})

    def test_unopened_big_blind_is_not_an_open_raise(self):
        result = app.analyze({"completed_hand": True, "player_count": 8, "position": "BB", "card1": "Ah", "card2": "As"})
        self.assertEqual(result["action"], "SEM AÇÃO")


if __name__ == "__main__":
    unittest.main()


class VisionRelayTests(unittest.TestCase):
    def test_vision_payload_validation(self):
        state = app.normalize_vision_payload({
            "version": "0.3.1",
            "running": True,
            "confirmed": True,
            "hand": ["JS", "9C"],
            "board": ["2D", "8H", "2S"],
            "street": "FLOP",
        })
        self.assertEqual(state["hand"], ["JS", "9C"])
        self.assertEqual(state["board"], ["2D", "8H", "2S"])
        self.assertEqual(state["street"], "FLOP")

    def test_vision_payload_rejects_duplicate_cards(self):
        with self.assertRaises(ValueError):
            app.normalize_vision_payload({
                "hand": ["JS", "9C"],
                "board": ["JS", "8H", "2S"],
                "street": "FLOP",
            })


class VisionNumericRelayTests(unittest.TestCase):
    def test_vision_numeric_fields(self):
        state = app.normalize_vision_payload({
            "version": "0.4.0",
            "running": True,
            "confirmed": True,
            "hand": ["AS", "KD"],
            "board": [],
            "street": "PRÉ-FLOP",
            "blinds": {"small": 100, "big": 200},
            "ante": 25,
            "hero_stack_chips": 7650,
            "hero_stack_bb": 38.25,
            "table_stacks": [4200, 7650, 12000],
            "effective_stack_bb": 21,
            "pot_chips": 450,
            "pot_bb": 2.25,
        })
        self.assertEqual(state["blinds"]["big"], 200.0)
        self.assertEqual(state["hero_stack_bb"], 38.25)
        self.assertEqual(state["effective_stack_bb"], 21.0)
        self.assertEqual(state["pot_bb"], 2.25)

    def test_vision_numeric_fields_reject_negative(self):
        with self.assertRaises(ValueError):
            app.normalize_vision_payload({
                "hand": [],
                "board": [],
                "street": "AGUARDANDO",
                "hero_stack_chips": -1,
            })
