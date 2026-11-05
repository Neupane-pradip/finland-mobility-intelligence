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

### Interpretation

The download URL is mutable: its contents may change.
The fingerprint identifies this downloaded snapshot.
The timetable's service-date coverage has not yet been inspected.

## Initial Python validation results

For the October 30, 2026 downloaded snapshot:

- 3,429 stop records: stop IDs are nonblank and unique.
- 105 route records: route IDs are nonblank and unique.
- 71,447 trip records: every route reference exists in routes.txt.

Synthetic unit tests cover valid inputs, blank IDs,
duplicate IDs, empty tables, and missing route references.

These checks do not establish full GTFS compliance.
Trip-ID uniqueness, stop-time relationships, service calendars,
coordinates, and time values are not yet validated by the script.