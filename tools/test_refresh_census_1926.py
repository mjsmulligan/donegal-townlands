"""Tests for tools/refresh_census_1926.py.

Everything here is offline. A fake NAI server stands in for the live API, whose
behaviour could not be verified from the build sandbox (its proxy blocks the NAI host).
The fake follows the assumptions in the tool: county and ded__icontains filters,
limit and offset paging, one CSV with a header per page, an empty body past the end.
The data is SYNTHETIC and uses invented names.
"""
import csv
import hashlib
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import refresh_census_1926 as rc  # noqa: E402
import source_manifest  # noqa: E402

HEADER = b"aform_name,county,townland,ded,first_name,surname,a_id\r\n"
NOW = rc.dt.datetime(2026, 11, 10, 1, 2, 3, tzinfo=rc.dt.timezone.utc)


def line(a_id, ded, surname="Smith", county="Donegal", first="Ann", townland="Testland"):
    return f"F{a_id},{county},{townland},{ded},{first},{surname},{a_id}\r\n".encode()


def make_csv(ded, ids, **kw):
    return HEADER + b"".join(line(i, ded, **kw) for i in ids)


class FakeNAI:
    def __init__(self, data, cap=None, statuses=None, header=HEADER):
        self.data = data  # ded name -> list of row lines
        self.cap = cap
        self.statuses = statuses or {}  # ded name -> list of statuses to return first
        self.header = header
        self.calls = []

    def get(self, params):
        ded = params["ded__icontains"]
        self.calls.append(dict(params))
        queue = self.statuses.get(ded)
        if queue:
            status = queue.pop(0)
            if status == "network":
                raise rc.TransientError("boom")
            if status != 200:
                return rc.Response(status, {"Content-Type": "text/plain"}, b"error text")
        rows = self.data[ded]
        limit = min(params["limit"], self.cap or params["limit"])
        chunk = rows[params["offset"]: params["offset"] + limit]
        if not chunk:
            return rc.Response(200, {"Content-Type": "text/csv"}, b"")
        return rc.Response(200, {"Content-Type": "text/csv"}, self.header + b"".join(chunk))


def no_sleep(_):
    pass


class Repo:
    """A throwaway copy of the repository layout for two DEDs."""

    def __init__(self, tmp):
        self.root = pathlib.Path(tmp)
        self.paths = rc.Paths(
            source_dir=self.root / "data/source/census", working_dir=self.root / "data/census",
            manifest=self.root / "data/source/manifest.csv",
            refresh_dir=self.root / "data/source/census_refresh",
            places=self.root / "data/processed/places/places.csv")
        for p in (self.paths.source_dir, self.paths.working_dir, self.paths.places.parent):
            p.mkdir(parents=True)
        with self.paths.places.open("w", encoding="utf-8", newline="") as s:
            w = csv.writer(s)
            w.writerow(["logainm_id", "name_en", "name_ga", "place_type", "ded_id", "civil_parish_id",
                        "barony_id", "county_id", "latitude", "longitude", "snapshot_date"])
            w.writerow(["1001", "Alpha", "", "ded", "", "", "", "100013", "", "", "2026-11-09"])
            w.writerow(["1002", "Beta", "", "ded", "", "", "", "100013", "", "", "2026-11-09"])
            w.writerow(["5", "Somewhere", "", "townland", "1001", "", "", "100013", "", "", "2026-11-09"])
        self.old = {"Alpha": make_csv("Alpha", [1, 2, 3, 4]), "Beta": make_csv("Beta", [10, 11, 12])}
        for ded, content in self.old.items():
            (self.paths.source_dir / f"{ded}_1926.csv").write_bytes(content)
            (self.paths.working_dir / f"{ded}_1926.csv").write_bytes(content)
        (self.paths.source_dir / "Alpha_1901.csv").write_bytes(b"census_year\r\n1901\r\n")
        (self.paths.source_dir / "Alpha_1911.csv").write_bytes(b"census_year\r\n1911\r\n")
        # A researcher working copy that must never be touched.
        self.working = make_csv("Alpha", [1, 2, 3, 4], surname="Edited")
        (self.paths.working_dir / "1926_Alpha.csv").write_bytes(self.working)
        rows = [source_manifest.source_metadata(p) for p in sorted(self.paths.source_dir.glob("*.csv"))]
        with self.paths.manifest.open("w", encoding="utf-8", newline="") as s:
            w = csv.DictWriter(s, fieldnames=source_manifest.FIELDS)
            w.writeheader()
            w.writerows(rows)

    def snapshot(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.root.rglob("*")) if p.is_file()}

    def verify(self):
        with mock.patch.object(source_manifest, "SOURCE_DIR", self.paths.source_dir), \
                mock.patch.object(source_manifest, "MANIFEST", self.paths.manifest), \
                mock.patch.object(source_manifest, "EXPECTED_FILES", 4), \
                mock.patch.object(source_manifest, "ROOT", self.root):
            return source_manifest.verify_manifest() == 0


