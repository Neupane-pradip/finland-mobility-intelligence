"""Synthetic tests: these records are not Tampere observations."""

import csv
import io
import tempfile
import unittest
from unittest.mock import patch
from datetime import date
from pathlib import Path
from zipfile import ZipFile

from scripts.inspect_gtfs import (
    WEEKDAYS,
    build_active_dates,
    check_references,
    inspect_feed,
    main,
    parse_date,
    parse_sequence,
    parse_time,
    read_rows,
    unique_rows,
    validate_calendar,
    validate_exceptions,
    validate_stop_times,
)


def calendar_row(**changes):
    row = {
        "service_id": "weekday",
        "start_date": "20261030",
        "end_date": "20261102",
        **{day: "0" for day in WEEKDAYS},
        "friday": "1",
        "monday": "1",
    }
    row.update(changes)
    return row


def visit(sequence, arrival, departure=None, **changes):
    row = {
        "trip_id": "trip_A",
        "stop_id": "0001",
        "stop_sequence": str(sequence),
        "arrival_time": arrival,
        "departure_time": arrival if departure is None else departure,
        "timepoint": "1",
    }
    row.update(changes)
    return row


def write_table(archive, name, headers, rows):
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    archive.writestr(name, text.getvalue())


class TestParsing(unittest.TestCase):
    def test_real_date(self):
        self.assertEqual(parse_date("20240229"), date(2024, 2, 29))

    def test_bad_dates(self):
        for value in ("20260229", "20261301", "2026-10-30", "", "2026103"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_date(value)

    def test_times(self):
        self.assertEqual(parse_time("8:00:00"), 28_800)
        self.assertEqual(parse_time("24:00:15"), 86_415)
        self.assertEqual(parse_time("25:10:00"), 90_600)
        self.assertEqual(parse_time("00:00:00"), 0)
        self.assertIsNone(parse_time(""))

    def test_bad_times(self):
        for value in ("24:60:00", "12:00:60", "-1:00:00", "12:00", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_time(value)

    def test_sequences(self):
        self.assertEqual(parse_sequence("0"), 0)
        self.assertEqual(parse_sequence("01"), 1)
        self.assertEqual(parse_sequence(str(2**63 - 1)), 2**63 - 1)
        for value in ("", "-1", "1.5", " ", "abc", "１", str(2**63)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_sequence(value)


class TestIdentifiers(unittest.TestCase):
    def test_ids_preserve_zeros(self):
        result = unique_rows(
            [{"stop_id": "0001"}, {"stop_id": "0002"}], "stop_id"
        )
        self.assertEqual(set(result), {"0001", "0002"})

    def test_bad_identifiers(self):
        cases = [
            [],
            [{"stop_id": ""}],
            [{"stop_id": " "}],
            [{"stop_id": "1"}, {"stop_id": "1"}],
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    unique_rows(rows, "stop_id")

    def test_reference_exists(self):
        self.assertEqual(
            check_references([{"route_id": "1"}], "route_id", {"1"}), 1
        )

    def test_reference_missing(self):
        for value in ("99", "", " "):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    check_references(
                        [{"route_id": value}], "route_id", {"1"}
                    )


class TestCalendars(unittest.TestCase):
    def test_inclusive_range_and_weekdays(self):
        calendar = validate_calendar([calendar_row()])
        active = build_active_dates(calendar, {})
        self.assertEqual(
            active["weekday"],
            {date(2026, 10, 30), date(2026, 11, 2)},
        )

    def test_bad_calendar(self):
        cases = [
            [calendar_row(service_id="")],
            [calendar_row(), calendar_row()],
            [calendar_row(start_date="20261103")],
            [calendar_row(friday="2")],
            [calendar_row(end_date="20260230")],
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    validate_calendar(rows)

    def test_add_remove_and_exception_only_service(self):
        calendar = validate_calendar([calendar_row()])
        exceptions = validate_exceptions([
            {
                "service_id": "weekday",
                "date": "20261030",
                "exception_type": "2",
            },
            {
                "service_id": "weekday",
                "date": "20261031",
                "exception_type": "1",
            },
            {
                "service_id": "special",
                "date": "20261101",
                "exception_type": "1",
            },
        ])
        active = build_active_dates(calendar, exceptions)

        self.assertNotIn(date(2026, 10, 30), active["weekday"])
        self.assertIn(date(2026, 10, 31), active["weekday"])
        self.assertEqual(active["special"], {date(2026, 11, 1)})

    def test_bad_exceptions(self):
        valid = {
            "service_id": "s",
            "date": "20261030",
            "exception_type": "1",
        }
        cases = [
            [{**valid, "service_id": ""}],
            [{**valid, "date": "20260230"}],
            [{**valid, "exception_type": "3"}],
            [valid, valid],
            [valid, {**valid, "exception_type": "2"}],
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    validate_exceptions(rows)

    def test_no_weekdays_can_be_enabled(self):
        row = calendar_row(friday="0", monday="0")
        active = build_active_dates(validate_calendar([row]), {})
        self.assertEqual(active["weekday"], set())

    def test_empty_weekly_calendar_with_explicit_dates(self):
        exceptions = validate_exceptions([{
            "service_id": "special",
            "date": "20261030",
            "exception_type": "1",
        }])
        active = build_active_dates({}, exceptions)
        self.assertEqual(active["special"], {date(2026, 10, 30)})


class TestStopTimes(unittest.TestCase):
    def validate(self, rows, trips=None):
        return validate_stop_times(
            rows,
            {"trip_A"} if trips is None else trips,
            {"0001"},
        )

    def test_valid_midnight_trip_and_sequence_gaps(self):
        result = self.validate([
            visit(0, "23:55:00"),
            visit(30, "24:00:15"),
        ])
        self.assertEqual(result["rows"], 2)
        self.assertEqual(result["after_midnight_rows"], 1)
        self.assertEqual(result["maximum_service_day_seconds"], 86_415)

    def test_input_order_does_not_define_visit_order(self):
        self.validate([
            visit(20, "09:10:00"),
            visit(10, "09:00:00"),
        ])

    def test_different_trips_can_share_sequences(self):
        self.validate([
            visit(1, "09:00:00"),
            visit(2, "09:10:00"),
            visit(1, "10:00:00", trip_id="trip_B"),
            visit(2, "10:10:00", trip_id="trip_B"),
        ], {"trip_A", "trip_B"})

    def test_bad_references(self):
        for changes in (
            {"trip_id": "missing"},
            {"stop_id": "missing"},
            {"trip_id": ""},
            {"stop_id": ""},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.validate([
                        visit(1, "09:00:00", **changes),
                        visit(2, "09:10:00"),
                    ])

    def test_duplicate_numeric_key(self):
        with self.assertRaisesRegex(ValueError, "Duplicate stop-time key"):
            self.validate([
                visit("01", "09:00:00"),
                visit("1", "09:10:00"),
            ])

    def test_bad_sequence(self):
        with self.assertRaises(ValueError):
            self.validate([
                visit("-1", "09:00:00"),
                visit(2, "09:10:00"),
            ])

    def test_departure_before_arrival(self):
        with self.assertRaisesRegex(ValueError, "Departure before arrival"):
            self.validate([
                visit(1, "09:00:00", "08:59:00"),
                visit(2, "09:10:00"),
            ])

    def test_backwards_trip_times(self):
        with self.assertRaisesRegex(ValueError, "Time moves backwards"):
            self.validate([
                visit(1, "09:10:00"),
                visit(2, "09:00:00"),
            ])

    def test_missing_approximate_intermediate_times_allowed(self):
        result = self.validate([
            visit(1, "09:00:00"),
            visit(2, "", timepoint="0"),
            visit(3, "09:10:00"),
        ])
        self.assertEqual(result["rows_with_missing_times"], 1)

    def test_missing_exact_times_fail(self):
        with self.assertRaisesRegex(ValueError, "Exact timepoint"):
            self.validate([
                visit(1, "09:00:00"),
                visit(2, "", timepoint="1"),
                visit(3, "09:10:00"),
            ])

    def test_missing_endpoint_times_fail(self):
        for rows in (
            [visit(1, "", timepoint="0"), visit(2, "09:10:00")],
            [visit(1, "09:00:00"), visit(2, "", timepoint="0")],
        ):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    self.validate(rows)

    def test_bad_time_and_timepoint(self):
        for changes in (
            {"arrival_time": "09:60:00"},
            {"timepoint": "2"},
        ):
            with self.subTest(changes=changes):
                row = visit(1, "09:00:00")
                row.update(changes)
                with self.assertRaises(ValueError):
                    self.validate([row, visit(2, "09:10:00")])

    def test_empty_and_single_visit_fail(self):
        for rows in ([], [visit(1, "09:00:00")]):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    self.validate(rows)

    def test_trip_without_visits_fails(self):
        with self.assertRaisesRegex(ValueError, "no stop-time records"):
            self.validate([
                visit(1, "09:00:00"),
                visit(2, "09:10:00"),
            ], {"trip_A", "trip_B"})

    def test_unsupported_on_demand_window_fails(self):
        with self.assertRaisesRegex(ValueError, "Unsupported on-demand"):
            self.validate([
                visit(
                    1, "09:00:00",
                    start_pickup_drop_off_window="09:00:00",
                ),
                visit(2, "09:10:00"),
            ])


class TestCsvReading(unittest.TestCase):
    def test_quoted_comma_and_utf8_bom(self):
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr(
                "stops.txt",
                '\ufeffstop_id,stop_name\n"0001","Stop, A"\n',
            )
        buffer.seek(0)

        with ZipFile(buffer) as archive:
            rows = list(read_rows(archive, "stops.txt", {"stop_id"}))

        self.assertEqual(rows[0]["stop_id"], "0001")
        self.assertEqual(rows[0]["stop_name"], "Stop, A")

    def test_bad_header_or_row(self):
        for text in (
            "name\nA\n",
            "stop_id,stop_id\n1,2\n",
            "stop_id,name\n1\n",
            "stop_id\n1,extra\n",
        ):
            with self.subTest(text=text):
                buffer = io.BytesIO()
                with ZipFile(buffer, "w") as archive:
                    archive.writestr("stops.txt", text)
                buffer.seek(0)

                with ZipFile(buffer) as archive:
                    with self.assertRaises(ValueError):
                        list(read_rows(
                            archive, "stops.txt", {"stop_id"}
                        ))


class TestFeedIntegration(unittest.TestCase):
    def test_duplicate_archive_names_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feed.zip"
            self.make_feed(path)
            with ZipFile(path, "a") as archive:
                with self.assertWarns(UserWarning):
                    archive.writestr("stops.txt", "stop_id\nother\n")
            with self.assertRaisesRegex(ValueError, "Duplicate ZIP"):
                inspect_feed(path)

    def test_archive_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feed.zip"
            self.make_feed(path)
            with patch("scripts.inspect_gtfs.MAX_UNCOMPRESSED_BYTES", 1):
                with self.assertRaisesRegex(ValueError, "size limit"):
                    inspect_feed(path)

    def test_failed_cli_removes_stale_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.zip"
            output = Path(directory) / "report.json"
            output.write_text('{"old_success": true}', encoding="utf-8")
            arguments = ["inspect_gtfs", "--zip", str(path), "--output", str(output)]
            with patch("sys.argv", arguments), patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(main(), 1)
            self.assertFalse(output.exists())

    def test_output_cannot_replace_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feed.zip"
            self.make_feed(path)
            original = path.read_bytes()
            arguments = ["inspect_gtfs", "--zip", str(path), "--output", str(path)]
            with patch("sys.argv", arguments), patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(main(), 1)
            self.assertEqual(path.read_bytes(), original)

    def make_feed(self, path, missing_service=False):
        """Build a tiny, completely synthetic GTFS ZIP."""
        with ZipFile(path, "w") as archive:
            write_table(
                archive, "agency.txt",
                ["agency_name", "agency_timezone"],
                [{
                    "agency_name": "Synthetic Transit",
                    "agency_timezone": "Europe/Helsinki",
                }],
            )
            write_table(
                archive, "stops.txt", ["stop_id"],
                [{"stop_id": "0001"}],
            )
            write_table(
                archive, "routes.txt", ["route_id"],
                [{"route_id": "1"}],
            )
            write_table(
                archive, "trips.txt",
                ["trip_id", "route_id", "service_id"],
                [{
                    "trip_id": "trip_A",
                    "route_id": "1",
                    "service_id": (
                        "missing" if missing_service else "special"
                    ),
                }],
            )
            write_table(
                archive, "calendar_dates.txt",
                ["service_id", "date", "exception_type"],
                [{
                    "service_id": "special",
                    "date": "20261030",
                    "exception_type": "1",
                }],
            )
            write_table(
                archive, "stop_times.txt",
                [
                    "trip_id", "stop_id", "stop_sequence",
                    "arrival_time", "departure_time", "timepoint",
                ],
                [
                    visit(1, "23:55:00"),
                    visit(2, "24:00:15"),
                ],
            )

    def test_full_exception_only_feed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feed.zip"
            self.make_feed(path)
            report = inspect_feed(path)

        self.assertEqual(report["counts"]["trips"], 1)
        self.assertEqual(report["counts"]["calendar"], 0)
        self.assertEqual(report["counts"]["combined_services"], 1)
        self.assertEqual(report["stop_times"]["rows"], 2)
        self.assertEqual(
            report["service_dates_for_trips"]["first"], "2026-10-30"
        )

    def test_missing_service_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feed.zip"
            self.make_feed(path, missing_service=True)

            with self.assertRaisesRegex(ValueError, "Unknown service_id"):
                inspect_feed(path)

    def test_missing_required_files_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feed.zip"
            with ZipFile(path, "w"):
                pass

            with self.assertRaisesRegex(ValueError, "Missing files"):
                inspect_feed(path)


if __name__ == "__main__":
    unittest.main()
