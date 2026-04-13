"""Smoke tests for backend_bridge + native lib (no GUI)."""

from __future__ import annotations

import os
import sys
import unittest

# Project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import backend_bridge as bb  # noqa: E402


class TestBackendSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bb.set_working_directory()
        bb.ensure_demo_data_files()
        bb.load_library()
        ok, msg = bb.import_all_csvs()
        assert ok, msg

    def test_read_room_records(self):
        rooms = bb.read_all_room_records()
        self.assertGreater(len(rooms), 0)
        for r in rooms:
            self.assertIn("id", r)
            self.assertIn("name", r)
            self.assertIn("is_lab", r)

    def test_import_rooms_csv(self):
        ok, msg = bb.import_rooms_csv()
        self.assertTrue(ok, msg)

    def test_import_all_csvs(self):
        ok, msg = bb.import_all_csvs()
        self.assertTrue(ok, msg)

    def test_generate_timetable(self):
        self.assertTrue(bb.generate_timetable_native())
        lec = bb.read_all_lectures()
        self.assertGreater(len(lec), 0)

    def test_room_map_matches_lectures(self):
        rooms = bb.read_room_map()
        for L in bb.read_all_lectures():
            rid = int(L.get("room_id") or 0)
            if rid:
                self.assertIn(rid, rooms)

    def test_get_faculty_schedule_native(self):
        self.assertTrue(bb.generate_timetable_native())
        lec = bb.get_faculty_schedule_lectures(1)
        self.assertIsInstance(lec, list)
        self.assertGreater(len(lec), 0)
        self.assertIn("subject", lec[0])

    def test_login_admin(self):
        self.assertTrue(bb.login_admin("admin", "admin123"))
        self.assertFalse(bb.login_admin("admin", "wrong"))

    def test_login_faculty_demo(self):
        fid = bb.login_faculty("sample", "sample123")
        self.assertIsNotNone(fid)
        self.assertEqual(int(fid), 1)


if __name__ == "__main__":
    unittest.main()
