import unittest
import math
from strategy import decide, expand_range, normalize_hand, PROFILES, RANKS


def review(**changes):
    data = dict(completed_hand=True, player_count=6, position="BTN", mode="cash",
                stack_bb=100, card1="As", card2="Ah", situation="unopened")
    data.update(changes)
    return decide(data)


class StrategyTest(unittest.TestCase):
    def test_published_opening_examples(self):
        self.assertEqual(review()["raise_to_bb"], 2.5)
        self.assertEqual(review(player_count=8)["raise_to_bb"], 3)
        self.assertEqual(review(player_count=8)["strategy_status"], "adapted_reference")
        self.assertEqual(review(card1="2s",card2="2h")["action"], "FOLD")
        self.assertEqual(review(player_count=8,card1="2s",card2="2h")["action"], "RAISE")
        self.assertEqual(review(position="LJ",card1="As",card2="Th")["action"], "RAISE")
        self.assertEqual(review(player_count=8,position="UTG",card1="As",card2="Th")["action"], "FOLD")

    def test_no_interpolation_or_legacy_fallback(self):
        for changes in [dict(stack_bb=99),dict(stack_bb=20),dict(player_count=3),dict(player_count=10),dict(ante_bb=1),dict(situation="limped"),dict(situation="facing_3bet")]:
            with self.subTest(changes=changes):
                self.assertEqual(review(**changes)["action"],"REVISAR")
        self.assertEqual(review(position="SB")["action"],"MISTA")

    def test_mtt_profiles_do_not_reuse_cash(self):
        args=dict(mode="tournament",player_count=9,position="UTG",icm_pressure=False,card1="As",card2="8s")
        self.assertEqual(review(**args,stack_bb=100)["action"],"FOLD")
        self.assertEqual(review(**args,stack_bb=75)["action"],"RAISE")
        self.assertIsNone(review(**args,stack_bb=75)["raise_to_bb"])
        self.assertEqual(review(mode="tournament",player_count=9)["action"],"REVISAR")
        self.assertEqual(review(mode="tournament",player_count=8,position="HJ",stack_bb=10,icm_pressure=False)["action"],"ALL-IN")
        self.assertEqual(review(mode="tournament",player_count=8,position="BTN",stack_bb=10,icm_pressure=False)["action"],"MISTA")

    def test_threebet_and_original_7_5_bug(self):
        args=dict(situation="facing_raise",opener_position="LJ",open_to_bb=5)
        r=review(**args)
        self.assertEqual(r["raise_to_bb"],15)
        self.assertEqual(r["min_raise_to_bb"],9)
        self.assertEqual(r["additional_bb"],15)
        r=review(**args,position="SB")
        self.assertEqual(r["raise_to_bb"],20)
        self.assertEqual(r["additional_bb"],19.5)
        r=review(situation="facing_raise",position="BB",opener_position="SB",open_to_bb=3)
        self.assertEqual(r["raise_to_bb"],9)
        self.assertEqual(r["additional_bb"],8)
        r=review(player_count=2,position="BB",situation="facing_raise",opener_position="BTN/SB",open_to_bb=3)
        self.assertEqual(r["raise_to_bb"],12)
        with self.assertRaises(ValueError):
            review(situation="facing_raise",opener_position="LJ",last_raise_bb=1,call_bb=5)
        with self.assertRaises(ValueError):
            review(**args,call_bb=3)

    def test_threebet_needs_context_and_does_not_auto_fold_other_hands(self):
        for changes in [dict(opener_position="SB"),dict(opener_position=""),dict(callers=1),dict(open_to_bb=10),dict(stack_bb=50),dict(card1="Ts",card2="Th")]:
            args=dict(situation="facing_raise",opener_position="LJ",open_to_bb=3)
            args.update(changes)
            with self.subTest(changes=changes):
                self.assertEqual(review(**args)["action"],"REVISAR")

    def test_pot_odds_and_conditional_ev(self):
        args=dict(street="river",pot_bb=10,call_bb=5,estimated_equity=40,closes_action=True)
        r=review(**args)
        self.assertEqual(r["action"],"CALL")
        self.assertAlmostEqual(r["pot_odds_pct"],100/3)
        self.assertAlmostEqual(r["ev_call_bb"],1)
        args["estimated_equity"]=20
        self.assertEqual(review(**args)["action"],"FOLD")
        args["estimated_equity"]=100/3
        self.assertEqual(review(**args)["action"],"INDIFERENTE")
        for change in [dict(closes_action=False),dict(active_opponents=2),dict(mode="tournament"),dict(call_bb=0)]:
            self.assertEqual(review(**(args|change))["action"],"REVISAR")
        with self.assertRaises(ValueError):
            review(**(args|dict(remaining_bb=4)))

    def test_all_169_hands_have_deterministic_source_backed_classification(self):
        for profile in PROFILES.values():
            for position in profile["ranges"]:
                for i,a in enumerate(RANKS):
                    for j,b in enumerate(RANKS):
                        # 13 pairs + 78 suited + 78 offsuit.
                        r=review(player_count=profile["players"],mode=profile["mode"],stack_bb=profile["stack"],position=position,icm_pressure=False,card1=a+"s",card2=b+("h" if i>=j else "s"))
                        self.assertIn(r["action"],{"RAISE","FOLD","MISTA","ALL-IN"})
                        self.assertTrue(r["sources"])
                        if r["raise_to_bb"] is not None:
                            self.assertLessEqual(r["raise_to_bb"],profile["stack"])
                            self.assertGreaterEqual(r["raise_to_bb"],2)

    def test_invalid_data(self):
        for change in [dict(stack_bb=math.nan),dict(stack_bb=-1),dict(stack_bb=True),dict(player_count=3.5),dict(card1="Ah",card2="Ah"),dict(mode="bad"),dict(street="bad"),dict(completed_hand=False)]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                review(**change)
        self.assertEqual(expand_range("77+"),{"77","88","99","TT","JJ","QQ","KK","AA"})
        self.assertEqual(expand_range("AJs+"),{"AJs","AQs","AKs"})
        self.assertEqual(expand_range("97s+"),{"97s","98s"})
        self.assertEqual(normalize_hand("3h","Ah"),"A3s")


if __name__ == "__main__":
    unittest.main()
