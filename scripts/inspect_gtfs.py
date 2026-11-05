import csv
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile


# ------------------------------------------------------------
# 1. Validate stop identifiers
# ------------------------------------------------------------
def validate_stop_ids(rows):
    """Return the stop count and validated stop-ID lookup."""

    seen_ids = set()
    total_stops = 0
    empty_ids = 0
    duplicate_ids = 0

    for row in rows:
        total_stops += 1
        stop_id = row["stop_id"]

        # Check for blanks without changing the original identifier.
        if not stop_id.strip():
            empty_ids += 1
        elif stop_id in seen_ids:
            duplicate_ids += 1
        else:
            seen_ids.add(stop_id)

    if total_stops == 0:
        raise ValueError("No stop records")

    if empty_ids > 0 or duplicate_ids > 0:
        raise ValueError(
            f"Stop ID validation failed: {empty_ids} empty IDs, "
            f"{duplicate_ids} repeated occurrences"
        )

    return total_stops, seen_ids


# ------------------------------------------------------------
# 2. Validate route identifiers
# ------------------------------------------------------------
def validate_route_ids(rows):
    """Reject blank or repeated route IDs and return their lookup."""

    route_ids = set()
    total_routes = 0

    for row in rows:
        total_routes += 1
        route_id = row["route_id"]

        if not route_id.strip():
            raise ValueError(
                f"Blank route_id in route record {total_routes}"
            )

        if route_id in route_ids:
            raise ValueError(f"Duplicate route_id: {route_id!r}")

        route_ids.add(route_id)

    if total_routes == 0:
        raise ValueError("No route records")

    return route_ids


# ------------------------------------------------------------
# 3. Validate trip references to routes
# ------------------------------------------------------------
def validate_trip_routes(rows, route_ids):
    """Check that every trip references an existing route."""

    total_trips = 0
    invalid_references = 0
    examples = []

    for row in rows:
        total_trips += 1
        route_id = row["route_id"]

        if not route_id.strip() or route_id not in route_ids:
            invalid_references += 1

            # Limit stored examples to keep error messages manageable.
            if len(examples) < 3:
                examples.append(
                    f"trip_id={row['trip_id']!r}, "
                    f"route_id={route_id!r}"
                )

    if total_trips == 0:
        raise ValueError("No trip records")

    if invalid_references > 0:
        raise ValueError(
            f"Trip route validation failed: "
            f"{invalid_references} invalid references. "
            f"Examples: {'; '.join(examples)}"
        )

    return total_trips


# ------------------------------------------------------------
# 4. Validate trip identifiers
# ------------------------------------------------------------
def validate_trip_ids(rows):
    """Reject blank or repeated trip IDs and return their lookup."""

    trip_ids = set()
    total_trips = 0

    for row in rows:
        total_trips += 1
        trip_id = row["trip_id"]

        if not trip_id.strip():
            raise ValueError(
                f"Blank trip_id in trip record {total_trips}"
            )

        if trip_id in trip_ids:
            raise ValueError(f"Duplicate trip_id: {trip_id!r}")

        trip_ids.add(trip_id)

    if total_trips == 0:
        raise ValueError("No trip records")

    return trip_ids


# ------------------------------------------------------------
# 5. Validate stop-time references
# ------------------------------------------------------------
def validate_stop_time_references(rows, trip_ids, stop_ids):
    """Check that every stop visit references an existing trip and stop."""

    total_rows = 0
    invalid_rows = 0
    examples = []

    for row in rows:
        total_rows += 1
        trip_id = row["trip_id"]
        stop_id = row["stop_id"]

        trip_exists = trip_id in trip_ids
        stop_exists = stop_id in stop_ids

        if not trip_exists or not stop_exists:
            # Count each invalid record once.
            invalid_rows += 1

            if len(examples) < 3:
                examples.append(
                    f"record={total_rows}, "
                    f"trip_id={trip_id!r}, stop_id={stop_id!r}"
                )

    if total_rows == 0:
        raise ValueError("No stop-time records")

    if invalid_rows > 0:
        raise ValueError(
            f"Stop-time reference validation failed: "
            f"{invalid_rows} invalid rows. "
            f"Examples: {'; '.join(examples)}"
        )

    return total_rows


