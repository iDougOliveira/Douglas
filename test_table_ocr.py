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


if __name__ == "__main__":
    unittest.main()
