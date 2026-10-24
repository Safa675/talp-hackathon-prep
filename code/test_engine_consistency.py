"""Focused regression checks for event/decision timing and live-session replay."""

import json
import random
import tempfile
import unittest
from pathlib import Path

import engine
import sim


class TimeConsistencyTests(unittest.TestCase):
    def test_events_and_actions_change_the_world_in_their_week(self):
        leg = {"week": 4, "date": "2026-11-24", "from": "PHL", "to": "MCO"}
        worn_parts = {"week": 4, "text": "Worn parts", "effect": "many cancellations", "scope": "all", "until_week": 5}
        witness = None
        for seed in range(1000):
            plain = sim.leg_facts({"airport_assistance": "none"}, leg, 4, random.Random(seed), {}, [], False)[0]
            crisis = sim.leg_facts({"airport_assistance": "none"}, leg, 4, random.Random(seed), {}, [worn_parts], False)[0]
            lease = sim.leg_facts({"airport_assistance": "none"}, leg, 4, random.Random(seed), {"lease": "1 aircraft"}, [worn_parts], False)[0]
            if plain != "canceled" and crisis == "canceled" and lease != "canceled":
                witness = seed
                break
        self.assertIsNotNone(witness, "the week-4 event and lease should change at least one same-seed flight")
        self.assertNotIn(worn_parts, sim.events_in_force([worn_parts], 3))
        self.assertIn(worn_parts, sim.events_in_force([worn_parts], 4))
        self.assertIn(worn_parts, sim.events_in_force([worn_parts], 5))
        self.assertNotIn(worn_parts, sim.events_in_force([worn_parts], 6))

        strike_leg = {"week": 8, "date": "2026-12-22", "from": "PHL", "to": "MCO"}
        strike = {"week": 8, "text": "Ground strike", "known_crisis": True, "effect": "none", "scope": "bases"}
        self.assertFalse(sim.strike_announced([strike], 7))
        self.assertTrue(sim.strike_announced([strike], 8))
        witness = None
        for seed in range(1000):
            plain = sim.leg_facts({}, strike_leg, 8, random.Random(seed), {}, [], False)[0]
            crisis = sim.leg_facts({}, strike_leg, 8, random.Random(seed), {}, [], True)[0]
            backup = sim.leg_facts({}, strike_leg, 8, random.Random(seed), {"backup": "on"}, [], True)[0]
            if plain != "canceled" and crisis == "canceled" and backup != "canceled":
                witness = seed
                break
        self.assertIsNotNone(witness, "the strike and backup action should change at least one same-seed flight")

    def test_event_and_decision_effective_weeks(self):
        decisions = [
            {"week": 4, "target": "everyone", "actions": [{"action": "Lease an aircraft with crew for 2 weeks", "level": "1 aircraft"}], "message": "week four"},
            {"week": 8, "target": "everyone", "actions": [
                {"action": "Backup ground handling contract at both bases for the strike days", "level": "on"},
                {"action": "Rebooking deal with a partner airline for 2 disrupted weeks", "level": "on"},
            ], "message": "week eight"},
        ]
        person = {"id": "p", "group": "students", "trips": []}
        self.assertEqual(sim.effects(decisions, person, 3), {})
        self.assertIn("lease", sim.effects(decisions, person, 4))
        self.assertIn("lease", sim.effects(decisions, person, 5))
        self.assertEqual(sim.effects(decisions, person, 6), {})
        self.assertEqual(sim.effects(decisions, person, 7), {})
        self.assertIn("backup", sim.effects(decisions, person, 8))
        self.assertIn("partner", sim.effects(decisions, person, 9))
        self.assertNotIn("backup", sim.effects(decisions, person, 9))
        self.assertEqual(sim.company_message(decisions, person, 3), "")
        self.assertEqual(sim.company_message(decisions, person, 4), "week four")
        self.assertEqual(sim.company_message(decisions, person, 6), "")
        self.assertEqual(sim.company_message(decisions, person, 8), "week eight")
        self.assertEqual(sim.company_message(decisions, person, 10), "")

    def test_live_session_replays_changed_week_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ("RUNS", "CKPT", "LOGS", "SESSIONS")
            old = {name: getattr(engine, name) for name in names}
            try:
                for name in names:
                    setattr(engine, name, root / name.lower())
                people = root / "personas_test.jsonl"
                people.write_text("".join(json.dumps({"id": f"p{i}", "group": "students", "home_area": "PHL", "trips": []}) + "\n" for i in range(4)))
                events = root / "surprises_test.json"
                events.write_text(json.dumps([{"week": 3, "text": "Inspection", "effect": "none", "scope": "all", "until_week": 3}]))
                decisions = root / "decisions_test.json"
                decisions.write_text("[]")
                run = engine.Run("timing_test", "plan", 1, str(decisions), str(events), False, "mock", str(people), session=True, social=False)
                run.execute(4)
                self.assertEqual(run.info["status"], "paused")
                before = run.info["chain"][:]
                self.assertEqual(run.validity()["valid_through"], 4)

                current = json.loads(events.read_text())
                current.append({"week": 4, "text": "Worn parts", "effect": "many cancellations", "scope": "all", "until_week": 5})
                events.write_text(json.dumps(current))
                self.assertEqual(run.validity()["stale_from"], 4)
                run.execute(4)
                self.assertEqual(run.info["chain"][1:4], before[1:4])
                self.assertNotEqual(run.info["chain"][4], before[4])
                fourth = engine.load_ckpt(run.info["chain"][4])["entries"]
                third = engine.load_ckpt(run.info["chain"][3])["entries"]
                self.assertTrue(all("Worn parts" in e["prompt"] for e in fourth))
                self.assertTrue(all("Worn parts" not in e["prompt"] for e in third))

                decisions.write_text(json.dumps([{"week": 4, "target": "everyone", "actions": [
                    {"action": "Free changes and cancellations for bookings in a 2-week window", "level": "on"}],
                    "message": "New week-four decision"}]))
                self.assertEqual(run.validity()["stale_from"], 4)
                run.execute(4)
                fourth = engine.load_ckpt(run.info["chain"][4])["entries"]
                third = engine.load_ckpt(run.info["chain"][3])["entries"]
                self.assertTrue(all("New week-four decision" in e["prompt"] for e in fourth))
                self.assertTrue(all("New week-four decision" not in e["prompt"] for e in third))

                current.append({"week": 8, "known_from": 5, "text": "Future strike", "known_crisis": True,
                                "effect": "none", "scope": "bases", "until_week": 8})
                events.write_text(json.dumps(current))
                self.assertEqual(run.validity()["valid_through"], 4)
                current[-1]["known_from"] = 1
                events.write_text(json.dumps(current))
                self.assertEqual(run.validity()["stale_from"], 1)
            finally:
                for name, value in old.items():
                    setattr(engine, name, value)

    def test_known_strike_news_precedes_operational_effect(self):
        strike = {"week": 8, "text": "Known 48-hour strike", "known_crisis": True,
                  "effect": "none", "scope": "bases", "until_week": 8}
        person = {"id": "p", "group": "students", "trips": []}
        _, outcome, facts, world = sim.week_facts(person, 7, random.Random(1), [strike], True)
        self.assertEqual(outcome, "none")
        self.assertFalse(world["strike_day"])
        self.assertTrue(any("Known 48-hour strike" in fact for fact in facts))
        self.assertTrue(engine.event_known(strike, 1))
        self.assertFalse(sim.strike_announced([strike], 7))
        self.assertTrue(sim.strike_announced([strike], 8))

    def test_unrefunded_cancellation_is_not_counted_within_24h(self):
        people = [{"id": "p", "trips": [{"week": 8, "date": "2026-12-22", "from": "PHL", "to": "MCO"}]}]
        weekly = [{"persona": "p", "week": 8, "had_flight_this_week": True,
                   "flight_outcome": "canceled", "status": "canceled the trip",
                   "within_24h": False, "complaint": True}]
        self.assertEqual(engine.board_metrics(people, weekly, [], [])['goal_2'], 0.0)

    def test_timely_offer_is_not_a_completed_rebooking(self):
        delayed = {"persona": "p", "week": 8, "had_flight_this_week": True,
                   "flight_outcome": "delayed", "status": "flies as planned",
                   "within_24h": True, "complaint": False}
        self.assertEqual(engine.recovery_24h(delayed), False)
        self.assertEqual(engine.observed_week_metrics([delayed])["resolved_24h"], 0)
        # goal_2 counts a delayed flight that still operates within 24h; the strict view does not
        self.assertEqual(engine.board_metrics([{"id": "p", "trips": []}], [delayed], [], [])["goal_2_strict"], 0.0)
        self.assertEqual(engine.board_metrics([{"id": "p", "trips": []}], [delayed], [], [])["goal_2"], 100.0)
        self.assertTrue(engine.recovery_24h(dict(delayed, status="rebooked")))

    def test_complaint_anchor_is_fixed_before_events(self):
        people = [{"id": "p", "trips": []}, {"id": "q", "trips": []}]
        early = [{"persona": p, "week": w, "flight_outcome": "none", "had_flight_this_week": False,
                  "complaint": p == "p" and w == 1} for w in (1, 2) for p in ("p", "q")]
        late = [dict(early[0], week=8, complaint=True), dict(early[1], week=8, complaint=False)]
        high = engine.board_metrics(people, early + late, [], [])["goal_3"]
        low = engine.board_metrics(people, early + [dict(r, complaint=False) for r in late], [], [])["goal_3"]
        self.assertGreater(high, low)

    def test_batch_manager_does_not_touch_live_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = engine.SESSIONS
            try:
                engine.SESSIONS = Path(tmp)
                marker = engine.SESSIONS / "active.json"
                marker.write_text('{"an active session": true}')
                self.assertEqual(engine.Manager(load_sessions=False).runs, {})
                self.assertEqual(marker.read_text(), '{"an active session": true}')
            finally:
                engine.SESSIONS = old


if __name__ == "__main__":
    unittest.main()
