import csv
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile


def validate_stop_ids(rows):
    """Check stop IDs and return the record count if validation passes."""

    # A set lets us check whether an ID has already appeared.
    seen_ids = set()

    total_stops = 0
    empty_ids = 0
    duplicate_ids = 0

    for row in rows:
        total_stops += 1

        # Keep IDs as text so leading zeros are preserved.
        stop_id = row["stop_id"]

        # strip() detects empty or whitespace-only IDs.
        # It does not change the original stop_id.
        if not stop_id.strip():
            empty_ids += 1
        elif stop_id in seen_ids:
            duplicate_ids += 1
        else:
            seen_ids.add(stop_id)

    # An empty table should not pass just because it has no duplicates.
    if total_stops == 0:
        raise ValueError("No stop records")

    # Reject missing or repeated IDs instead of silently accepting them.
    if empty_ids > 0 or duplicate_ids > 0:
        raise ValueError(
            f"Stop ID validation failed: {empty_ids} empty IDs, "
            f"{duplicate_ids} repeated occurrences"
        )

    return total_stops


def main():
    """Inspect the downloaded ZIP and validate its stop IDs."""

    # Find the project folder relative to this script.
    # This avoids depending on the terminal's working directory.
    project_root = Path(__file__).resolve().parent.parent
    zip_path = project_root / "data" / "raw" / "gtfs_tampere.zip"

    print("Project folder:", project_root)
    print("ZIP file:", zip_path)
    print("ZIP exists:", zip_path.is_file())

    # Stop with a clear message if the download is missing.
    if not zip_path.is_file():
        raise FileNotFoundError(f"GTFS ZIP not found: {zip_path}")

    # Open the original ZIP for reading without extracting it.
    # The with block closes it automatically.
    with ZipFile(zip_path, "r") as archive:
        for entry in archive.infolist():
            print(entry.filename, entry.file_size)

        # Read stops.txt directly from inside the archive.
        with archive.open("stops.txt") as raw_file:
            # Decode bytes into text.
            # utf-8-sig also handles an optional UTF-8 byte-order mark.
            with TextIOWrapper(
                raw_file,
                encoding="utf-8-sig",
                newline="",
            ) as text_file:
                # Use CSV column names as dictionary keys.
                reader = csv.DictReader(text_file)

                # Check the header before trying to access stop_id.
                if not reader.fieldnames or "stop_id" not in reader.fieldnames:
                    raise ValueError("stops.txt is missing the stop_id column")

                total_stops = validate_stop_ids(reader)

                print(
                    f"PASS: {total_stops} stop records "
                    "have nonblank, unique IDs"
                )


# Run the inspection only when this file is executed directly.
# Importing validate_stop_ids from a test does not run main().
if __name__ == "__main__":
    main()