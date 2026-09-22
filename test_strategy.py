import unittest
import math
from strategy import decide, expand_range, normalize_hand, PROFILES, RANKS


def review(**changes):
    data = dict(
        completed_hand=True, player_count=6, position="BTN", mode="cash",
        stack_bb=100, card1="As", card2="Ah", situation="unopened",
        street="preflop", ante_bb=0,
    )
    data.update(changes)
    return decide(data)


class StrategyTest(unittest.TestCase):
    def test_opening_examples(self):
        self.assertEqual(review()["action"], "RAISE")
        self.assertEqual(review()["raise_to_bb"], 2.5)
        self.assertEqual(review(player_count=8)["raise_to_bb"], 3)
        self.assertEqual(review(card1="2s", card2="2h")["action"], "FOLD")
        self.assertEqual(review(player_count=8, card1="2s", card2="2h")["action"], "RAISE")

    def test_study_matching_is_automatic(self):
        r = review(stack_bb=99)
        self.assertEqual(r["action"], "RAISE")
        self.assertEqual(r["strategy_status"], "adapted_reference")
        self.assertEqual(r["study_stack_bb"], 100)

        r = review(player_count=3)
        self.assertEqual(r["action"], "RAISE")
        self.assertEqual(r["study_players"], 6)

        r = review(player_count=2, position="BTN/SB")
        self.assertEqual(r["action"], "RAISE")
        self.assertEqual(r["study_position"], "SB")

        r = review(player_count=10, position="MP")
        self.assertEqual(r["action"], "RAISE")
        self.assertIn(r["study_position"], {"UTG+1", "UTG+2"})

    def test_tournament_short_stack_single_action(self):
        r = review(
            mode="tournament", player_count=8, position="BTN",
            stack_bb=10, icm_pressure=False
        )
        self.assertEqual(r["action"], "ALL-IN")
        self.assertEqual(r["raise_to_bb"], 10)

    def test_threebet_value_core(self):
        r = review(
            situation="facing_raise", opener_position="LJ",
            open_to_bb=5
        )
        self.assertEqual(r["action"], "RAISE")
        self.assertEqual(r["raise_to_bb"], 15)
        self.assertEqual(r["min_raise_to_bb"], 9)

        r = review(
            situation="facing_raise", opener_position="LJ",
            open_to_bb=3, card1="Ts", card2="Th"
        )
        self.assertEqual(r["action"], "SEM COBERTURA")

    def test_flop_board_changes_decision(self):
        r = review(
            card1="As", card2="Qh", street="flop",
            flop1="Ah", flop2="7d", flop3="2c",
            pot_bb=6, call_bb=0
        )
        self.assertEqual(r["action"], "BET")
        self.assertEqual(r["hand_class"], "um par")
        self.assertIn("rainbow", r["board_texture"])

        r = review(
            card1="As", card2="Qh", street="flop",
            flop1="Ah", flop2="7d", flop3="2c",
            pot_bb=8, call_bb=2
        )
        self.assertEqual(r["action"], "CALL")

        r = review(
            card1="As", card2="Ah", street="flop",
            flop1="Ad", flop2="7c", flop3="2h",
            pot_bb=8, call_bb=2
        )
        self.assertEqual(r["action"], "RAISE")
        self.assertEqual(r["hand_class"], "trinca")

    def test_draw_and_pot_odds(self):
        r = review(
            card1="As", card2="Ks", street="flop",
            flop1="Qs", flop2="Js", flop3="2d",
            pot_bb=8, call_bb=2
        )
        self.assertEqual(r["action"], "CALL")
        self.assertGreaterEqual(r["estimated_draw_equity_pct"], r["pot_odds_pct"])

        r = review(
            card1="7s", card2="2h", street="flop",
            flop1="As", flop2="Kd", flop3="Qc",
            pot_bb=5, call_bb=5
        )
        self.assertEqual(r["action"], "FOLD")

    def test_turn_and_river_require_board(self):
        r = review(
            card1="As", card2="Qh", street="turn",
            flop1="Ad", flop2="7d", flop3="2c", turn="Ks",
            pot_bb=10, call_bb=0
        )
        self.assertIn(r["action"], {"BET", "CHECK"})

        r = review(
            card1="As", card2="Qh", street="river",
            flop1="Ad", flop2="7d", flop3="2c", turn="Ks", river="3h",
            pot_bb=12, call_bb=0
        )
        self.assertIn(r["action"], {"BET", "CHECK"})

        with self.assertRaises(ValueError):
            review(street="flop", flop1="Ah", flop2="7d", pot_bb=6)

    def test_duplicate_cards_are_rejected(self):
        with self.assertRaises(ValueError):
            review(
                card1="As", card2="Kh", street="flop",
                flop1="As", flop2="7d", flop3="2c", pot_bb=6
            )

    def test_ranges_and_invalid_data(self):
        self.assertEqual(expand_range("77+"), {"77","88","99","TT","JJ","QQ","KK","AA"})
        self.assertEqual(expand_range("AJs+"), {"AJs","AQs","AKs"})
        self.assertEqual(normalize_hand("3h","Ah"), "A3s")

        for change in [
            dict(stack_bb=math.nan), dict(stack_bb=-1), dict(stack_bb=True),
            dict(player_count=3.5), dict(card1="Ah",card2="Ah"),
            dict(mode="bad"), dict(street="bad"), dict(completed_hand=False)
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                review(**change)


if __name__ == "__main__":
    unittest.main()
