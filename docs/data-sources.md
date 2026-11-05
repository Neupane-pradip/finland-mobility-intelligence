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
The complete feed's active service-date coverage has not yet been calculated.

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
- Sequence gaps and zero values are allowed.
- Different trips may use the same sequence values.

### Service identifiers and trip references

- calendar.txt contains 175 distinct service IDs.
- calendar_dates.txt contains 55 distinct service IDs.
- The combined lookup contains 175 distinct service IDs.
- All 55 service IDs in calendar_dates.txt also occur in calendar.txt.
- All 71,447 trips reference a service in the combined lookup.

Service IDs are collected from both calendar files.
Repeated service IDs are allowed during collection because one service
can have multiple date exceptions.

This collection step does not check uniqueness of calendar.service_id
or of the (service_id, date) key in calendar_dates.txt.

A known service identifier does not by itself establish valid
operating dates or guarantee that the service has active dates.

## Automated tests

The test suite currently contains 38 passing tests.

Tests use synthetic records rather than the downloaded feed.
They cover:

- Valid identifiers and references.
- Blank identifiers and references.
- Duplicate stop, route, and trip identifiers.
- Empty tables.
- Missing route, trip, stop, and service references.
- Duplicate trip/sequence pairs.
- Numerically equivalent sequence values.
- Invalid sequence formats.
- Allowed sequence gaps and zero values.
- Repeated service IDs during calendar lookup collection.
- Combining service IDs from both calendar files.
- Trip references to services defined only through calendar exceptions.

Run the real-feed inspection from the project folder:

    python scripts/inspect_gtfs.py

Run the automated tests:

    python -m unittest discover -s tests -v

## Validation limitations

These checks do not establish full GTFS compliance.

The script does not yet validate:

- Calendar primary-key uniqueness.
- Calendar date formats and actual date validity.
- Calendar date-range ordering.
- Weekday flags.
- Calendar exception types.
- Conflicting or duplicate service-date exceptions.
- Complete active service-date coverage.
- Arrival and departure time formats.
- Chronological progression within trips.
- Required arrival/departure times at applicable stops.
- Geographic coordinates.
- Agency, shape, fare, or transfer relationships.
- Every required or conditionally required GTFS field.

GTFS Schedule describes planned service.
These results do not establish actual vehicle arrivals,
punctuality, passenger demand, or service reliability.