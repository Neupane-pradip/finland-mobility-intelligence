import unittest

from scripts.inspect_gtfs import validate_stop_ids


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