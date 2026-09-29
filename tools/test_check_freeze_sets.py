"""Tests for check_freeze_sets.py that need no real study.

The guard finds `studies/` relative to its own file, so each test copies the
script into a temporary directory as tools/check_freeze_sets.py, writes the
studies it needs next to it, and runs it with sys.executable -- the same shape
harness/test_class_agreement.py uses for its driver. The temporary tree always
holds a study named in GRANDFATHERED whose manifest covers DEVIATIONS.md;
without one the guard fails on purpose and says the exemption list is stale.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

GRANDFATHER = "016-policy-currency-anchor"
STUDY = "000-test-study"


def digest_of(content):
    return hashlib.sha256(content).hexdigest()


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="freeze-guard-")
        tools = os.path.join(self.root, "tools")
        os.makedirs(tools)
        shutil.copy(
            os.path.join(HERE, "check_freeze_sets.py"),
            os.path.join(tools, "check_freeze_sets.py"),
        )
        self.studies = os.path.join(self.root, "studies")
        os.makedirs(self.studies)
        deviations = b"no deviations recorded\n"
        self._write_file(GRANDFATHER, "DEVIATIONS.md", deviations)
        self._write_manifest(GRANDFATHER, "%s  DEVIATIONS.md\n" % digest_of(deviations))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _study_dir(self, name):
        path = os.path.join(self.studies, name)
        os.makedirs(os.path.join(path, "harness"), exist_ok=True)
        return path

    def _write_file(self, study, relpath, content):
        path = os.path.join(self._study_dir(study), relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(content)

    def _write_manifest(self, study, text):
        path = os.path.join(self._study_dir(study), "harness", "STUDY-MANIFEST.sha256")
        with open(path, "w") as handle:
            handle.write(text)

    def _run_guard(self):
        return subprocess.run(
            [sys.executable, os.path.join(self.root, "tools", "check_freeze_sets.py")],
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_unreadable_lines_fail_even_when_the_file_was_edited(self):
        stale = digest_of(b"original bytes\n")
        forms = {
            "binary-marker": "%s *adapter/SPEC.md" % stale,
            "one-space": "%s adapter/SPEC.md" % stale,
            "tab": "%s\tadapter/SPEC.md" % stale,
        }
        for form, line in forms.items():
            with self.subTest(form=form):
                self._write_file(STUDY, "adapter/SPEC.md", b"edited bytes\n")
                self._write_manifest(STUDY, line + "\n")
                proc = self._run_guard()
                self.assertNotEqual(0, proc.returncode)
                self.assertIn(STUDY, proc.stderr)
                self.assertIn("line 1", proc.stderr)
                # The digest check cannot see a line it cannot parse, so the
                # failure must come from the new check, not from the edit.
                self.assertNotIn("no longer matches", proc.stderr)

    def test_blank_lines_and_comments_still_pass(self):
        content = b"adapter spec\n"
        self._write_file(STUDY, "adapter/SPEC.md", content)
        self._write_manifest(
            STUDY,
            "%s  adapter/SPEC.md\n" % digest_of(content)
            + "\n"
            + "# a comment the guard must keep skipping\n",
        )
        proc = self._run_guard()
        self.assertEqual(0, proc.returncode)
        self.assertIn("checked 2 study freeze set(s); 0 problem(s)", proc.stdout)

    def test_edited_file_under_readable_line_still_fails(self):
        # Control: the temporary tree reaches the digest check, so a failure
        # above cannot hide behind a tree the guard never really read.
        self._write_file(STUDY, "adapter/SPEC.md", b"edited bytes\n")
        self._write_manifest(STUDY, "%s  adapter/SPEC.md\n" % digest_of(b"original bytes\n"))
        proc = self._run_guard()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("no longer matches", proc.stderr)


if __name__ == "__main__":
    unittest.main()