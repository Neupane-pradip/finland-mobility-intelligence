"""Inspect a local GTFS ZIP. Only Python's standard library is needed."""

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from io import TextIOWrapper
from pathlib import Path
from zipfile import BadZipFile, ZipFile


WEEKDAYS = (
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
)
# This is a local processing limit, not a GTFS rule.
MAX_UNCOMPRESSED_BYTES = 1_000_000_000


def parse_date(value):
    """Read a real calendar date written as YYYYMMDD."""
    if not re.fullmatch(r"[0-9]{8}", value):
        raise ValueError(f"Invalid date: {value!r}")
    return date(int(value[:4]), int(value[4:6]), int(value[6:]))


def parse_time(value):
    """Keep missing times as None and allow times such as 24:00:15."""
    if value == "":
        return None
    if not re.fullmatch(r"[0-9]{1,2}:[0-9]{2}:[0-9]{2}", value):
        raise ValueError(f"Invalid time: {value!r}")
    hours, minutes, seconds = map(int, value.split(":"))
    if minutes > 59 or seconds > 59:
        raise ValueError(f"Invalid time: {value!r}")
    return hours * 3600 + minutes * 60 + seconds


def parse_sequence(value):
    """Convert the sequence to an integer without accepting signs or spaces."""
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError(f"Invalid stop_sequence: {value!r}")
    number = int(value)
    if number > 2**63 - 1:
        raise ValueError("stop_sequence exceeds SQLite's integer limit")
    return number


def read_rows(archive, filename, required_headers):
    """Read one CSV row at a time directly from the ZIP."""
    with archive.open(filename) as raw_file:
        with TextIOWrapper(raw_file, encoding="utf-8-sig", newline="") as text:
            reader = csv.DictReader(text, strict=True)
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)):
                raise ValueError(f"Duplicate headers in {filename}")
            if not required_headers.issubset(headers):
                raise ValueError(f"Missing required headers in {filename}")
            for row in reader:
                # DictReader uses None for extra fields or missing values.
                if None in row or None in row.values():
                    raise ValueError(f"Wrong field count in {filename}, line {reader.line_num}")
                yield row


def unique_rows(rows, id_column):
    """Build an ID lookup. Do not convert IDs to numbers or strip them."""
    result = {}
    for row in rows:
        identifier = row[id_column]
        if not identifier.strip():
            raise ValueError(f"Blank {id_column}")
        if identifier in result:
            raise ValueError(f"Duplicate {id_column}: {identifier!r}")
        result[identifier] = row
    if not result:
        raise ValueError(f"No records for {id_column}")
    return result


def check_references(rows, column, known_ids):
    """Check that each referenced ID exists in its parent table."""
    count = 0
    for row in rows:
        value = row[column]
        if not value.strip() or value not in known_ids:
            raise ValueError(f"Unknown {column}: {value!r}")
        count += 1
    return count


def validate_calendar(rows):
    """Validate weekly patterns. An empty calendar is allowed."""
    result = {}
    for row in rows:
        service = row["service_id"]
        if not service.strip() or service in result:
            raise ValueError(f"Blank or duplicate calendar service_id: {service!r}")
        start = parse_date(row["start_date"])
        end = parse_date(row["end_date"])
        if start > end:
            raise ValueError(f"Calendar starts after it ends: {service!r}")
        if any(row[day] not in ("0", "1") for day in WEEKDAYS):
            raise ValueError(f"Invalid weekday flag: {service!r}")
        result[service] = row
    return result


def validate_exceptions(rows):
    """A service may have several exceptions, but only one per date."""
    result = {}
    for row in rows:
        service = row["service_id"]
        day = parse_date(row["date"])
        key = (service, day)
        if not service.strip() or key in result:
            raise ValueError(f"Blank service or duplicate exception: {key!r}")
        if row["exception_type"] not in ("1", "2"):
            raise ValueError(f"Invalid exception_type: {row['exception_type']!r}")
        result[key] = row["exception_type"]
    return result


def build_active_dates(calendar, exceptions):
    """Expand weekly patterns first, then add or remove exception dates."""
    active = {}
    for service, row in calendar.items():
        days = set()
        current = parse_date(row["start_date"])
        end = parse_date(row["end_date"])
        while current <= end:
            if row[WEEKDAYS[current.weekday()]] == "1":
                days.add(current)
            if current == end:
                break
            current += timedelta(days=1)
        active[service] = days
    for (service, day), exception_type in exceptions.items():
        days = active.setdefault(service, set())
        if exception_type == "1":
            days.add(day)
        else:
            days.discard(day)
    return active


