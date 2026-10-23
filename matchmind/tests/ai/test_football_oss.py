"""Licence guard on the football OSS inventory.

The repository must become public before submission, so adopting an unlicensed dependency is a
real risk rather than a style question. This test makes the decision explicit: anything we would
adopt must have a permissive licence recorded, and anything without one must be marked
reference-only in the write-up.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "evaluation" / "research" / "football_oss.json"
WRITEUP = ROOT / "evaluation" / "research" / "DATA_AND_OSS.md"

PERMISSIVE = {"MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0", "CC0-1.0", "ISC"}
# Libraries we would consider adding as a dependency.
ADOPTABLE = {"ML-KULeuven/socceraction", "PySport/kloppy", "andrewRowlinson/mplsoccer",
             "Alek050/databallpy", "openfootball/football.json"}


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    def test_the_inventory_exists_and_records_licences(self):
        self.assertTrue(self.inventory)
        for full_name, entry in self.inventory.items():
            if "error" in entry:
                self.assertEqual(entry["error"], "HTTP 404",
                                 "%s failed unexpectedly: %s" % (full_name, entry["error"]))
                continue
            self.assertIn("licence", entry, full_name)

    def test_everything_we_would_adopt_is_permissively_licensed(self):
        offenders = []
        for full_name in ADOPTABLE:
            entry = self.inventory.get(full_name, {})
            if "error" in entry:
                continue
            if entry.get("licence") not in PERMISSIVE:
                offenders.append("%s (%s)" % (full_name, entry.get("licence")))
        self.assertEqual(offenders, [],
                         "these are marked adoptable but are not permissively licensed: %r"
                         % (offenders,))

    def test_data_we_cannot_redistribute_is_recorded_as_such(self):
        for full_name in ("statsbomb/open-data", "statsbomb/statsbombpy"):
            entry = self.inventory.get(full_name, {})
            if "error" in entry:
                continue
            self.assertNotIn(entry.get("licence"), PERMISSIVE,
                             "%s is now permissively licensed; revisit DATA_AND_OSS.md"
                             % full_name)

    def test_the_writeup_exists_and_names_the_licence_trap(self):
        text = WRITEUP.read_text(encoding="utf-8")
        self.assertIn("StatsBomb", text)
        self.assertIn("public", text)
        self.assertIn("socceraction", text)
        self.assertIn("xT", text)


if __name__ == "__main__":
    unittest.main()
