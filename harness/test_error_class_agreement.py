"""Tests for error_class_agreement.py that need neither evaluator.

The driver's verdicts are pure functions of what each implementation printed, so the cases that
matter most — an implementation that answers with a disposition, two that disagree, two that agree
with each other and not with the row — are tested here without building anything. The vendored rows
are held to their recorded digests, so a row's expectation cannot be edited in place.
"""
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

import error_class_agreement as driver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGED = os.path.join(ROOT, driver.STAGED)
RELEASED = os.path.join(ROOT, "reference", "conformance-evaluation")

GO_ERROR = json.dumps(
    {"status": "error", "evaluationError": {"class": "malformed-input", "phase": "preflight"}}
)
PY_ERROR = json.dumps({"error": {"class": "malformed-input", "phase": "preflight"}})
DISPOSITION = json.dumps({"disposition": {"kind": "not-applicable"}})


class ReportOfTests(unittest.TestCase):
    def test_go_writes_its_error_to_stdout(self):
        self.assertEqual(
            ("error", "malformed-input", "preflight"),
            driver.report_of(GO_ERROR, GO_ERROR, "evaluationError"),
        )

    def test_python_writes_its_error_to_stderr_and_nothing_to_stdout(self):
        self.assertEqual(
            ("error", "malformed-input", "preflight"), driver.report_of("", PY_ERROR, "error")
        )

    def test_the_error_member_is_the_implementations_own_name_for_it(self):
        # Reading the Go envelope under the Python member name finds no error.
        self.assertEqual(("unparsed", None, None), driver.report_of(GO_ERROR, GO_ERROR, "error"))

    def test_a_disposition_is_not_an_error(self):
        self.assertEqual(
            ("disposition", None, None), driver.report_of(DISPOSITION, "", "error")
        )

    def test_a_disposition_together_with_an_error_is_reported_as_both(self):
        both = json.dumps(
            {"disposition": {"kind": "unresolved"}, "evaluationError": {"class": "malformed-input"}}
        )
        self.assertEqual("both", driver.report_of(both, both, "evaluationError")[0])

    def test_output_that_is_not_an_error_envelope_is_unparsed(self):
        for text in ("", "not json", "[]", "null", json.dumps({"error": "a string"}),
                     json.dumps({"error": {"class": 7}})):
            with self.subTest(text=text):
                self.assertEqual(("unparsed", None, None), driver.report_of(text, text, "error"))


class VerdictTests(unittest.TestCase):
    ERROR = ("error", "malformed-input", "preflight")

    def test_a_row_passes_when_both_refuse_and_all_three_classes_agree(self):
        self.assertIsNone(driver.verdict("malformed-input", self.ERROR, self.ERROR))

    def test_phase_is_never_part_of_the_verdict(self):
        other_phase = ("error", "malformed-input", "evaluation")
        no_phase = ("error", "malformed-input", None)
        self.assertIsNone(driver.verdict("malformed-input", self.ERROR, other_phase))
        self.assertIsNone(driver.verdict("malformed-input", no_phase, self.ERROR))

    def test_a_disposition_from_either_implementation_fails_the_row(self):
        answered = ("disposition", None, None)
        self.assertIn("go emitted a disposition", driver.verdict("malformed-input", answered, self.ERROR))
        self.assertIn("py emitted a disposition", driver.verdict("malformed-input", self.ERROR, answered))

    def test_an_error_that_comes_with_a_disposition_fails_the_row(self):
        both = ("both", "malformed-input", "preflight")
        self.assertIn("together with an error", driver.verdict("malformed-input", both, self.ERROR))

    def test_unreadable_output_fails_the_row(self):
        self.assertIn("could not be read", driver.verdict("malformed-input", self.ERROR, ("unparsed", None, None)))

    def test_implementations_that_disagree_fail_the_row(self):
        other = ("error", "unsupported-required-extension", "preflight")
        self.assertEqual(
            "the implementations report different classes",
            driver.verdict("malformed-input", self.ERROR, other),
        )

    def test_implementations_that_agree_against_the_row_fail_it_and_say_which(self):
        # The case a staged row exists to surface: the row may be the thing that is wrong.
        self.assertEqual(
            "both implementations agree with each other and not with the row",
            driver.verdict("unsupported-required-extension", self.ERROR, self.ERROR),
        )


