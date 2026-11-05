import unittest

from scripts.inspect_gtfs import validate_stop_ids, validate_trip_routes


class TestStopIds(unittest.TestCase):
    """Test validation using synthetic records, not the real feed."""

    def test_unique_ids_pass(self):
        # Different IDs should be accepted.
        rows = [
            {"stop_id": "0001"},
            {"stop_id": "0002"},
        ]

        # The function should return the number of accepted records.
        self.assertEqual(validate_stop_ids(rows), 2)

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