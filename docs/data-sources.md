# Data sources

## Tampere GTFS Schedule

- Publisher: Tampere City Public Transport
- Documentation: https://wiki.itsfactory.fi/index.php/Tampere_Public_Transport_GTFS_feed
- Download URL: https://data.itsfactory.fi/journeys/files/gtfs/latest/gtfs_tampere.zip
- Specification: https://gtfs.org/documentation/schedule/reference/
- License named in provider documentation: Tampere City Open Data License
- Download date: 2026-10-30 (Europe/Helsinki)
- Local file: data/raw/gtfs_tampere.zip
- Downloaded size: 18,339,552 bytes
- SHA-256: 356c1f1058e2305ac34f553146b19de5b351edc26f060ef8e299414885f8e3a6

## Snapshot interpretation

The download URL is mutable.
The SHA-256 fingerprint identifies this downloaded snapshot.

The download date does not establish the timetable's operating dates.
The original ZIP is retained locally and excluded from Git.

The report's inspection timestamp is not the download timestamp
or the publisher's update timestamp.

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
It does not establish that every file has been validated.

## Previously verified findings

The earlier inspection runs established:

- 3,429 stop records have nonblank, unique stop IDs.
- 105 route records have nonblank, unique route IDs.
- 71,447 trip records have nonblank, unique trip IDs.
- Every trip references an existing route.
- 2,328,188 stop-time records reference existing trips and stops.
- Stop-time sequences pass the nonnegative-integer format check.
- Every (trip_id, stop_sequence) pair is unique.
- calendar.txt contains 175 distinct service IDs.
- calendar_dates.txt contains 55 distinct service IDs.
- The combined lookup contains 175 distinct service IDs.
- All exception-file service IDs also occur in calendar.txt.
- Every trip references a service in the combined calendar lookup.

These observations apply only to the identified snapshot.

## Completed implementation scope

The revised inspection script implements the following checks.

### Archive and CSV handling

- Required files for the supported schedule profile are present.
- At least one calendar file is present.
- Duplicate ZIP member names are rejected.
- Required CSV headers are present and header names are unique.
- Records with missing or extra CSV fields are rejected.
- A local uncompressed-size guard limits archive processing.
- The ZIP is read directly without extraction or modification.

### Identifiers and references

- Stop, route, and trip identifiers are nonblank and unique.
- Identifiers remain text, preserving leading zeros.
- Trips reference existing routes and services.
- Stop times reference existing trips and stops.

### Weekly calendars and exceptions

- calendar.service_id is nonblank and unique.
- Dates use YYYYMMDD and represent actual calendar dates.
- Calendar start dates do not exceed end dates.
- Weekday flags contain only 0 or 1.
- Exception types contain only 1 or 2.
- Each exception (service_id, date) pair is unique.
- Services defined only through explicit dates are supported.
- Weekly patterns are expanded before exceptions are applied.
- Additions insert dates and removals discard dates.
- Referenced services with no active dates are reported as warnings.

### Stop times

- Sequences are nonnegative integers.
- Numeric sequence values determine key equality.
- Each (trip_id, stop_sequence) pair is unique.
- Gaps and zero sequence values are allowed.
- Times are parsed as service-day seconds.
- Times after midnight retain hours of 24 or greater.
- Missing time values remain missing rather than becoming zero.
- Exact timepoints require arrival and departure values.
- Departure cannot precede arrival at the same visit.
- Known times cannot move backwards along numeric stop sequence.
- Each trip must have at least two visits.
- Every trip must have stop-time records.

### Explicit project policies and implementation limits

This tool supports conventional fixed-stop schedules.
Populated on-demand location and time-window fields are rejected
as unsupported rather than interpreted.

Both arrival and departure values are required at a trip's
first and last visits as an explicit project policy.

GTFS time parsing accepts one- or two-digit hours.
Sequence values must fit SQLite's signed 64-bit INTEGER storage.

These implementation limits are not presented as universal
GTFS specification requirements.

## Verified revised inspection (2026-11-08)

The revised script passed on the local Tampere ZIP and wrote
reports/inspection.json. Its SHA-256 matches the snapshot recorded above.

- All 2,328,188 stop-time rows passed the implemented checks.
- 68,163 stop-time rows contain an arrival or departure at or after 24:00:00.
- The maximum service-day time is 102,300 seconds (28:25:00).
- No rows have missing arrival or departure values.
- Referenced services cover 233 distinct service dates, from
  2026-10-17 to 2027-06-06.
- No referenced services have an empty active-date set.

These are findings about this snapshot, not a full GTFS compliance result.

## Reproducible commands

Run from the project folder:

    python -m unittest discover -s tests -v
    python scripts/inspect_gtfs.py

Optional input and report paths:

    python scripts/inspect_gtfs.py --zip data/raw/gtfs_tampere.zip --output reports/inspection.json

No third-party Python packages are required.

A failed run exits with a nonzero code.
The command removes an older output report before inspecting,
so it cannot leave a stale success report at that output path.

## Inspection report

A successful report includes:

- Input path, byte size, and SHA-256.
- Inspection timestamp in UTC.
- Archive inventory and table counts.
- Agency timezone values as supplied.
- After-midnight stop-time count and one observed example.
- Maximum observed time expressed as service-day seconds.
- Count of rows with missing arrival or departure values.
- First, last, and distinct active service dates for referenced services.
- Referenced services with no active dates.
- Scope and limitations.

The earliest and latest service dates do not imply that service
operates on every intervening date.

Service-date coverage does not include the following calendar
day merely because a stop time exceeds 24:00:00.

## Automated tests

The revised suite passed all 39 tests on 2026-11-08. It covers parsing,
identifiers, calendars, stop times, CSV reading, synthetic ZIP integration,
archive limits, and CLI failure handling.

Synthetic fixtures are not observations about Tampere.

## Limitations

This is a scoped learning validator, not full GTFS compliance validation.

It does not comprehensively validate:

- Geographic coordinates or stop location types.
- Agency identifiers or timezone names.
- Route types and most other enumerated fields.
- Shape, fare, transfer, or other optional-file relationships.
- Every required or conditionally required GTFS field.
- Flexible or on-demand service semantics.
- Redundant calendar additions or removals.
- Realtime compatibility or stable identifiers across feed versions.

Agency timezone values are recorded, but the script does not convert
service dates and times into UTC event timestamps.

GTFS times use a service-day time origin with daylight-saving
considerations. UTC conversion requires separate careful handling.

GTFS Schedule describes planned service.
These findings do not establish actual arrivals, punctuality,
passenger demand, or service reliability.