class DriverEndToEndTests(unittest.TestCase):
    def _run(self, go_output=GO_ERROR, py_output=PY_ERROR, expected="malformed-input",
             suite_version=False):
        with tempfile.TemporaryDirectory() as root:
            harness = os.path.join(root, "harness")
            staged = os.path.join(root, "reference", "conformance-evaluation-staged")
            pyrepo = os.path.join(root, "python")
            os.makedirs(harness)
            os.makedirs(staged)
            os.makedirs(os.path.join(pyrepo, "jps_evaluator"))
            driver_path = os.path.join(harness, "error_class_agreement.py")
            with open(driver.__file__, encoding="utf-8") as source, open(
                driver_path, "w", encoding="utf-8"
            ) as target:
                target.write(source.read())
            payload = {
                "status": "staged",
                "cases": [{
                    "id": "row-1",
                    "pack": "unused.json",
                    "facts": {},
                    "expectedErrorClass": expected,
                }],
            }
            if suite_version:
                payload["suiteVersion"] = "not-a-staged-file"
            with open(os.path.join(staged, "cases.json"), "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            go_output_path = os.path.join(root, "go-output.txt")
            with open(go_output_path, "w", encoding="utf-8") as handle:
                handle.write(go_output)
            gobin = os.path.join(root, "go-standin")
            with open(gobin, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\ncat " + repr(go_output_path) + "\n")
            os.chmod(gobin, os.stat(gobin).st_mode | stat.S_IXUSR)

            with open(os.path.join(pyrepo, "jps_evaluator", "__init__.py"), "w", encoding="utf-8"):
                pass
            with open(os.path.join(pyrepo, "jps_evaluator", "__main__.py"), "w", encoding="utf-8") as handle:
                handle.write("import sys\nsys.stderr.write(" + repr(py_output) + ")\n")

            return subprocess.run(
                [sys.executable, driver_path, gobin, pyrepo],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_driver_agreement_exits_zero(self):
        result = self._run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("AGREE row-1", result.stdout)
        self.assertIn("1/1 staged rows", result.stdout)

    def test_driver_disposition_difference_exits_one(self):
        result = self._run(go_output=DISPOSITION)
        self.assertEqual(1, result.returncode)
        self.assertIn("DIFF  row-1", result.stdout)
        self.assertIn("go emitted a disposition", result.stdout)
        self.assertIn("0/1 staged rows", result.stdout)

    def test_driver_row_class_difference_exits_one(self):
        result = self._run(expected="unsupported-required-extension")
        self.assertEqual(1, result.returncode)
        self.assertIn("DIFF  row-1", result.stdout)
        self.assertIn("agree with each other and not with the row", result.stdout)

    def test_driver_refuses_a_corpus(self):
        result = self._run(suite_version=True)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("refusing to treat a corpus as one", result.stderr)


class VendoredRowsTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(STAGED, "provenance.json")) as handle:
            self.provenance = json.load(handle)

    def test_every_vendored_file_has_its_recorded_digest_and_nothing_else_is_vendored(self):
        recorded = self.provenance["files"]
        present = set()
        for directory, _, names in os.walk(STAGED):
            for name in names:
                relative = os.path.relpath(os.path.join(directory, name), STAGED).replace(os.sep, "/")
                if relative not in ("provenance.json", "README.md"):
                    present.add(relative)
        self.assertEqual(set(recorded), present)
        for relative, digest in recorded.items():
            with self.subTest(file=relative), open(os.path.join(STAGED, relative), "rb") as handle:
                self.assertEqual(digest, hashlib.sha256(handle.read()).hexdigest())

    def test_the_rows_are_a_staged_file_and_not_a_corpus(self):
        with open(os.path.join(STAGED, "cases.json")) as handle:
            staged = json.load(handle)
        self.assertEqual("staged", staged["status"])
        self.assertNotIn("suiteVersion", staged)
        self.assertTrue(staged["cases"])
        for case in staged["cases"]:
            with self.subTest(case=case["id"]):
                self.assertIn("expectedErrorClass", case)
                self.assertNotIn("expectedDisposition", case)
                self.assertNotIn("expectedErrorPhase", case)
                self.assertTrue(os.path.isfile(os.path.join(STAGED, case["pack"])))

    def test_the_staged_copy_of_the_released_fixture_is_the_released_fixture(self):
        name = "data-request-intake-triage.json"
        with open(os.path.join(STAGED, "packs", name), "rb") as staged, \
                open(os.path.join(RELEASED, name), "rb") as released:
            self.assertEqual(released.read(), staged.read())


if __name__ == "__main__":
    unittest.main()