def new_server(**kw):
    data = {
        "Alpha": [line(i, "Alpha") for i in (1, 2, 3)] + [line(4, "Alpha", surname="Corrected"), line(5, "Alpha")],
        "Beta": [line(i, "Beta") for i in (10, 11, 12)],
    }
    return FakeNAI(data, **kw)


class DownloadTests(unittest.TestCase):
    def test_pages_are_joined_without_changing_a_byte(self):
        rows = [line(i, "Alpha") for i in range(1, 8)]
        dl = rc.download_ded("Alpha", "Donegal", FakeNAI({"Alpha": rows}).get, page_size=3, delay=0, sleep=no_sleep)
        self.assertEqual(dl.content, HEADER + b"".join(rows))
        self.assertEqual((dl.pages, dl.page_rows), (3, [3, 3, 1]))

    def test_server_page_cap_below_the_limit_still_reads_everything(self):
        rows = [line(i, "Alpha") for i in range(1, 8)]
        dl = rc.download_ded("Alpha", "Donegal", FakeNAI({"Alpha": rows}, cap=2).get, page_size=5, delay=0, sleep=no_sleep)
        self.assertEqual(dl.content, HEADER + b"".join(rows))

    def test_bytes_are_kept_as_supplied_including_lf_endings_and_quotes(self):
        h = b"aform_name,county,townland,ded,first_name,surname,a_id\n"
        rows = [b'F1,Donegal,"Test, land",Alpha,"Ann ""Nan""",Smith,1\n', b"F2,Donegal,T,Alpha,Bo,Lee,2\n"]
        fake = FakeNAI({"Alpha": rows}, header=h)
        dl = rc.download_ded("Alpha", "Donegal", fake.get, page_size=1, delay=0, sleep=no_sleep)
        self.assertEqual(dl.content, h + b"".join(rows))

    def test_request_carries_the_filters_and_paging(self):
        fake = FakeNAI({"Alpha": [line(1, "Alpha")]})
        rc.download_ded("Alpha", "Donegal", fake.get, page_size=1000, delay=0, sleep=no_sleep)
        self.assertEqual(fake.calls[0], {"county": "Donegal", "ded__icontains": "Alpha", "limit": 1000, "offset": 0})
        self.assertEqual(fake.calls[1]["offset"], 1)

    def test_transient_errors_are_retried_with_backoff(self):
        fake = FakeNAI({"Alpha": [line(1, "Alpha")]}, statuses={"Alpha": [503, "network"]})
        waits = []
        dl = rc.download_ded("Alpha", "Donegal", fake.get, delay=0, retries=4, sleep=waits.append)
        self.assertEqual(dl.page_rows, [1])
        self.assertEqual(waits[:2], [1, 2])

    def test_retries_run_out(self):
        fake = FakeNAI({"Alpha": [line(1, "Alpha")]}, statuses={"Alpha": [503] * 5})
        with self.assertRaisesRegex(rc.RefreshError, "after 3 attempts"):
            rc.download_ded("Alpha", "Donegal", fake.get, delay=0, retries=3, sleep=no_sleep)

    def test_client_errors_fail_at_once(self):
        fake = FakeNAI({"Alpha": [line(1, "Alpha")]}, statuses={"Alpha": [400]})
        with self.assertRaisesRegex(rc.RefreshError, "HTTP 400"):
            rc.download_ded("Alpha", "Donegal", fake.get, delay=0, sleep=no_sleep)
        self.assertEqual(len(fake.calls), 1)

    def test_a_json_error_body_with_status_200_is_refused(self):
        def get(params):
            return rc.Response(200, {"Content-Type": "application/json"}, b'{"detail": "bad filter"}')
        with self.assertRaisesRegex(rc.RefreshError, "non-CSV"):
            rc.download_ded("Alpha", "Donegal", get, delay=0, sleep=no_sleep)

    def test_a_server_that_ignores_offset_is_detected(self):
        page = HEADER + line(1, "Alpha")
        with self.assertRaisesRegex(rc.RefreshError, "ignored the offset"):
            rc.download_ded("Alpha", "Donegal", lambda p: rc.Response(200, {"Content-Type": "text/csv"}, page),
                            delay=0, sleep=no_sleep)

    def test_endless_pagination_is_stopped(self):
        n = [0]

        def get(params):
            n[0] += 1
            return rc.Response(200, {"Content-Type": "text/csv"}, HEADER + line(n[0], "Alpha"))
        with self.assertRaisesRegex(rc.RefreshError, "did not finish"):
            rc.download_ded("Alpha", "Donegal", get, delay=0, sleep=no_sleep, max_pages=5)

    def test_rate_limit_delay_between_pages(self):
        waits = []
        rc.download_ded("Alpha", "Donegal", FakeNAI({"Alpha": [line(i, "Alpha") for i in (1, 2)]}).get,
                        page_size=1, delay=1.5, sleep=waits.append)
        self.assertEqual(waits, [1.5, 1.5])


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.ds = rc.Dataset("Alpha", "1001", "Donegal", "Alpha_1926.csv", pathlib.Path("x"))
        self.old = make_csv("Alpha", [1, 2, 3, 4])

    def dl(self, content, rows=None):
        n = rows if rows is not None else len(rc.parse_csv(content)) - 1
        return rc.Download(content=content, pages=1, page_rows=[n])

    def test_good_download(self):
        facts = rc.validate_download(self.dl(make_csv("Alpha", [1, 2, 3, 4, 5])), self.ds, self.old)
        self.assertEqual(facts["records"], 5)

    def test_icontains_extras_are_allowed_but_reported(self):
        content = make_csv("Alpha", [1, 2]) + make_csv("Alphabet", [3, 4])[len(HEADER):]
        facts = rc.validate_download(self.dl(content), self.ds, self.old)
        self.assertEqual(facts["deds"], {"Alpha": 2, "Alphabet": 2})

    def expect(self, content, message, rows=None, **kw):
        with self.assertRaisesRegex(rc.RefreshError, message):
            rc.validate_download(self.dl(content, rows), self.ds, self.old, **kw)

    def test_empty(self):
        with self.assertRaisesRegex(rc.RefreshError, "no records"):
            rc.validate_download(rc.Download(b"", 0, []), self.ds, self.old)

    def test_changed_header_is_a_schema_change(self):
        self.expect(b"aform_name,county,townland,ded,first_name,SURNAME,a_id\r\n" + line(1, "Alpha").split(b"\r\n")[0] + b"\r\n",
                    "schema change")

    def test_wrong_county(self):
        self.expect(make_csv("Alpha", [1, 2, 3, 4], county="Mayo"), "Unexpected county")

    def test_expected_ded_missing(self):
        self.expect(make_csv("Alphabet", [1, 2, 3, 4]), "not represented")

    def test_ded_that_does_not_match_the_query(self):
        self.expect(make_csv("Alpha", [1, 2, 3, 4]) + line(9, "Other")[0:], "do not match the query")

    def test_duplicate_a_id(self):
        self.expect(make_csv("Alpha", [1, 2, 3, 3]), "Duplicate a_id")

    def test_blank_a_id(self):
        self.expect(HEADER + b"F1,Donegal,T,Alpha,Ann,Smith,\r\n" + make_csv("Alpha", [2, 3, 4])[len(HEADER):], "Blank a_id")

    def test_ragged_row(self):
        self.expect(make_csv("Alpha", [1, 2, 3]) + b"F9,Donegal,Alpha\r\n", "do not have")

    def test_page_row_count_must_match(self):
        self.expect(make_csv("Alpha", [1, 2, 3, 4]), "Pages reported", rows=3)

    def test_large_shrink_is_treated_as_incomplete(self):
        self.old = make_csv("Alpha", list(range(1, 41)))
        self.expect(make_csv("Alpha", list(range(1, 30))), "10% fewer")
        rc.validate_download(self.dl(make_csv("Alpha", list(range(1, 30)))), self.ds, self.old, allow_shrink=True)

    def test_not_utf8(self):
        self.expect(HEADER + b"F1,Donegal,\xff,Alpha,Ann,Smith,1\r\n", "UTF-8")


