# First relational model

## Feed versioning

Keep each downloaded feed as a separate snapshot.
Use the ZIP's SHA-256 fingerprint to identify its contents.
Record the source URL and download timestamp separately.

Every imported table includes feed_version_id.
Never join records across different feed versions accidentally.

## Tables and keys

| Table | One row represents | Primary key |
|---|---|---|
| feed_versions | One distinct feed snapshot | feed_version_id |
| stops | One stop/location within a snapshot | feed_version_id, stop_id |
| routes | One route within a snapshot | feed_version_id, route_id |
| services | One service identifier within a snapshot | feed_version_id, service_id |
| trips | One scheduled trip within a snapshot | feed_version_id, trip_id |
| stop_times | One ordered stop visit within a trip | feed_version_id, trip_id, stop_sequence |
| calendar | One service's weekly pattern and date range | feed_version_id, service_id |
| calendar_dates | One service-date exception | feed_version_id, service_id, date |

services is a table we create from service IDs appearing in
calendar.txt or calendar_dates.txt. It is not a source GTFS file.

## Relationships

All relationships include feed_version_id:

- trips.route_id references routes.route_id.
- trips.service_id references services.service_id.
- stop_times.trip_id references trips.trip_id.
- stop_times.stop_id references stops.stop_id.
- calendar.service_id references services.service_id.
- calendar_dates.service_id references services.service_id.

## Data types

- Preserve GTFS IDs as text, including leading zeros.
- Store stop_sequence as an integer.
- Store service dates as dates.
- Preserve original arrival/departure time text.
- Also store arrival/departure as integer service-day seconds.
- Preserve missing times as missing, not zero.
- Retain agency timezone metadata for later timestamp conversion.

## Verified after-midnight example

Trip: 134_20179_17848766
Stop: 3634
Stop sequence: 23
Arrival and departure: 24:00:15
Service-day seconds: 86415

The actual operating dates of this trip have not yet been checked.