def validate_stop_times(rows, trip_ids, stop_ids):
    """Check visits and times, including trips whose rows arrive out of order."""
    result = {
        "rows": 0, "after_midnight_rows": 0,
        "after_midnight_example": None, "maximum_service_day_seconds": None,
        "rows_with_missing_times": 0,
    }
    unsupported = (
        "location_group_id", "location_id",
        "start_pickup_drop_off_window", "end_pickup_drop_off_window",
    )
    # A temporary SQLite file avoids keeping millions of visits in Python memory.
    # This is only a sorting workspace, not the project's future database.
    connection = sqlite3.connect("")
    try:
        connection.execute(
            "CREATE TABLE visits (trip TEXT, sequence INTEGER, arrival INTEGER, "
            "departure INTEGER, PRIMARY KEY (trip, sequence)) WITHOUT ROWID"
        )
        for row in rows:
            if any(row.get(field, "") for field in unsupported):
                raise ValueError("Unsupported on-demand location or time window")
            trip = row["trip_id"]
            if trip not in trip_ids or row["stop_id"] not in stop_ids:
                raise ValueError(f"Unknown trip_id or stop_id: {row!r}")
            sequence = parse_sequence(row["stop_sequence"])
            arrival = parse_time(row["arrival_time"])
            departure = parse_time(row["departure_time"])
            timepoint = row.get("timepoint", "") or "1"
            if timepoint not in ("0", "1"):
                raise ValueError(f"Invalid timepoint: {timepoint!r}")
            missing = arrival is None or departure is None
            if missing and timepoint == "1":
                raise ValueError(f"Exact timepoint needs both times: {trip!r}")
            if not missing and departure < arrival:
                raise ValueError(f"Departure before arrival: {trip!r}")
            try:
                connection.execute(
                    "INSERT INTO visits VALUES (?, ?, ?, ?)",
                    (trip, sequence, arrival, departure),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(f"Duplicate stop-time key: {(trip, sequence)!r}") from error
            result["rows"] += 1
            result["rows_with_missing_times"] += int(missing)
            known = [value for value in (arrival, departure) if value is not None]
            if known:
                maximum = max(known)
                old_maximum = result["maximum_service_day_seconds"]
                if old_maximum is None or maximum > old_maximum:
                    result["maximum_service_day_seconds"] = maximum
                if maximum >= 86400:
                    result["after_midnight_rows"] += 1
                    if result["after_midnight_example"] is None:
                        result["after_midnight_example"] = dict(row)

        # Numeric sequence order matters; CSV row order does not.
        seen_trips = set()
        previous_trip = None
        previous_time = None
        visit_count = 0
        last_missing = False
        for trip, sequence, arrival, departure in connection.execute(
            "SELECT trip, sequence, arrival, departure FROM visits ORDER BY trip, sequence"
        ):
            missing = arrival is None or departure is None
            if trip != previous_trip:
                if previous_trip is not None and (visit_count < 2 or last_missing):
                    raise ValueError(f"Trip needs two visits and endpoint times: {previous_trip!r}")
                if missing:
                    raise ValueError(f"First visit needs both times: {trip!r}")
                seen_trips.add(trip)
                previous_trip = trip
                previous_time = None
                visit_count = 0
            for value in (arrival, departure):
                if value is not None:
                    if previous_time is not None and value < previous_time:
                        raise ValueError(f"Time moves backwards: {trip!r}, sequence {sequence}")
                    previous_time = value
            visit_count += 1
            last_missing = missing
        if previous_trip is not None and (visit_count < 2 or last_missing):
            raise ValueError(f"Trip needs two visits and endpoint times: {previous_trip!r}")
        if set(trip_ids) - seen_trips:
            raise ValueError("Some trips have no stop-time records")
        if result["rows"] == 0:
            raise ValueError("No stop-time records")
        return result
    finally:
        connection.close()


def inspect_feed(zip_path):
    """Validate the supported schedule tables and return a JSON-ready report."""
    zip_path = Path(zip_path)
    # Hash in small chunks so the complete ZIP need not be loaded into memory.
    fingerprint = hashlib.sha256()
    with zip_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            fingerprint.update(chunk)

    with ZipFile(zip_path) as archive:
        names = archive.namelist()
        required = {"agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}
        if not required.issubset(names):
            raise ValueError(f"Missing files: {sorted(required - set(names))}")
        if not {"calendar.txt", "calendar_dates.txt"}.intersection(names):
            raise ValueError("Missing files: calendar.txt or calendar_dates.txt is needed")
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP member names")
        if sum(info.file_size for info in archive.infolist()) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Archive exceeds the local uncompressed-size limit")

        stops = unique_rows(read_rows(archive, "stops.txt", {"stop_id"}), "stop_id")
        routes = unique_rows(read_rows(archive, "routes.txt", {"route_id"}), "route_id")
        trips = unique_rows(
            read_rows(archive, "trips.txt", {"trip_id", "route_id", "service_id"}), "trip_id"
        )
        agencies = list(read_rows(archive, "agency.txt", {"agency_timezone"}))
        if not agencies:
            raise ValueError("No agency records")
        calendar = {}
        exceptions = {}
        if "calendar.txt" in names:
            headers = {"service_id", "start_date", "end_date", *WEEKDAYS}
            calendar = validate_calendar(read_rows(archive, "calendar.txt", headers))
        if "calendar_dates.txt" in names:
            headers = {"service_id", "date", "exception_type"}
            exceptions = validate_exceptions(read_rows(archive, "calendar_dates.txt", headers))
        active = build_active_dates(calendar, exceptions)
        check_references(trips.values(), "route_id", routes)
        check_references(trips.values(), "service_id", active)
        stop_times = validate_stop_times(
            read_rows(archive, "stop_times.txt", {
                "trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time",
            }), trips, stops,
        )

    referenced = {row["service_id"] for row in trips.values()}
    days = set()
    for service in referenced:
        days.update(active[service])
    empty_services = sorted(service for service in referenced if not active[service])
    return {
        "input_path": str(zip_path.resolve()),
        "input_bytes": zip_path.stat().st_size,
        "sha256": fingerprint.hexdigest(),
        "inspected_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive_files": names,
        "counts": {
            "agency": len(agencies), "stops": len(stops), "routes": len(routes),
            "trips": len(trips), "stop_times": stop_times["rows"],
            "calendar": len(calendar), "calendar_dates": len(exceptions),
            "combined_services": len(active),
        },
        "agency_timezones": sorted({row["agency_timezone"] for row in agencies}),
        "stop_times": stop_times,
        "service_dates_for_trips": {
            "first": min(days).isoformat() if days else None,
            "last": max(days).isoformat() if days else None,
            "distinct_dates": len(days),
            "services_without_active_dates": empty_services,
        },
        "warnings": [f"Service has no active dates: {service}" for service in empty_services],
        "scope_and_limitations": [
            "Conventional fixed-stop schedules only; not full GTFS compliance validation.",
            "Coordinates, location types, agency IDs, timezone names, route types and most enums are not validated.",
            "Shapes, fares, transfers and other optional relationships are not validated.",
            "Not every required or conditionally required GTFS field is checked.",
            "On-demand locations and time windows are unsupported.",
            "Redundant calendar exceptions and stable IDs across snapshots are not checked.",
            "Endpoint times are required by project policy; hours have one or two digits.",
            "No UTC event conversion or realtime compatibility validation is performed.",
            "Service date bounds do not imply service on every intervening date.",
            "Times after midnight do not extend service-date coverage.",
            "Planned schedules do not establish actual arrivals, demand or reliability.",
        ],
    }


def main():
    """Choose paths, remove an old report, inspect, and save the new report."""
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, default=root / "data/raw/gtfs_tampere.zip")
    parser.add_argument("--output", type=Path, default=root / "reports/inspection.json")
    args = parser.parse_args()
    try:
        # Never delete or overwrite the source ZIP through an output-path mistake.
        if args.zip.resolve() == args.output.resolve():
            raise ValueError("Input ZIP and output report must have different paths")
        args.output.unlink(missing_ok=True)
        report = inspect_feed(args.zip)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError, BadZipFile, csv.Error, RuntimeError, sqlite3.Error) as error:
        print(f"Inspection failed: {error}", file=sys.stderr)
        return 1
    print(f"Inspection passed. Report: {args.output}")
    for warning in report["warnings"]:
        print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
