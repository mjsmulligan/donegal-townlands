"""Tests for the Donegal Townlands identifier registry."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from identifiers import (  # noqa: E402
    FIELDS,
    generator_self_test,
    new_identifier,
    parse_registry,
    validate_append_only,
)


class IdentifierTests(unittest.TestCase):
    def test_generates_uuid_v4(self):
        value = new_identifier("person")
        self.assertEqual(len(value), 36)
        self.assertEqual(value[14], "4")
        self.assertIn(value[19].lower(), "89ab")

    def test_manual_place_namespace(self):
        value = new_identifier("place", manual_place=True)
        self.assertTrue(value.startswith("dt-place:"))
        self.assertEqual(value.split(":")[1][14], "4")

    def test_registry_header_and_empty_rows(self):
        rows, errors = parse_registry(",".join(FIELDS) + "\n")
        self.assertEqual(rows, [])
        self.assertEqual(errors, [])

    def test_repeated_id_requires_valid_lifecycle_transition(self):
        value = new_identifier("person")
        text = (
            ",".join(FIELDS) + "\n"
            f"{value},person,active,,2026-11-01,initial\n"
            f"{value},person,active,,2026-11-01,repeated active row\n"
        )
        _, errors = parse_registry(text)
        self.assertTrue(any("must change status" in error for error in errors))

    def test_append_only_lifecycle_transition_is_valid(self):
        value = new_identifier("person")
        successor = new_identifier("person")
        text = (
            ",".join(FIELDS) + "\n"
            f"{value},person,active,,2026-11-01,initial\n"
            f"{successor},person,active,,2026-11-01,initial\n"
            f"{value},person,merged,{successor},2026-11-02,"
            "see DECISIONS.md#merge\n"
        )
        _, errors = parse_registry(text)
        self.assertEqual(errors, [])

    def test_retired_requires_successor_and_decision(self):
        value = new_identifier("person")
        text = (
            ",".join(FIELDS) + "\n"
            f"{value},person,retired,,2026-11-01,retired after review\n"
        )
        _, errors = parse_registry(text)
        self.assertTrue(any("requires a successor" in error for error in errors))
        self.assertTrue(any("DECISIONS.md" in error for error in errors))

    def test_successor_must_resolve(self):
        value = new_identifier("person")
        successor = new_identifier("person")
        text = (
            ",".join(FIELDS) + "\n"
            f"{value},person,merged,{successor},2026-11-01,"
            "see DECISIONS.md#merge\n"
        )
        _, errors = parse_registry(text)
        self.assertTrue(any("not registered" in error for error in errors))

    def test_append_only_allows_appending(self):
        baseline = (",".join(FIELDS) + "\n").encode()
        current = baseline + b"new row\n"
        self.assertEqual(validate_append_only(current, baseline), [])

    def test_append_only_rejects_rewriting(self):
        baseline = b"id,type,status,successor,date,reason\nold,person,active,,2026-01-01,first\n"
        rewritten = b"id,type,status,successor,date,reason\nold,person,active,,2026-01-01,changed\n"
        self.assertTrue(validate_append_only(rewritten, baseline))

    def test_append_only_rejects_removal(self):
        baseline = b"id,type,status,successor,date,reason\nold,person,active,,2026-01-01,first\n"
        self.assertTrue(validate_append_only(baseline.splitlines()[0] + b"\n", baseline))

    def test_10000_uuid_self_test(self):
        self.assertEqual(generator_self_test(10000, ROOT), [])


if __name__ == "__main__":
    unittest.main()