# ------------------------------------------------------------
# 6. Validate stop-time composite keys
# ------------------------------------------------------------
def validate_stop_time_keys(rows):
    """Check sequences and reject repeated trip/sequence pairs."""

    seen_keys = set()
    total_rows = 0

    for row in rows:
        total_rows += 1
        trip_id = row["trip_id"]
        sequence_text = row["stop_sequence"]

        # Require nonnegative integers written with ASCII digits.
        if (
            not sequence_text
            or not sequence_text.isascii()
            or not sequence_text.isdecimal()
        ):
            raise ValueError(
                f"Invalid stop_sequence in record {total_rows}: "
                f"{sequence_text!r}"
            )

        # Numeric comparison makes "01" and "1" equivalent.
        sequence = int(sequence_text)
        key = (trip_id, sequence)

        if key in seen_keys:
            raise ValueError(f"Duplicate stop-time key: {key!r}")

        seen_keys.add(key)

    if total_rows == 0:
        raise ValueError("No stop-time records")

    return total_rows


# ------------------------------------------------------------
# 7. Collect service identifiers — NEW
# ------------------------------------------------------------
def collect_service_ids(rows):
    """Collect nonblank service IDs from one calendar file."""

    service_ids = set()

    for record_number, row in enumerate(rows, start=1):
        service_id = row["service_id"]

        if not service_id.strip():
            raise ValueError(
                f"Blank service_id in calendar record {record_number}"
            )

        # Repeated service IDs are expected in calendar_dates.txt.
        # One service can have multiple date exceptions.
        service_ids.add(service_id)

    return service_ids

def validate_trip_services(rows, service_ids):
    """Check that every trip references a known service identifier."""

    total_trips = 0
    invalid_references = 0
    examples = []

    for row in rows:
        total_trips += 1
        service_id = row["service_id"]

        if not service_id.strip() or service_id not in service_ids:
            invalid_references += 1

            # Keep only a few examples for a readable error message.
            if len(examples) < 3:
                examples.append(
                    f"trip_id={row['trip_id']!r}, "
                    f"service_id={service_id!r}"
                )

    if total_trips == 0:
        raise ValueError("No trip records")

    if invalid_references > 0:
        raise ValueError(
            f"Trip service validation failed: "
            f"{invalid_references} invalid references. "
            f"Examples: {'; '.join(examples)}"
        )

    return total_trips


