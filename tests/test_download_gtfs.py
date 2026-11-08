"""Test the downloader using a simulated connection failure."""

import io
import json
import tempfile
import unittest
from scripts.download_gtfs import (download_with_retries)
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from scripts.download_gtfs import main


class TestDownloadFailure(unittest.TestCase):
    def test_failed_download_is_logged(self):
        # Use a temporary folder so the real retrieval log stays untouched.
        with tempfile.TemporaryDirectory() as folder:
            fake_root = Path(folder)
            fake_script = fake_root / "scripts" / "download_gtfs.py"

            # main() uses __file__ to find the project folder.
            with patch(
                "scripts.download_gtfs.__file__",
                str(fake_script),
            ):
                # Pretend the download encountered a connection error.
                with patch(
                    "scripts.download_gtfs.download_with_retries",
                    side_effect=URLError("Simulated connection failure"),
                ):
                    with patch("sys.stderr", new_callable=io.StringIO):
                        exit_code = main()

            self.assertEqual(exit_code, 1)

            log_path = fake_root / "data" / "raw" / "retrievals.jsonl"
            lines = log_path.read_text(encoding="utf-8").splitlines()

            # One failed attempt should produce exactly one record.
            self.assertEqual(len(lines), 1)

            record = json.loads(lines[0])
            self.assertEqual(record["status"], "failed")
            self.assertEqual(record["error_type"], "URLError")
            self.assertIn(
                "Simulated connection failure",
                record["error_message"],
            )
            self.assertIn("started_at_utc", record)
            self.assertIn("completed_at_utc", record)

class TestDownloadRetries(unittest.TestCase):
    def test_connection_failure_stops_after_three_attempts(self):
        with patch(
            "scripts.download_gtfs.download_snapshot",
            side_effect=URLError("Simulated connection failure"),
        ) as download:
            # Skip real waiting during the test.
            with patch("scripts.download_gtfs.time.sleep") as sleep:
                with patch("sys.stdout", new_callable=io.StringIO):
                    with self.assertRaises(URLError):
                        download_with_retries("https://example.com", Path("."))

        self.assertEqual(download.call_count, 3)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [1, 2],
        )

    def test_invalid_zip_is_not_retried(self):
        with patch(
            "scripts.download_gtfs.download_snapshot",
            side_effect=ValueError("The downloaded file is not a ZIP archive"),
        ) as download:
            with patch("scripts.download_gtfs.time.sleep") as sleep:
                with self.assertRaises(ValueError):
                    download_with_retries("https://example.com", Path("."))

        self.assertEqual(download.call_count, 1)
        sleep.assert_not_called()

    def test_second_attempt_succeeds(self):
        # This is a fake result. No file is downloaded or created.
        expected = (Path("fake_snapshot.zip"), "fake_hash", 100)

        with patch(
            "scripts.download_gtfs.download_snapshot",
            side_effect=[
                URLError("Temporary connection problem"),
                expected,
            ],
        ) as download:
            with patch("scripts.download_gtfs.time.sleep") as sleep:
                with patch("sys.stdout", new_callable=io.StringIO):
                    result = download_with_retries(
                        "https://example.com",
                        Path("."),
                    )

        self.assertEqual(result, expected)
        self.assertEqual(download.call_count, 2)
        sleep.assert_called_once_with(1)

if __name__ == "__main__":
    unittest.main()