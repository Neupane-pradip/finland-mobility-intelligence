import unittest

from scripts.inspect_gtfs import (
    validate_route_ids,
    validate_stop_ids,
    validate_stop_time_references,
    validate_trip_ids,
    validate_trip_routes,
    validate_stop_time_keys,
    collect_service_ids,
    validate_trip_services
)


class TestStopIds(unittest.TestCase):
    """Test validation using synthetic records, not the real feed."""

    def test_unique_ids_pass(self):
        rows = [
            {"stop_id": "0001"},
            {"stop_id": "0002"},
        ]

        # Unpack the two values returned by the validator.
        count, stop_ids = validate_stop_ids(rows)

        self.assertEqual(count, 2)
        self.assertEqual(stop_ids, {"0001", "0002"})

    def test_duplicate_ids_fail(self):
        # The second occurrence repeats an existing ID.
        rows = [
            {"stop_id": "0001"},
            {"stop_id": "0001"},
        ]

        # Passing means the expected error was raised.
        with self.assertRaisesRegex(ValueError, "1 repeated occurrences"):
            validate_stop_ids(rows)

    def test_blank_id_fails(self):
        # Whitespace alone is not a usable identifier.
        rows = [{"stop_id": "   "}]

        with self.assertRaisesRegex(ValueError, "1 empty IDs"):
            validate_stop_ids(rows)

    def test_empty_table_fails(self):
        # No records should trigger an error.
        with self.assertRaisesRegex(ValueError, "No stop records"):
            validate_stop_ids([])

class TestTripRoutes(unittest.TestCase):
    """Use synthetic records to test trip-to-route references."""

    def test_existing_route_passes(self):
        # Multiple trips may legitimately share one route.
        rows = [
            {"trip_id": "trip_A", "route_id": "1"},
            {"trip_id": "trip_B", "route_id": "1"},
        ]

        self.assertEqual(validate_trip_routes(rows, {"1"}), 2)

    def test_missing_route_fails(self):
        # Route 99 is absent from the route lookup.
        rows = [{"trip_id": "trip_A", "route_id": "99"}]

        with self.assertRaisesRegex(ValueError, "1 invalid references"):
            validate_trip_routes(rows, {"1"})

    def test_blank_route_fails(self):
        # A whitespace-only route reference is invalid.
        rows = [{"trip_id": "trip_A", "route_id": "   "}]

        with self.assertRaisesRegex(ValueError, "1 invalid references"):
            validate_trip_routes(rows, {"1"})

    def test_empty_trips_fail(self):
        with self.assertRaisesRegex(ValueError, "No trip records"):
            validate_trip_routes([], {"1"})

class TestRouteIds(unittest.TestCase):
    """Test route IDs using synthetic records."""

    def test_unique_ids_pass(self):
        rows = [
            {"route_id": "01"},
            {"route_id": "10"},
        ]

        # Return the lookup while preserving IDs as text.
        self.assertEqual(validate_route_ids(rows), {"01", "10"})

    def test_duplicate_ids_fail(self):
        rows = [
            {"route_id": "1"},
            {"route_id": "1"},
        ]

        with self.assertRaisesRegex(ValueError, "Duplicate route_id"):
            validate_route_ids(rows)

    def test_blank_id_fails(self):
        # Check both an empty value and whitespace.
        for blank in ("", "   "):
            with self.subTest(route_id=blank):
                with self.assertRaisesRegex(ValueError, "Blank route_id"):
                    validate_route_ids([{"route_id": blank}])

    def test_empty_table_fails(self):
        with self.assertRaisesRegex(ValueError, "No route records"):
            validate_route_ids([])

class TestTripIds(unittest.TestCase):
    """Check trip identifiers using synthetic records."""

    def test_unique_ids_pass(self):
        rows = [
            {"trip_id": "001"},
            {"trip_id": "002"},
        ]

        # Return the validated lookup, preserving IDs as text.
        self.assertEqual(validate_trip_ids(rows), {"001", "002"})

    def test_duplicate_ids_fail(self):
        rows = [
            {"trip_id": "trip_A"},
            {"trip_id": "trip_A"},
        ]

        with self.assertRaisesRegex(ValueError, "Duplicate trip_id"):
            validate_trip_ids(rows)

    def test_blank_id_fails(self):
        for blank in ("", "   "):
            with self.subTest(trip_id=blank):
                with self.assertRaisesRegex(ValueError, "Blank trip_id"):
                    validate_trip_ids([{"trip_id": blank}])

    def test_empty_table_fails(self):
        with self.assertRaisesRegex(ValueError, "No trip records"):
            validate_trip_ids([])

class TestStopTimeReferences(unittest.TestCase):
    """Test references using synthetic stop-time records."""

    def test_existing_references_pass(self):
        rows = [
            {"trip_id": "trip_A", "stop_id": "0001"},
            {"trip_id": "trip_A", "stop_id": "0002"},
        ]

        count = validate_stop_time_references(
            rows,
            trip_ids={"trip_A"},
            stop_ids={"0001", "0002"},
        )

        self.assertEqual(count, 2)

    def test_missing_trip_fails(self):
        rows = [{"trip_id": "unknown", "stop_id": "0001"}]

        with self.assertRaisesRegex(ValueError, "1 invalid rows"):
            validate_stop_time_references(
                rows,
                trip_ids={"trip_A"},
                stop_ids={"0001"},
            )

    def test_missing_stop_fails(self):
        rows = [{"trip_id": "trip_A", "stop_id": "9999"}]

        with self.assertRaisesRegex(ValueError, "1 invalid rows"):
            validate_stop_time_references(
                rows,
                trip_ids={"trip_A"},
                stop_ids={"0001"},
            )

    def test_both_missing_count_as_one_invalid_row(self):
        rows = [{"trip_id": "unknown", "stop_id": "9999"}]

        # We count invalid records, not individual broken references.
        with self.assertRaisesRegex(ValueError, "1 invalid rows"):
            validate_stop_time_references(
                rows,
                trip_ids={"trip_A"},
                stop_ids={"0001"},
            )

    def test_empty_table_fails(self):
        with self.assertRaisesRegex(ValueError, "No stop-time records"):
            validate_stop_time_references(
                [],
                trip_ids={"trip_A"},
                stop_ids={"0001"},
            )