# ------------------------------------------------------------
# 8. Read the real feed and run the checks
# ------------------------------------------------------------
def main():
    """Inspect the ZIP, validate core records, and collect services."""

    # Locate the download relative to this script.
    project_root = Path(__file__).resolve().parent.parent
    zip_path = project_root / "data" / "raw" / "gtfs_tampere.zip"

    print("Project folder:", project_root)
    print("ZIP file:", zip_path)
    print("ZIP exists:", zip_path.is_file())

    if not zip_path.is_file():
        raise FileNotFoundError(f"GTFS ZIP not found: {zip_path}")

    # All archive-reading blocks below remain inside this with block.
    with ZipFile(zip_path, "r") as archive:

        # List archive contents without extracting them.
        for entry in archive.infolist():
            print(entry.filename, entry.file_size)

        # Read and validate stops.
        with archive.open("stops.txt") as raw_file:
            with TextIOWrapper(
                raw_file,
                encoding="utf-8-sig",
                newline="",
            ) as text_file:
                reader = csv.DictReader(text_file)

                if not reader.fieldnames or "stop_id" not in reader.fieldnames:
                    raise ValueError(
                        "stops.txt is missing the stop_id column"
                    )

                total_stops, stop_ids = validate_stop_ids(reader)

                print(
                    f"PASS: {total_stops} stop records "
                    "have nonblank, unique IDs"
                )

        # Read and validate routes.
        with archive.open("routes.txt") as raw_file:
            with TextIOWrapper(
                raw_file,
                encoding="utf-8-sig",
                newline="",
            ) as text_file:
                reader = csv.DictReader(text_file)

                if not reader.fieldnames or "route_id" not in reader.fieldnames:
                    raise ValueError(
                        "routes.txt is missing the route_id column"
                    )

                route_ids = validate_route_ids(reader)

                print(
                    f"PASS: {len(route_ids)} route records "
                    "have nonblank, unique IDs"
                )

        # Check trip references against the validated route lookup.
        with archive.open("trips.txt") as raw_file:
            with TextIOWrapper(
                raw_file,
                encoding="utf-8-sig",
                newline="",
            ) as text_file:
                reader = csv.DictReader(text_file)
                required_columns = {"trip_id", "route_id"}

                if not required_columns.issubset(reader.fieldnames or []):
                    raise ValueError(
                        "trips.txt must contain trip_id and route_id"
                    )

                total_trips = validate_trip_routes(reader, route_ids)

                print(
                    f"PASS: {total_trips} trip records "
                    "reference existing routes"
                )

        # Reopen trips because the previous reader is exhausted.
        with archive.open("trips.txt") as raw_file:
            with TextIOWrapper(
                raw_file,
                encoding="utf-8-sig",
                newline="",
            ) as text_file:
                reader = csv.DictReader(text_file)

                if not reader.fieldnames or "trip_id" not in reader.fieldnames:
                    raise ValueError(
                        "trips.txt is missing the trip_id column"
                    )

                trip_ids = validate_trip_ids(reader)

                print(
                    f"PASS: {len(trip_ids)} trip records "
                    "have nonblank, unique IDs"
                )

        # Check stop-time references against both validated lookups.
        with archive.open("stop_times.txt") as raw_file:
            with TextIOWrapper(
                raw_file,
                encoding="utf-8-sig",
                newline="",
            ) as text_file:
                reader = csv.DictReader(text_file)
                required_columns = {"trip_id", "stop_id"}

                if not required_columns.issubset(reader.fieldnames or []):
                    raise ValueError(
                        "stop_times.txt must contain trip_id and stop_id"
                    )

                total_stop_times = validate_stop_time_references(
                    reader,
                    trip_ids,
                    stop_ids,
                )

                print(
                    f"PASS: {total_stop_times} stop-time records "
                    "reference existing trips and stops"
                )

        # Reopen stop times to validate composite keys.
        with archive.open("stop_times.txt") as raw_file:
            with TextIOWrapper(
                raw_file,
                encoding="utf-8-sig",
                newline="",
            ) as text_file:
                reader = csv.DictReader(text_file)
                required_columns = {"trip_id", "stop_sequence"}

                if not required_columns.issubset(reader.fieldnames or []):
                    raise ValueError(
                        "stop_times.txt must contain trip_id "
                        "and stop_sequence"
                    )

                total_keys = validate_stop_time_keys(reader)

                print(
                    f"PASS: {total_keys} stop-time records "
                    "have valid sequences and unique trip/sequence keys"
                )

        # NEW: Build the service lookup from both calendar files.
        service_ids = set()
        available_files = set(archive.namelist())

        calendar_files = [
            name
            for name in ("calendar.txt", "calendar_dates.txt")
            if name in available_files
        ]

        if not calendar_files:
            raise ValueError(
                "Neither calendar.txt nor calendar_dates.txt is present"
            )

        for filename in calendar_files:
            with archive.open(filename) as raw_file:
                with TextIOWrapper(
                    raw_file,
                    encoding="utf-8-sig",
                    newline="",
                ) as text_file:
                    reader = csv.DictReader(text_file)

                    if (
                        not reader.fieldnames
                        or "service_id" not in reader.fieldnames
                    ):
                        raise ValueError(
                            f"{filename} is missing the service_id column"
                        )

                    file_service_ids = collect_service_ids(reader)

                    # Combine IDs while retaining only distinct values.
                    service_ids.update(file_service_ids)

                    print(
                        f"{filename}: "
                        f"{len(file_service_ids)} distinct service IDs"
                    )

        if not service_ids:
            raise ValueError("No service IDs found in calendar files")

        print("Combined distinct service IDs:", len(service_ids))

        # Check trips after collecting IDs from both calendar files.
        with archive.open("trips.txt") as raw_file:
            with TextIOWrapper(
                raw_file,
                encoding="utf-8-sig",
                newline="",
            ) as text_file:
                reader = csv.DictReader(text_file)
                required_columns = {"trip_id", "service_id"}

                if not required_columns.issubset(reader.fieldnames or []):
                    raise ValueError(
                        "trips.txt must contain trip_id and service_id"
                    )

                total_trips = validate_trip_services(reader, service_ids)

                print(
                    f"PASS: {total_trips} trip records "
                    "reference services in the calendar lookup"
                )


# Execute main only when running this file directly.
# Importing functions from tests does not inspect the downloaded ZIP.
if __name__ == "__main__":
    main()