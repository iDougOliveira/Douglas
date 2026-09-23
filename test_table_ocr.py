#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "pokervision"))
import table_ocr


class TableOCRLogicTests(unittest.TestCase):
    def test_inactive_labels(self):
        self.assertTrue(table_ocr.is_inactive_label("Ausente"))
        self.assertTrue(table_ocr.is_inactive_label("Lugar Vazio"))
        self.assertTrue(table_ocr.is_inactive_label("Vazio"))
        self.assertFalse(table_ocr.is_inactive_label("Ausente na próxima mão"))
        self.assertFalse(table_ocr.is_inactive_label("Ficar de fora na próxima big blind"))

    def test_player_count_from_inactive_seats(self):
        self.assertEqual(table_ocr.infer_player_count(9, 0), 9)
        self.assertEqual(table_ocr.infer_player_count(9, 3), 6)
        self.assertEqual(table_ocr.infer_player_count(6, 2), 4)
        self.assertIsNone(table_ocr.infer_player_count(9, 8))
        self.assertIsNone(table_ocr.infer_player_count(11, 1))

    def test_duplicate_ocr_fragments_are_one_seat(self):
        points = [(0.10, 0.20), (0.11, 0.23), (0.82, 0.20)]
        clusters = table_ocr.cluster_points(points)
        self.assertEqual(len(clusters), 2)

    def test_invalid_active_count_never_publishes(self):
        self.assertIsNone(table_ocr.infer_player_count(9, 9))
        self.assertIsNone(table_ocr.infer_player_count(2, 2))

    def test_stack_parser(self):
        self.assertEqual(table_ocr.parse_stack_bb("89,7 BB"), 89.7)
        self.assertEqual(table_ocr.parse_stack_bb("Player 216,9 BB"), 216.9)
        self.assertIsNone(table_ocr.parse_stack_bb("Pote: 8,5"))

    def test_action_parser(self):
        self.assertEqual(table_ocr.parse_action_text("Pago"), "CALL")
        self.assertEqual(table_ocr.parse_action_text("Aumento para 8 BB"), "RAISE")
        self.assertEqual(table_ocr.parse_action_text("Desisto"), "FOLD")
        self.assertEqual(table_ocr.parse_action_text("All In"), "ALL-IN")
        self.assertEqual(table_ocr.parse_action_text("texto qualquer"), "")

    def test_action_only_allin_keeps_seat_observation(self):
        perimeter = [
            {"text": "Alice", "x": 0.15, "y": 0.20},
            {"text": "All In", "x": 0.15, "y": 0.24},
        ]
        observations = table_ocr.build_seat_observations(
            perimeter,
            perimeter,
        )
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["name"], "Alice")
        self.assertIsNone(observations[0]["stack_bb"])
        self.assertEqual(observations[0]["action"], "ALL-IN")

    def test_seat_observation_adds_bet_and_action(self):
        perimeter = [
            {"text": "Alice", "x": 0.15, "y": 0.20},
            {"text": "89,7 BB", "x": 0.15, "y": 0.24},
        ]
        all_lines = perimeter + [
            {"text": "3 BB", "x": 0.25, "y": 0.30},
            {"text": "Pago", "x": 0.18, "y": 0.18},
            {"text": "Pote: 18 BB", "x": 0.50, "y": 0.46},
        ]
        observations = table_ocr.build_seat_observations(
            perimeter,
            all_lines,
        )
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["name"], "Alice")
        self.assertEqual(observations[0]["stack_bb"], 89.7)
        self.assertEqual(observations[0]["bet_bb"], 3.0)
        self.assertEqual(observations[0]["action"], "CALL")

    def test_seat_observation_pairing(self):
        lines = [
            {"text": "Alice", "x": 0.15, "y": 0.20},
            {"text": "89,7 BB", "x": 0.15, "y": 0.24},
            {"text": "Bob", "x": 0.82, "y": 0.20},
            {"text": "72,7 BB", "x": 0.82, "y": 0.24},
        ]
        observations = table_ocr.build_seat_observations(lines)
        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0]["name"], "Alice")
        self.assertEqual(observations[0]["stack_bb"], 89.7)


if __name__ == "__main__":
    unittest.main()
