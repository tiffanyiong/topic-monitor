import importlib.util
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "run_daily.py"
SPEC = importlib.util.spec_from_file_location("run_daily", MODULE_PATH)
run_daily = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_daily)


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "schedule_time": "08:00",
            "schedule_timezone": "America/Los_Angeles",
        }

    def test_run_before_schedule_is_skipped(self):
        now = datetime(2026, 7, 10, 7, 59)
        with patch.object(run_daily, "current_local_datetime", return_value=now):
            self.assertFalse(run_daily.should_run_for_schedule(self.config))

    def test_run_at_schedule_is_allowed(self):
        now = datetime(2026, 7, 10, 8, 0)
        with patch.object(run_daily, "current_local_datetime", return_value=now):
            self.assertTrue(run_daily.should_run_for_schedule(self.config))

    def test_delayed_run_after_schedule_is_allowed(self):
        now = datetime(2026, 7, 10, 9, 16)
        with patch.object(run_daily, "current_local_datetime", return_value=now):
            self.assertTrue(run_daily.should_run_for_schedule(self.config))

    def test_invalid_schedule_falls_back_to_eight(self):
        self.assertEqual((8, 0), run_daily.scheduled_time_parts({"schedule_time": "25:99"}))

    def test_sent_marker_blocks_another_run_today(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = Path(temp_dir) / "last_sent_date"
            marker.write_text("2026-07-10")
            now = datetime(2026, 7, 10, 11, 0)
            with patch.object(run_daily, "LAST_SENT_FILE", marker), patch.object(
                run_daily, "current_local_datetime", return_value=now
            ):
                self.assertTrue(run_daily.already_sent_today(self.config))

    def test_github_output_records_delivery_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "github-output"
            with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}):
                run_daily.set_github_output("sent_today", "true")
            self.assertEqual("sent_today=true\n", output.read_text())


if __name__ == "__main__":
    unittest.main()
