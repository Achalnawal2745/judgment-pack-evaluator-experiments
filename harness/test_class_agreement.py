"""Tests for class_agreement.py that need neither evaluator.

The driver finds the corpus relative to its own file. Each test copies the
driver into a temporary tree with that layout, writes the manifest the case
needs, and stands in for both implementations.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest


DRIVER_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "class_agreement.py")


class ClassAgreementDriverTests(unittest.TestCase):
    def setUp(self):
        self._temps = []

    def tearDown(self):
        for path in self._temps:
            shutil.rmtree(path, ignore_errors=True)

    def _tempdir(self):
        path = tempfile.mkdtemp()
        self._temps.append(path)
        return path

    def _tree(self, manifest):
        root = self._tempdir()
        harness = os.path.join(root, "harness")
        corpus = os.path.join(root, "reference", "conformance-evaluation")
        os.makedirs(harness)
        os.makedirs(corpus)
        shutil.copy(DRIVER_SRC, os.path.join(harness, "class_agreement.py"))
        with open(os.path.join(corpus, "manifest.json"), "w") as handle:
            json.dump(manifest, handle)
        with open(os.path.join(corpus, "dummy-pack.json"), "w") as handle:
            json.dump({}, handle)
        return root, os.path.join(harness, "class_agreement.py")

    def _go_bin(self, stdout="", stderr="", code=0):
        directory = self._tempdir()
        path = os.path.join(directory, "go-standin")
        with open(os.path.join(directory, "go-standin.stdout"), "w") as handle:
            handle.write(stdout)
        with open(os.path.join(directory, "go-standin.stderr"), "w") as handle:
            handle.write(stderr)
        with open(path, "w") as handle:
            handle.write(
                textwrap.dedent(
                    f"""\
                    #!/bin/sh
                    dir=$(dirname "$0")
                    cat "$dir/go-standin.stdout"
                    cat "$dir/go-standin.stderr" >&2
                    exit {int(code)}
                    """
                )
            )
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def _py_repo(self, stdout="", stderr="", code=0):
        repo = self._tempdir()
        pkg = os.path.join(repo, "jps_evaluator")
        os.makedirs(pkg)
        open(os.path.join(pkg, "__init__.py"), "w").close()
        with open(os.path.join(pkg, "__main__.py"), "w") as handle:
            handle.write(
                textwrap.dedent(
                    f"""\
                    import sys
                    sys.stdout.write({stdout!r})
                    sys.stderr.write({stderr!r})
                    raise SystemExit({int(code)})
                    """
                )
            )
        return repo

    def _run(self, driver, gobin, pyrepo):
        return subprocess.run(
            [sys.executable, driver, gobin, pyrepo],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _one_row(self):
        return {
            "cases": [
                {
                    "id": "row-1",
                    "pack": "packs/dummy-pack.json",
                    "facts": {"x": 1},
                }
            ]
        }

    def test_empty_manifest_is_refused(self):
        root, driver = self._tree({"cases": []})
        proc = self._run(driver, self._go_bin(), self._py_repo())
        self.assertEqual(1, proc.returncode)
        self.assertEqual("", proc.stdout)
        self.assertIn("zero rows", proc.stderr)

    def test_identical_non_zero_exits_do_not_agree(self):
        root, driver = self._tree(self._one_row())
        output = "refused\n"
        proc = self._run(
            driver,
            self._go_bin(stderr=output, code=2),
            self._py_repo(stderr=output, code=2),
        )
        self.assertEqual(1, proc.returncode)
        self.assertIn("DIFF", proc.stdout)
        self.assertIn("0/1 rows byte-agree between implementations", proc.stdout)

    def test_different_dispositions_do_not_agree(self):
        root, driver = self._tree(self._one_row())
        go_out = json.dumps({"disposition": {"kind": "not-applicable"}})
        py_out = json.dumps({"disposition": {"kind": "unresolved"}})
        proc = self._run(
            driver,
            self._go_bin(stdout=go_out),
            self._py_repo(stdout=py_out),
        )
        self.assertEqual(1, proc.returncode)
        self.assertIn("DIFF", proc.stdout)
        self.assertIn("0/1 rows byte-agree between implementations", proc.stdout)

    def test_matching_dispositions_agree(self):
        root, driver = self._tree(self._one_row())
        out = json.dumps({"disposition": {"kind": "not-applicable"}})
        proc = self._run(
            driver,
            self._go_bin(stdout=out),
            self._py_repo(stdout=out),
        )
        self.assertEqual(0, proc.returncode)
        self.assertIn("AGREE", proc.stdout)
        self.assertIn("1/1 rows byte-agree between implementations", proc.stdout)


if __name__ == "__main__":
    unittest.main()
