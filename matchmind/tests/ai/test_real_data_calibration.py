"""Pins the real-data calibration: the mapping, the refusals, and the units.

Role B delivered one real match as a research package and asked Role C to decide how to adopt it.
The decision was calibration, not substitution: the real record stays outside the runtime, and what it
buys us is an external check on whether the synthetic clip behaves like football.

These tests protect the three things that could quietly go wrong:

* someone adds a Wyscout event name and it silently falls out of the mapping;
* someone starts computing recovery or possession metrics from a record that does not have them;
* the tolerance comparison mixes a fraction with a percentage and reports "everything is fine" while
  the table beside it says otherwise. That one actually happened while writing the harness.
"""
import json
import unittest

from evaluation import real_data_calibration as calibration


class SampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = calibration.real_window()
        cls.report = calibration.build_report()

    def test_the_sample_parses_and_stays_inside_its_window(self):
        self.assertEqual(len(self.real), 96)
        for event in self.real:
            self.assertGreaterEqual(event["sec"], calibration.WINDOW[0])
            self.assertLessEqual(event["sec"], calibration.WINDOW[1])

    def test_the_documented_event_counts_are_what_the_file_holds(self):
        counts = self.report["event_names_in_sample"]
        self.assertEqual(counts["Pass"], 59)
        self.assertEqual(counts["Shot"], 4)
        self.assertEqual(counts["Duel"], 16)
        self.assertEqual(sum(counts.values()), 96)

    def test_every_event_name_in_the_sample_has_a_mapping_entry(self):
        """A new Wyscout type must be mapped or explicitly refused, never silently ignored."""
        for name in self.report["event_names_in_sample"]:
            self.assertIn(name, calibration.WYSCOUT_MAPPING, name)

    def test_both_sides_are_assigned(self):
        self.assertEqual({e["team"] for e in self.real}, {"HOME", "AWAY"})


class RefusalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = calibration.build_report()

    def test_recovery_and_possession_metrics_are_refused_with_a_reason(self):
        refused = {item["metric"] for item in self.report["refusals"]}
        for metric in ("high_recoveries", "linked_shots", "sustained_control"):
            self.assertIn(metric, refused)
        for item in self.report["refusals"]:
            self.assertTrue(item["reason"].strip(), item["metric"])

    def test_the_real_source_is_labelled_not_ours_and_not_runtime(self):
        source = self.report["real_source"]
        self.assertFalse(source["synthetic"])
        self.assertFalse(source["runtime_compatible"])
        self.assertIn("CC BY 4.0", source["licence"])

    def test_no_model_is_called(self):
        self.assertEqual(self.report["model_calls"], 0)


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = calibration.build_report()

    def test_the_compared_metrics_are_real_numbers(self):
        columns = self.report["columns"]
        self.assertEqual(columns["real sample"]["events"], 96)
        self.assertEqual(columns["synthetic shipped"]["events"], 30)
        self.assertGreater(columns["synthetic dense (proposal)"]["events"], 96)

    def test_the_shipped_clip_is_much_sparser_than_real_football(self):
        """Measured, not assumed: 10.0 s per event against the real sample's ~3.1 s."""
        columns = self.report["columns"]
        self.assertAlmostEqual(columns["synthetic shipped"]["seconds_per_event"], 10.0, places=1)
        self.assertLess(columns["real sample"]["seconds_per_event"], 4.0)

    def test_the_dense_proposal_matches_density(self):
        columns = self.report["columns"]
        real = columns["real sample"]["seconds_per_event"]
        dense = columns["synthetic dense (proposal)"]["seconds_per_event"]
        self.assertLess(abs(dense - real) / real, 0.30)

    def test_an_overshoot_is_not_reported_as_ok(self):
        """Regression: the first version compared 1.5 against 50.0 and called a +150% overshoot ok."""
        verdicts = calibration.compare({
            "real sample": {"shots_per_10_min": 8.0},
            "synthetic": {"shots_per_10_min": 20.0},
        })
        shots = [v for v in verdicts if v["metric"] == "shots_per_10_min"][0]
        self.assertEqual(shots["delta_pct"], 150.0)
        self.assertFalse(shots["within_tolerance"])

    def test_a_small_difference_is_reported_as_ok(self):
        verdicts = calibration.compare({
            "real sample": {"seconds_per_event": 3.12},
            "synthetic": {"seconds_per_event": 3.2},
        })
        row = [v for v in verdicts if v["metric"] == "seconds_per_event"][0]
        self.assertTrue(row["within_tolerance"])

    def test_the_dense_proposal_is_not_presented_as_a_perfect_match(self):
        """It fixes density and overshoots composition. The report must say so."""
        columns = self.report["columns"]
        self.assertGreater(columns["synthetic dense (proposal)"]["pass_share_pct"],
                           columns["real sample"]["pass_share_pct"])
        self.assertGreater(columns["synthetic dense (proposal)"]["shots_per_10_min"],
                           columns["real sample"]["shots_per_10_min"])


class CalibratedProfileTests(unittest.TestCase):
    """The tuned knobs, and the limits of tuning."""

    @classmethod
    def setUpClass(cls):
        cls.report = calibration.build_report()
        cls.columns = cls.report["columns"]

    def test_the_default_knobs_still_reproduce_the_published_proposal(self):
        """Tuning must not quietly change the fixture the repository already publishes."""
        from collections import Counter
        events = calibration.dense_window()
        self.assertEqual(len(events), 110)
        self.assertEqual(Counter(e["name"] for e in events),
                         {"pass": 94, "shot": 9, "recovery": 6, "goal": 1})

    def test_the_calibrated_profile_matches_the_real_shot_rate(self):
        real = self.columns["real sample"]["shots_per_10_min"]
        tuned = self.columns["synthetic dense (calibrated)"]["shots_per_10_min"]
        self.assertEqual(tuned, real)

    def test_the_calibrated_profile_keeps_the_density(self):
        tuned = self.columns["synthetic dense (calibrated)"]
        real = self.columns["real sample"]["seconds_per_event"]
        self.assertLess(abs(tuned["seconds_per_event"] - real) / real, 0.30)
        # Tuning the shot chance must not shrink the fixture back into sparse territory.
        self.assertGreaterEqual(tuned["events"], 96)

    def test_tuning_does_not_claim_to_fix_the_pass_share(self):
        tuned = self.columns["synthetic dense (calibrated)"]["pass_share_pct"]
        self.assertGreater(tuned, self.columns["real sample"]["pass_share_pct"])
        note = self.report["cannot_be_fixed_by_a_knob"]
        self.assertIn("pass share", note["what_it_cannot"])
        self.assertIn("recoveries", note["pass_share_gap"])


if __name__ == "__main__":
    unittest.main()