class CompareTests(unittest.TestCase):
    def test_counts_and_field_changes(self):
        old = make_csv("Alpha", [1, 2, 3, 4])
        new = HEADER + line(1, "Alpha") + line(2, "Alpha", surname="Fixed") + line(3, "Alpha") + line(9, "Alpha")
        c = rc.compare(old, new, "Alpha")
        self.assertEqual((c["added"], c["removed"], c["changed"], c["unchanged"]), (1, 1, 1, 2))
        self.assertEqual(c["field_counts"], {"surname": 1})
        self.assertIn(["Alpha", "2", "changed", "surname", "Smith", "Fixed", "Ann", "Fixed", "Testland", "substantive"],
                      c["changes"])
        self.assertEqual(c["changed_serialisation"], 0)

    def test_nan_and_float_forms_are_labelled_serialisation_only(self):
        self.assertTrue(rc.serialisation_only("nan", ""))
        self.assertTrue(rc.serialisation_only("70.0", "70"))
        self.assertTrue(rc.serialisation_only("", ""))
        self.assertFalse(rc.serialisation_only("70.0", "71"))
        self.assertFalse(rc.serialisation_only("Smith", "Smyth"))
        self.assertFalse(rc.serialisation_only("nan", "0"))
        header = b"aform_name,county,townland,ded,first_name,surname,a_id,updated_age\r\n"
        old = header + b"F1,Donegal,T,Alpha,Ann,Smith,1,70.0\r\nF2,Donegal,T,Alpha,Bo,Lee,2,nan\r\n"
        new = header + b"F1,Donegal,T,Alpha,Ann,Smith,1,70\r\nF2,Donegal,T,Alpha,Bo,Lee,2,41\r\n"
        c = rc.compare(old, new, "Alpha")
        self.assertEqual((c["changed"], c["changed_serialisation"], c["field_counts"]), (2, 1, {"updated_age": 1}))

    def test_comparison_does_not_touch_its_inputs(self):
        old = make_csv("Alpha", [1, 2])
        new = make_csv("Alpha", [1, 3])
        before = (bytes(old), bytes(new))
        rc.compare(old, new, "Alpha")
        self.assertEqual((old, new), before)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Repo(self.tmp.name + "/repo")
        self.staging = pathlib.Path(self.tmp.name) / "staging"

    def go(self, server, apply=True, **kw):
        return rc.run(self.repo.paths, get=server.get, ded_ids=kw.pop("ded_ids", None), apply=apply,
                      staging=self.staging, delay=0, sleep=no_sleep, verify=kw.pop("verify", self.repo.verify),
                      now=lambda: NOW, **kw)

    def test_discovery_resolves_ids_and_finds_copies(self):
        ds = {d.ded_name: d for d in rc.discover_datasets(self.repo.paths)}
        self.assertEqual(set(ds), {"Alpha", "Beta"})
        self.assertEqual((ds["Alpha"].ded_id, ds["Alpha"].county), ("1001", "Donegal"))
        self.assertEqual(len(ds["Alpha"].mirrors), 1)
        self.assertEqual(ds["Alpha"].working_copy.name, "1926_Alpha.csv")
        self.assertIsNone(ds["Beta"].working_copy)

    def test_a_working_copy_that_is_not_a_plain_copy_stops_the_run(self):
        (self.repo.paths.working_dir / "Beta_1926.csv").write_bytes(make_csv("Beta", [10, 11, 12], surname="Hand"))
        with self.assertRaisesRegex(rc.RefreshError, "not identical"):
            rc.discover_datasets(self.repo.paths)

    def test_a_ded_missing_from_the_register_stops_the_run(self):
        (self.repo.paths.source_dir / "Gamma_1926.csv").write_bytes(make_csv("Gamma", [1]))
        with self.assertRaisesRegex(rc.RefreshError, "exactly one DED"):
            rc.discover_datasets(self.repo.paths)

    def test_dry_run_changes_nothing_in_the_repository(self):
        before = self.repo.snapshot()
        self.assertEqual(self.go(new_server(), apply=False), 0)
        self.assertEqual(self.repo.snapshot(), before)
        self.assertTrue((self.staging / "report" / "comparison_report.md").exists())

    def test_apply_replaces_everything_with_the_exact_downloaded_bytes(self):
        before = self.repo.snapshot()
        server = new_server()
        self.assertEqual(self.go(server), 0)
        expected = {d: HEADER + b"".join(rows) for d, rows in server.data.items()}
        for ded in ("Alpha", "Beta"):
            self.assertEqual((self.repo.paths.source_dir / f"{ded}_1926.csv").read_bytes(), expected[ded])
            self.assertEqual((self.repo.paths.working_dir / f"{ded}_1926.csv").read_bytes(), expected[ded])
        after = self.repo.snapshot()
        changed = {k for k in after if before.get(k) != after[k]}
        untouched = {"data/source/census/Alpha_1901.csv", "data/source/census/Alpha_1911.csv",
                     "data/census/1926_Alpha.csv"}
        self.assertFalse(changed & untouched)
        self.assertEqual(self.repo.working, (self.repo.paths.working_dir / "1926_Alpha.csv").read_bytes())
        self.assertTrue(self.repo.verify())

    def test_manifest_rows_and_outputs(self):
        self.assertEqual(self.go(new_server()), 0)
        with self.repo.paths.manifest.open(encoding="utf-8", newline="") as s:
            rows = {r["file"]: r for r in csv.DictReader(s)}
        a = rows["Alpha_1926.csv"]
        self.assertTrue(a["retrieval_method"].startswith("Direct download from the NAI"))
        self.assertEqual(a["date_acquired"], "2026-11-10")
        self.assertEqual(a["sha256"], hashlib.sha256((self.repo.paths.source_dir / "Alpha_1926.csv").read_bytes()).hexdigest())
        self.assertTrue(rows["Alpha_1901.csv"]["retrieval_method"].startswith("Adopted from the Gra"))
        out = self.repo.paths.refresh_dir / "20261110T010203Z"
        with (out / "refresh_manifest.csv").open(encoding="utf-8", newline="") as s:
            m = {r["ded_name"]: r for r in csv.DictReader(s)}
        self.assertEqual((m["Alpha"]["records_retrieved"], m["Alpha"]["rows_added"], m["Alpha"]["rows_changed"],
                          m["Alpha"]["rows_unchanged"], m["Alpha"]["replaced"]), ("5", "1", "1", "3", "yes"))
        self.assertEqual(m["Alpha"]["logainm_ded_id"], "1001")
        self.assertEqual(m["Alpha"]["new_sha256"], a["sha256"])
        self.assertNotEqual(m["Alpha"]["previous_sha256"], m["Alpha"]["new_sha256"])
        self.assertEqual(m["Beta"]["byte_identical_to_previous"], "yes")
        report = (out / "comparison_report.md").read_text(encoding="utf-8")
        self.assertIn("working copy 1926_Alpha.csv", report)
        self.assertNotIn(chr(0x2014), report)
        self.assertTrue((out / "changes.csv").exists())

    def test_one_failing_ded_means_nothing_is_replaced(self):
        before = self.repo.snapshot()
        server = new_server(statuses={"Beta": [400]})
        self.assertEqual(self.go(server), 1)
        self.assertEqual(self.repo.snapshot(), before)
        manifest = (self.staging / "report" / "refresh_manifest.csv").read_text(encoding="utf-8")
        self.assertIn("failed:", manifest)
        self.assertIn("passed", manifest)

    def test_a_schema_change_blocks_the_whole_refresh(self):
        before = self.repo.snapshot()
        server = new_server(header=b"aform_name,county,townland,ded,first_name,surname,a_id,extra\r\n")
        self.assertEqual(self.go(server), 1)
        self.assertEqual(self.repo.snapshot(), before)

    def test_failed_manifest_verification_restores_every_file(self):
        before = self.repo.snapshot()
        self.assertEqual(self.go(new_server(), verify=lambda: False), 1)
        self.assertEqual(self.repo.snapshot(), before)
        self.assertFalse(self.repo.paths.refresh_dir.exists())

    def test_a_write_failure_part_way_restores_every_file(self):
        before = self.repo.snapshot()
        real = rc.shutil.copyfile
        calls = [0]

        def flaky(src, dst, *a, **k):
            calls[0] += 1
            if calls[0] == 4:
                raise OSError("disk full")
            return real(src, dst, *a, **k)
        with mock.patch.object(rc.shutil, "copyfile", flaky):
            self.assertEqual(self.go(new_server()), 1)
        self.assertEqual(self.repo.snapshot(), before)

    def test_single_ded_run_stages_only_that_ded(self):
        server = new_server()
        self.assertEqual(self.go(server, apply=False, ded_ids=["1002"]), 0)
        self.assertEqual({c["ded__icontains"] for c in server.calls}, {"Beta"})

    def test_unknown_ded_id(self):
        with self.assertRaisesRegex(rc.RefreshError, "no existing 1926 file"):
            self.go(new_server(), apply=False, ded_ids=["999"])


class CliTests(unittest.TestCase):
    def test_apply_needs_all(self):
        with self.assertRaises(SystemExit):
            rc.main(["--ded-id", "1001", "--apply"])

    def test_needs_all_or_a_ded(self):
        with self.assertRaises(SystemExit):
            rc.main([])


class ManifestVerificationTests(unittest.TestCase):
    def test_direct_nai_rows_pass_and_unknown_methods_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp + "/r")
            self.assertTrue(repo.verify())
            rows = list(csv.DictReader(repo.paths.manifest.open(encoding="utf-8", newline="")))
            rows[0]["retrieval_method"] = "something else"
            with repo.paths.manifest.open("w", encoding="utf-8", newline="") as s:
                w = csv.DictWriter(s, fieldnames=source_manifest.FIELDS)
                w.writeheader()
                w.writerows(rows)
            self.assertFalse(repo.verify())


if __name__ == "__main__":
    unittest.main()
