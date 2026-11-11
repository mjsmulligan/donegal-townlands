"""Tests for .github/workflows/census-gedcom.yml (WP20). They read the workflow as text, so no YAML
library is needed, run the shell of the input-check step under bash, and run the same command line the
workflow uses against invented census files. They cannot run GitHub itself: see
docs/CENSUS_GEDCOM_WORKFLOW.md for the manual run that does."""

import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from tests import test_census_links as tcl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "census-gedcom.yml"
TOOL = ROOT / "tools" / "census_gedcom_export.py"


def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def step_block(name_start: str) -> str:
    """The lines of one step, from its '- name:' or '- uses:' line to the next step."""
    lines = text().split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("- ") and name_start in l)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("      - ")), len(lines))
    return "\n".join(lines[start:end])


def code() -> str:
    """The workflow without its comment lines, so the header may name what it never does."""
    return "\n".join(l for l in text().split("\n") if not l.lstrip().startswith("#"))


def upload_steps() -> list:
    lines = text().split("\n")
    out = []
    for i, l in enumerate(lines):
        if l.strip() == "- uses: actions/upload-artifact@v4":
            end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("      - ")), len(lines))
            out.append("\n".join(lines[i:end]))
    return out


def run_script(block: str) -> str:
    """The shell text of a step's `run: |` block."""
    lines = block.split("\n")
    i = next(i for i, l in enumerate(lines) if l.strip() == "run: |")
    body = []
    for l in lines[i + 1:]:
        if l.strip() and not l.startswith(" " * 10):
            break
        body.append(l)
    return textwrap.dedent("\n".join(body))


class WorkflowConfigurationTests(unittest.TestCase):
    def test_the_workflow_file_exists_and_is_manual_only(self):
        self.assertTrue(WORKFLOW.is_file())
        t = text()
        self.assertIn("workflow_dispatch:", t)
        for trigger in ("push:", "pull_request", "schedule:", "workflow_run", "repository_dispatch"):
            self.assertNotRegex(t, r"(?m)^\s*%s" % re.escape(trigger.rstrip(":")), trigger)

    def test_it_follows_the_conventions_of_the_other_workflows(self):
        t = text()
        self.assertIn('python-version: "3.12"', t)
        self.assertIn("actions/checkout@v4", t)
        self.assertIn("actions/setup-python@v5", t)
        self.assertIn("actions/upload-artifact@v4", t)
        self.assertIn('python -m unittest discover -s tests -p "test_census_*.py"', t)    # tests run first
        self.assertNotIn("pip install", t)                                                  # standard library only

    def test_tentative_output_is_explicitly_opt_in(self):
        t = text()
        block = re.search(r"(?ms)^      tentative:\n(.*?)(?=^      \w+:\n)", t).group(1)
        self.assertIn("type: boolean", block)
        self.assertRegex(block, r"default: false")
        tentative_step = step_block("Make the TENTATIVE GEDCOM")
        self.assertIn("if: ${{ inputs.tentative }}", tentative_step)
        self.assertIn("--tentative", tentative_step)
        self.assertNotIn("--tentative", step_block("Make the NORMAL GEDCOM"))
        normal_up, tentative_up = upload_steps()
        self.assertNotIn("if:", normal_up)
        self.assertIn("if: ${{ inputs.tentative }}", tentative_up)

    def test_normal_and_tentative_files_go_to_separate_folders_and_separate_artifacts(self):
        t = text()
        self.assertIn("census-gedcom/normal", t)
        self.assertIn("census-gedcom/tentative", t)
        names = re.findall(r"(?m)^\s+name: (census-gedcom-[^\n]+)$", t)
        self.assertEqual(len(names), 2)
        self.assertTrue(names[0].startswith("census-gedcom-normal-"))
        self.assertTrue(names[1].startswith("census-gedcom-TENTATIVE-"))
        self.assertEqual(len(upload_steps()), 2)
        self.assertEqual(t.count("if-no-files-found: error"), 2)

    def test_it_only_reads_and_never_commits_publishes_or_changes_decisions(self):
        t = code()
        self.assertRegex(t, r"(?m)^permissions:\n  contents: read\n")
        self.assertNotIn("contents: write", t)
        self.assertNotIn("pull-requests: write", t)
        for forbidden in ("git commit", "git push", "git add", "git config", "git checkout -b", "gh pr ", "gh release",
                          "gh api", "census_links.py accept", "census_links.py propose", "census_review", "refresh_census",
                          "data/research", "gedcom_people", "docs/"):
            self.assertNotIn(forbidden, t, forbidden)
        self.assertIn("persist-credentials: false", t)
        self.assertIn("git status --porcelain --untracked-files=all", t)    # the guard step

    def test_user_input_is_passed_through_the_environment_not_pasted_into_shell(self):
        t = text()
        for var in ("SCOPE", "VALUE", "TENTATIVE", "MIN_CONFIDENCE", "WIFE_PARENT"):
            self.assertRegex(t, r"(?m)^      %s: \$\{\{ inputs\.\w+ \}\}$" % var)
        scripts = "\n".join(run_script(step_block(n)) for n in ("Check the inputs", "Make the NORMAL", "Make the TENTATIVE", "Summary"))
        self.assertNotIn("inputs.value", scripts)
        self.assertNotIn("inputs.scope", scripts)

    def test_every_option_the_workflow_passes_exists_in_the_tool(self):
        out = subprocess.run([sys.executable, str(TOOL), "--help"], capture_output=True, text=True, check=True).stdout
        for flag in ("--townland", "--family", "--ded", "--wife-parent", "--tentative", "--min-confidence", "--out"):
            self.assertIn(flag, out, flag)
        self.assertIn("evidence", out)
        self.assertIn("assume", out)