class TestStopTimeKeys(unittest.TestCase):
    """Test composite keys using synthetic records."""

    def test_different_trips_can_share_sequence(self):
        rows = [
            {"trip_id": "trip_A", "stop_sequence": "1"},
            {"trip_id": "trip_B", "stop_sequence": "1"},
        ]

        self.assertEqual(validate_stop_time_keys(rows), 2)

    def test_sequence_gaps_are_allowed(self):
        rows = [
            {"trip_id": "trip_A", "stop_sequence": "10"},
            {"trip_id": "trip_A", "stop_sequence": "30"},
        ]

        self.assertEqual(validate_stop_time_keys(rows), 2)

    def test_duplicate_pair_fails(self):
        rows = [
            {"trip_id": "trip_A", "stop_sequence": "1"},
            {"trip_id": "trip_A", "stop_sequence": "1"},
        ]

        with self.assertRaisesRegex(ValueError, "Duplicate stop-time key"):
            validate_stop_time_keys(rows)

    def test_equivalent_numeric_sequences_fail(self):
        rows = [
            {"trip_id": "trip_A", "stop_sequence": "01"},
            {"trip_id": "trip_A", "stop_sequence": "1"},
        ]

        # Both sequences represent the integer 1.
        with self.assertRaisesRegex(ValueError, "Duplicate stop-time key"):
            validate_stop_time_keys(rows)

    def test_invalid_sequences_fail(self):
        for value in ("", " ", "-1", "1.5", "abc"):
            with self.subTest(sequence=value):
                rows = [{"trip_id": "trip_A", "stop_sequence": value}]

                with self.assertRaisesRegex(ValueError, "Invalid stop_sequence"):
                    validate_stop_time_keys(rows)

    def test_zero_sequence_passes(self):
        # Zero is a valid nonnegative sequence value.
        rows = [{"trip_id": "trip_A", "stop_sequence": "0"}]

        self.assertEqual(validate_stop_time_keys(rows), 1)

    def test_empty_table_fails(self):
        with self.assertRaisesRegex(ValueError, "No stop-time records"):
            validate_stop_time_keys([])

class TestServiceIds(unittest.TestCase):
    """Test service collection using synthetic calendar records."""

    def test_distinct_ids_are_collected(self):
        rows = [
            {"service_id": "001"},
            {"service_id": "002"},
        ]

        self.assertEqual(collect_service_ids(rows), {"001", "002"})

    def test_repeated_service_ids_are_allowed(self):
        # One service may appear on multiple exception dates.
        rows = [
            {"service_id": "service_A"},
            {"service_id": "service_A"},
        ]

        self.assertEqual(collect_service_ids(rows), {"service_A"})

    def test_blank_id_fails(self):
        for blank in ("", "   "):
            with self.subTest(service_id=blank):
                with self.assertRaisesRegex(ValueError, "Blank service_id"):
                    collect_service_ids([{"service_id": blank}])

    def test_empty_input_returns_empty_set(self):
        # An individual calendar file may contribute no IDs.
        # main() separately rejects an empty combined lookup.
        self.assertEqual(collect_service_ids([]), set())

    def test_combining_calendars_preserves_additional_services(self):
        # Synthetic example: a service appears only in calendar_dates.
        weekly = collect_service_ids([{"service_id": "weekly"}])
        exceptions = collect_service_ids(
            [{"service_id": "weekly"}, {"service_id": "special"}]
        )

        weekly.update(exceptions)

        self.assertEqual(weekly, {"weekly", "special"})

class TestTripServices(unittest.TestCase):
    """Check service references using synthetic trip records."""

    def test_existing_service_passes(self):
        # Multiple trips may share one service.
        rows = [
            {"trip_id": "trip_A", "service_id": "weekday"},
            {"trip_id": "trip_B", "service_id": "weekday"},
        ]

        self.assertEqual(
            validate_trip_services(rows, {"weekday"}),
            2,
        )

    def test_missing_service_fails(self):
        rows = [
            {"trip_id": "trip_A", "service_id": "unknown"},
        ]

        with self.assertRaisesRegex(ValueError, "1 invalid references"):
            validate_trip_services(rows, {"weekday"})

    def test_blank_service_fails(self):
        for blank in ("", "   "):
            with self.subTest(service_id=blank):
                rows = [
                    {"trip_id": "trip_A", "service_id": blank},
                ]

                with self.assertRaisesRegex(
                    ValueError, "1 invalid references"
                ):
                    validate_trip_services(rows, {"weekday"})

    def test_empty_trips_fail(self):
        with self.assertRaisesRegex(ValueError, "No trip records"):
            validate_trip_services([], {"weekday"})

    def test_exception_only_service_passes(self):
        # Build a combined lookup with a service defined only
        # in synthetic calendar_dates records.
        services = collect_service_ids(
            [{"service_id": "weekday"}]
        )
        services.update(
            collect_service_ids([{"service_id": "special"}])
        )

        rows = [
            {"trip_id": "trip_special", "service_id": "special"},
        ]

        self.assertEqual(validate_trip_services(rows, services), 1)