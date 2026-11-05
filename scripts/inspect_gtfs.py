import csv
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile


# SECTION 1: Reusable stop-ID validation
def validate_stop_ids(rows):
    """Check stop IDs and return the record count if validation passes."""

    seen_ids = set()
    total_stops = 0
    empty_ids = 0
    duplicate_ids = 0

    for row in rows:
        total_stops += 1

        # Preserve the original text, including leading zeros.
        stop_id = row["stop_id"]

        # Check for blank IDs without changing the original value.
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

def validate_trip_routes(rows, route_ids):
    """Check that every trip references a route in the lookup."""

    total_trips = 0
    invalid_references = 0
    examples = []

    for row in rows:
        total_trips += 1
        route_id = row["route_id"]

        # Reject blank references and IDs absent from routes.txt.
        if not route_id.strip() or route_id not in route_ids:
            invalid_references += 1

            # Keep only a few examples so error messages stay manageable.
            if len(examples) < 3:
                examples.append(
                    f"trip_id={row['trip_id']!r}, route_id={route_id!r}"
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

def validate_route_ids(rows):
    """Reject blank or repeated route IDs and return the valid ID set."""

    route_ids = set()
    total_routes = 0

    for row in rows:
        total_routes += 1
        route_id = row["route_id"]

        # Preserve the original ID, but reject whitespace-only values.
        if not route_id.strip():
            raise ValueError(
                f"Blank route_id in route record {total_routes}"
            )

        # Check before adding: a set would otherwise hide duplicates.
        if route_id in route_ids:
            raise ValueError(f"Duplicate route_id: {route_id!r}")

        route_ids.add(route_id)

    if total_routes == 0:
        raise ValueError("No route records")

    return route_ids

def validate_trip_ids(rows):
    """Reject blank or repeated trip IDs and return the valid ID set."""

    trip_ids = set()
    total_trips = 0

    for row in rows:
        total_trips += 1
        trip_id = row["trip_id"]

        # Preserve the original ID, including any leading zeros.
        if not trip_id.strip():
            raise ValueError(
                f"Blank trip_id in trip record {total_trips}"
            )

        # Check before adding so the set cannot hide duplicates.
        if trip_id in trip_ids:
            raise ValueError(f"Duplicate trip_id: {trip_id!r}")

        trip_ids.add(trip_id)

    if total_trips == 0:
        raise ValueError("No trip records")

    return trip_ids

def validate_stop_time_references(rows, trip_ids, stop_ids):
    """Check that each stop visit references an existing trip and stop."""

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
            # Count an invalid row once, even if both references fail.
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

def validate_stop_time_keys(rows):
    """Check sequence values and reject repeated trip/sequence pairs."""

    seen_keys = set()
    total_rows = 0

    for row in rows:
        total_rows += 1
        trip_id = row["trip_id"]
        sequence_text = row["stop_sequence"]

        # Require nonnegative whole numbers written with ASCII digits.
        if (
            not sequence_text
            or not sequence_text.isascii()
            or not sequence_text.isdecimal()
        ):
            raise ValueError(
                f"Invalid stop_sequence in record {total_rows}: "
                f"{sequence_text!r}"
            )

        # Compare sequences numerically: "01" and "1" mean the same value.
        sequence = int(sequence_text)
        key = (trip_id, sequence)

        if key in seen_keys:
            raise ValueError(
                f"Duplicate stop-time key: {key!r}"
            )

        seen_keys.add(key)

    if total_rows == 0:
        raise ValueError("No stop-time records")

    return total_rows

def main():
    """Inspect the GTFS archive, validate stops, and collect route IDs."""

    # SECTION 2: Locate the original download
    project_root = Path(__file__).resolve().parent.parent
    zip_path = project_root / "data" / "raw" / "gtfs_tampere.zip"

    print("Project folder:", project_root)
    print("ZIP file:", zip_path)
    print("ZIP exists:", zip_path.is_file())

    if not zip_path.is_file():
        raise FileNotFoundError(f"GTFS ZIP not found: {zip_path}")

    # SECTION 3: Open the ZIP and list its contents
    with ZipFile(zip_path, "r") as archive:
        for entry in archive.infolist():
            print(entry.filename, entry.file_size)

        # SECTION 4: Read and validate the stop records
        with archive.open("stops.txt") as raw_file:
            with TextIOWrapper(
                raw_file,
                encoding="utf-8-sig",
                newline="",
            ) as text_file:
                reader = csv.DictReader(text_file)

                if not reader.fieldnames or "stop_id" not in reader.fieldnames:
                    raise ValueError("stops.txt is missing the stop_id column")

                total_stops, stop_ids = validate_stop_ids(reader)

                print(
                    f"PASS: {total_stops} stop records "
                    "have nonblank, unique IDs"
                )

        # SECTION 5: Collect route IDs for the next relationship check
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

        # Check trips against the route IDs collected above.
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

        # Read trips again to validate and collect their identifiers.
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

        # Read the large table progressively without extracting it.
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

        # Reopen the file because the previous reader is exhausted.
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

# SECTION 6: Execute only when this file is run directly
if __name__ == "__main__":
    main()