class InputCheckStepTests(unittest.TestCase):
    """The real shell of the 'Check the inputs' step, run under bash."""

    def check(self, scope, value):
        script = run_script(step_block("Check the inputs"))
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "github_output"
            out.write_text("")
            env = {**os.environ, "SCOPE": scope, "VALUE": value, "GITHUB_OUTPUT": str(out)}
            r = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
            return r.returncode, dict(l.split("=", 1) for l in out.read_text().splitlines() if "=" in l)

    def test_valid_names_give_the_right_flag_and_a_safe_artifact_slug(self):
        self.assertEqual(self.check("townland", "Keadew Lower"), (0, {"flag": "--townland", "slug": "keadew-lower"}))
        self.assertEqual(self.check("family", "Mc Cadden"), (0, {"flag": "--family", "slug": "mc-cadden"}))
        self.assertEqual(self.check("ded", "Clogher"), (0, {"flag": "--ded", "slug": "clogher"}))
        self.assertEqual(self.check("townland", "Cullionboy")[1]["slug"], "cullionboy")

    def test_shell_metacharacters_and_odd_scopes_are_refused(self):
        for value in ("Keadew; rm -rf /", "$(whoami)", "`id`", "a|b", "x\ny", "../etc", "", "-rf", "Keadew\"Lower"):
            self.assertNotEqual(self.check("townland", value)[0], 0, repr(value))
        self.assertNotEqual(self.check("master", "Clogher")[0], 0)
        self.assertNotEqual(self.check("townland", "A" * 80)[0], 0)


class CommandLineExecutionTests(unittest.TestCase):
    """The same command lines the workflow runs, against invented census files in a temporary folder."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.census = self.dir / "census"
        self.census.mkdir()
        tcl.write_census(self.census, tcl.PEOPLE)

    def tearDown(self):
        self._tmp.cleanup()

    def cli(self, *extra):
        cmd = [sys.executable, str(TOOL), "--townland", "Alpha", "--wife-parent", "evidence", "--census-dir", str(self.census),
               "--decisions", str(self.dir / "none.csv"), "--tree", str(self.dir / "none_tree.csv"), *extra]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_normal_generation_writes_only_the_normal_file(self):
        r = self.cli("--out", str(self.dir / "normal"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        names = sorted(p.name for p in (self.dir / "normal").iterdir())
        self.assertEqual(names, ["townland_alpha.ged", "townland_alpha_report.txt"])
        self.assertNotIn("TENTATIVE", (self.dir / "normal" / "townland_alpha.ged").read_text(encoding="utf-8"))

    def test_tentative_generation_writes_a_clearly_named_separate_file(self):
        r = self.cli("--tentative", "--min-confidence", "low", "--out", str(self.dir / "tentative"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        names = sorted(p.name for p in (self.dir / "tentative").iterdir())
        self.assertEqual(names, ["townland_alpha_tentative.ged", "townland_alpha_tentative_report.txt"])
        self.assertIn("TENTATIVE LINK, not accepted by the researcher", (self.dir / "tentative" / "townland_alpha_tentative.ged").read_text(encoding="utf-8"))

    def test_neither_run_creates_or_changes_accepted_decisions(self):
        self.cli("--out", str(self.dir / "normal"))
        self.cli("--tentative", "--out", str(self.dir / "tentative"))
        self.assertFalse((self.dir / "none.csv").exists())


if __name__ == "__main__":
    unittest.main()
