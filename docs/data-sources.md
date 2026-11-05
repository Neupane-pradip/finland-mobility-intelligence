# Data sources

## Tampere GTFS Schedule

- Publisher: Tampere City Public Transport
- Documentation: https://wiki.itsfactory.fi/index.php/Tampere_Public_Transport_GTFS_feed
- Download URL: https://data.itsfactory.fi/journeys/files/gtfs/latest/gtfs_tampere.zip
- License named in provider documentation: Tampere City Open Data License
- Download date: 2026-10-30 (Europe/Helsinki)
- Local file: data/raw/gtfs_tampere.zip
- Downloaded size: 18,339,552 bytes
- SHA-256: 356c1f1058e2305ac34f553146b19de5b351edc26f060ef8e299414885f8e3a6

## Snapshot interpretation

The download URL is mutable: its contents may change.
The SHA-256 fingerprint identifies this downloaded snapshot.

The download date does not establish the timetable's operating dates.
The complete feed's service-date coverage has not yet been calculated.

The original ZIP is retained locally and excluded from Git.

## Files observed in the archive

- agency.txt
- calendar.txt
- calendar_dates.txt
- fare_attributes.txt
- fare_rules.txt
- municipalities.txt
- routes.txt
- shapes.txt
- stop_times.txt
- stops.txt
- transfers.txt
- trips.txt

This inventory was read from the downloaded ZIP.
It is not a claim that every file has been validated.

## Python validation results

Results apply to the October 30, 2026 downloaded snapshot.

### Stop identifiers

- 3,429 stop records were checked.
- All stop IDs are nonblank and unique.
- IDs are preserved as text, including leading zeros.

### Route identifiers

- 105 route records were checked.
- All route IDs are nonblank and unique.

### Trip identifiers and route references

- 71,447 trip records were checked.
- All trip IDs are nonblank and unique.
- Every trip's route_id references an existing route.

### Stop-time references and keys

- 2,328,188 stop-time records were checked.
- Every trip_id references an existing trip.
- Every stop_id references an existing stop.
- All stop_sequence values pass the nonnegative-integer format check.
- Every (trip_id, stop_sequence) pair is unique.
- Sequence values are compared numerically.
- Sequence gaps are allowed.
- Different trips may use the same sequence values.

## Automated tests

The test suite currently contains 28 passing tests.

Tests use synthetic records rather than the downloaded feed.
They cover:

- Valid identifiers and references.
- Blank identifiers.
- Duplicate identifiers.
- Empty tables.
- Missing route, trip, and stop references.
- Duplicate trip/sequence pairs.
- Numerically equivalent sequence values.
- Invalid sequence formats.
- Allowed sequence gaps and zero values.

Run the real-feed inspection from the project folder:

    python scripts/inspect_gtfs.py

Run the automated tests:

    python -m unittest discover -s tests -v

## Validation limitations

These checks do not establish full GTFS compliance.

The script does not yet validate:

- Trip service_id references to the calendar files.
- Calendar date ranges, weekday flags, or exceptions.
- Complete service-date coverage.
- Arrival and departure time formats.
- Chronological progression within trips.
- Required arrival/departure times at applicable stops.
- Geographic coordinates.
- Agency, shape, fare, or transfer relationships.
- Every required or conditionally required GTFS field.

GTFS Schedule describes planned service.
These results do not establish actual vehicle arrivals,
punctuality, passenger demand, or service reliability.