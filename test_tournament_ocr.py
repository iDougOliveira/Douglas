import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "pokervision"))
import tournament_ocr


class TournamentHudTests(unittest.TestCase):
    def test_parses_compact_mtt_hud(self):
        result = tournament_ocr.parse_tournament_hud_text(
            "38º de 198 04:31 Média: 32,5 BB 400/800(100)"
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["rank"], 38)
        self.assertEqual(result["remaining"], 198)
        self.assertEqual(result["avg_stack_bb"], 32.5)
        self.assertEqual(result["small_blind"], 400)
        self.assertEqual(result["big_blind"], 800)
        self.assertEqual(result["ante"], 100)
        self.assertEqual(result["level_seconds"], 271)

    def test_partial_hud_does_not_invent_missing_values(self):
        result = tournament_ocr.parse_tournament_hud_text(
            "Média: 18,2 BB 500/1000"
        )
        self.assertTrue(result["valid"])
        self.assertIsNone(result["rank"])
        self.assertIsNone(result["remaining"])
        self.assertEqual(result["avg_stack_bb"], 18.2)
        self.assertEqual(result["small_blind"], 500)
        self.assertEqual(result["big_blind"], 1000)
        self.assertIsNone(result["ante"])


if __name__ == "__main__":
    unittest.main()
