import strategy
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

    def test_quick_preflop_minimal_inputs(self):
        premium = review(
            mode="cash", player_count=9, position="SB", stack_bb=100,
            card1="As", card2="Kh", situation="facing_raise",
            quick_preflop=True, preflop_pressure="medium",
        )
        self.assertEqual(premium["action"], "RAISE")
        self.assertTrue(premium["quick_preflop"])

        weak = review(
            mode="cash", player_count=9, position="SB", stack_bb=100,
            card1="Qd", card2="4c", situation="facing_raise",
            quick_preflop=True, preflop_pressure="medium",
        )
        self.assertEqual(weak["action"], "FOLD")

        bb_call = review(
            mode="cash", player_count=9, position="BB", stack_bb=100,
            card1="Ts", card2="9s", situation="facing_raise",
            quick_preflop=True, preflop_pressure="low",
        )
        self.assertEqual(bb_call["action"], "CALL")

        reraised = review(
            mode="cash", player_count=9, position="BTN", stack_bb=100,
            card1="Qd", card2="4c", situation="facing_3bet",
            quick_preflop=True, preflop_pressure="medium",
        )
        self.assertEqual(reraised["action"], "FOLD")

        limped = review(
            mode="cash", player_count=9, position="SB", stack_bb=100,
            card1="As", card2="Kh", situation="limped",
            quick_preflop=True,
        )
        self.assertEqual(limped["action"], "RAISE")

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

    def test_postflop_ranges_are_pot_based(self):
        r = strategy.postflop_pressure_ranges(6, 10)
        self.assertEqual(r["low"], (1.5, 1.98))
        self.assertEqual(r["medium"], (3.0, 4.02))
        self.assertEqual(r["high"], (4.5, 6.0))
        self.assertEqual(r["allin"], (10.0, 10.0))

        deep = strategy.postflop_pressure_ranges(100, 500)
        self.assertEqual(deep["low"], (25.0, 33.0))
        self.assertEqual(deep["medium"], (50.0, 67.0))
        self.assertEqual(deep["high"], (75.0, 100.0))
        self.assertEqual(deep["allin"], (500.0, 500.0))

        shallow = strategy.postflop_pressure_ranges(10, 3)
        self.assertEqual(shallow["low"], (2.5, 2.9))
        self.assertIsNone(shallow["medium"])
        self.assertIsNone(shallow["high"])
        self.assertEqual(shallow["allin"], (3.0, 3.0))

    def test_postflop_pressure_bands(self):
        base = dict(
            card1="As", card2="Qh", street="flop",
            flop1="Ah", flop2="7d", flop3="2c",
            pot_bb=6, call_bb=0, stack_bb=40
        )
        low = review(**base, bet_pressure="low")
        self.assertEqual(low["action"], "CALL")
        self.assertAlmostEqual(low["call_bb"], 1.74)

        shove = review(**base, bet_pressure="allin")
        self.assertEqual(shove["call_bb"], 40.0)
        self.assertEqual(shove["bet_pressure"], "allin")
        self.assertEqual(shove["action"], "ALL-IN")

    def test_double_paired_board_does_not_fake_value_hand(self):
        # Screenshot regression: Hero J9s on 6h 6c 5c 5d does not own a
        # normal two-pair value hand; everyone shares 66/55 and Hero has J kicker.
        facing = review(
            mode="cash", player_count=9, position="CO", stack_bb=113,
            card1="Js", card2="9s", street="turn",
            flop1="6h", flop2="6c", flop3="5c", turn="5d",
            pot_bb=31.2, call_bb=0,
            post_action="facing_bet", bet_pressure="medium",
        )
        self.assertNotEqual(facing["action"], "RAISE")
        self.assertEqual(facing["action"], "FOLD")
        self.assertIn("kicker J", facing["hand_class"])

        checked = review(
            mode="cash", player_count=9, position="CO", stack_bb=113,
            card1="Js", card2="9s", street="turn",
            flop1="6h", flop2="6c", flop3="5c", turn="5d",
            pot_bb=31.2, call_bb=0,
            post_action="checked_to_hero", bet_pressure="none",
        )
        self.assertEqual(checked["action"], "CHECK")

        # A pocket pair above the lower board pair is recognized as a private
        # improvement, but still must not auto-raise on a double-paired board.
        improved = review(
            mode="cash", player_count=9, position="CO", stack_bb=113,
            card1="7s", card2="7d", street="turn",
            flop1="6h", flop2="6c", flop3="5c", turn="5d",
            pot_bb=31.2, call_bb=0,
            post_action="facing_bet", bet_pressure="medium",
        )
        self.assertEqual(improved["action"], "CALL")

    def test_tripled_board_full_house_is_relative_not_auto_stackoff(self):
        # Regression from screenshot: 66 on A-4-4-K-4 is 44466, but many
        # superior full houses exist (Ax, Kx, higher pocket pairs).
        checked = review(
            mode="cash", player_count=8, position="BTN", stack_bb=31.1,
            card1="6h", card2="6c", street="river",
            flop1="As", flop2="4c", flop3="4s", turn="Kc", river="4d",
            pot_bb=130.1, call_bb=0,
            post_action="checked_to_hero", bet_pressure="none",
        )
        self.assertEqual(checked["action"], "CHECK")
        self.assertIn("board triplicado", checked["hand_class"])
        self.assertNotIn("bet_bb", checked)

        facing_shove = review(
            mode="cash", player_count=8, position="BTN", stack_bb=31.1,
            card1="6h", card2="6c", street="river",
            flop1="As", flop2="4c", flop3="4s", turn="Kc", river="4d",
            pot_bb=130.1, call_bb=0,
            post_action="facing_bet", bet_pressure="allin",
        )
        self.assertEqual(facing_shove["action"], "FOLD")

    def test_postflop_bet_never_exceeds_stack(self):
        result = review(
            mode="cash", player_count=6, position="BTN", stack_bb=10,
            card1="Ah", card2="Ad", street="flop",
            flop1="As", flop2="Kd", flop3="7c",
            pot_bb=40, call_bb=0,
            post_action="checked_to_hero", bet_pressure="none",
        )
        self.assertLessEqual(result.get("bet_bb", 0), 10)
        self.assertEqual(result["action"], "ALL-IN")

    def test_auto_player_effective_stack_and_exact_call(self):
        result = review(
            mode="cash", player_count=6, position="BTN", stack_bb=100,
            effective_stack_bb=42, auto_player_action=True,
            card1="Ah", card2="Kh", street="flop",
            flop1="As", flop2="7d", flop3="2c",
            pot_bb=20, call_bb=8,
            post_action="facing_bet", bet_pressure="medium",
            active_opponents=1,
        )
        self.assertEqual(result["effective_stack_bb"], 42)
        self.assertEqual(result["call_bb"], 8)
        self.assertIn("Stack efetivo automático", " ".join(result["notes"]))

    def test_auto_preflop_allin_uses_effective_stack(self):
        result = review(
            mode="cash", player_count=6, position="BB", stack_bb=100,
            effective_stack_bb=35, auto_player_action=True,
            card1="Ah", card2="Ad", street="preflop",
            situation="facing_raise", preflop_pressure="allin",
            open_to_bb=35, quick_preflop=True,
        )
        self.assertEqual(result["action"], "CALL")
        self.assertEqual(result["call_bb"], 35)
        self.assertEqual(result["effective_stack_bb"], 35)

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
