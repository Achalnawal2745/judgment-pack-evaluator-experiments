"""Tests for rfc0016_harness.py that need neither evaluator.

The driver's verdicts are pure functions of what each implementation printed, so the cases that
matter most are tested here without building anything: bytes that differ in a way a decoder would
not see, an implementation that answers with a disposition where an error is expected, two that
agree with each other and not with the RFC. The cases file is held to the script that writes it,
so a row's expected answer cannot be edited in place.
"""
import json
import os
import subprocess
import sys
import unittest

import rfc0016_harness as driver

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "rfc0016_cases.json")

OUTCOME = '{"handoff":{"state":"none"},"kind":"outcome","outcomeId":"approve","reasons":[],"value":{"v":"0.10"}}'
GO_RESULT = '{"outputVersion":"2","status":"evaluated","disposition":' + OUTCOME + ',"trace":[]}\n'
PY_RESULT = '{"conformanceClaim":"none","disposition":' + OUTCOME + ',"experimental":true}\n'
GO_ERROR = json.dumps(
    {"status": "error", "evaluationError": {"class": "pack-not-conformant", "phase": "preflight"}}
)
PY_ERROR = json.dumps({"error": {"class": "pack-not-conformant", "phase": "preflight"}})


class MemberBytesTests(unittest.TestCase):
    def test_the_member_is_returned_as_it_is_written(self):
        self.assertEqual(OUTCOME, driver.member_bytes(GO_RESULT, "disposition"))
        self.assertEqual(OUTCOME, driver.member_bytes(PY_RESULT, "disposition"))

    def test_whitespace_and_member_order_inside_the_member_are_kept(self):
        spaced = '{"disposition": {"kind": "outcome", "handoff": {"state": "none"}}}'
        self.assertEqual(
            '{"kind": "outcome", "handoff": {"state": "none"}}',
            driver.member_bytes(spaced, "disposition"),
        )

    def test_an_escape_is_not_turned_into_its_character(self):
        escaped = '{"disposition":{"value":{"v":"\\u00e9"}}}'
        self.assertEqual('{"value":{"v":"\\u00e9"}}', driver.member_bytes(escaped, "disposition"))

    def test_a_member_of_that_name_inside_another_member_is_not_the_member(self):
        nested = '{"trace":{"disposition":{"kind":"inner"}},"disposition":{"kind":"outer"}}'
        self.assertEqual('{"kind":"outer"}', driver.member_bytes(nested, "disposition"))
        self.assertIsNone(driver.member_bytes('{"trace":{"disposition":{}}}', "disposition"))

    def test_a_name_inside_a_string_is_not_a_member(self):
        self.assertIsNone(driver.member_bytes('{"note":"\\"disposition\\":{}"}', "disposition"))

    def test_text_that_is_not_one_object_has_no_member(self):
        for text in ("", "not json", "[]", "null", '"disposition"', '{"disposition"', '{"disposition":'):
            with self.subTest(text=text):
                self.assertIsNone(driver.member_bytes(text, "disposition"))


class AnswerOfTests(unittest.TestCase):
    def test_go_writes_a_result_and_an_error_to_stdout(self):
        self.assertEqual(("disposition", OUTCOME), driver.answer_of(GO_RESULT, GO_RESULT, "evaluationError"))
        self.assertEqual(("error", "pack-not-conformant"), driver.answer_of(GO_ERROR, GO_ERROR, "evaluationError"))

    def test_python_writes_a_result_to_stdout_and_an_error_to_stderr(self):
        self.assertEqual(("disposition", OUTCOME), driver.answer_of(PY_RESULT, "", "error"))
        self.assertEqual(("error", "pack-not-conformant"), driver.answer_of("", PY_ERROR, "error"))

    def test_an_error_together_with_a_disposition_is_reported_as_both(self):
        both = '{"disposition":' + OUTCOME + ',"evaluationError":{"class":"malformed-input"}}'
        self.assertEqual(("both", "malformed-input"), driver.answer_of(both, both, "evaluationError"))

    def test_output_that_is_neither_is_unparsed(self):
        for text in ("", "not json", "[]", json.dumps({"error": "a string"}), json.dumps({"error": {"class": 7}})):
            with self.subTest(text=text):
                self.assertEqual("unparsed", driver.answer_of(text, text, "error")[0])


class VerdictTests(unittest.TestCase):
    def test_both_agree_with_the_rfc(self):
        answer = ("disposition", OUTCOME)
        self.assertEqual("matches-rfc", driver.verdict_of(answer, answer, answer))

    def test_one_byte_of_difference_is_a_divergence(self):
        other = ("disposition", OUTCOME.replace('"0.10"', '"0.1"'))
        self.assertEqual("DIVERGENT", driver.verdict_of(("disposition", OUTCOME), other, ("disposition", OUTCOME)))

    def test_the_same_value_written_in_another_order_is_a_divergence(self):
        reordered = '{"kind":"outcome","handoff":{"state":"none"},"outcomeId":"approve","reasons":[],"value":{"v":"0.10"}}'
        self.assertEqual(json.loads(OUTCOME), json.loads(reordered))
        self.assertEqual(
            "DIVERGENT",
            driver.verdict_of(("disposition", OUTCOME), ("disposition", reordered), ("disposition", OUTCOME)),
        )

    def test_a_disposition_against_an_error_is_a_divergence(self):
        self.assertEqual(
            "DIVERGENT",
            driver.verdict_of(("error", "malformed-input"), ("disposition", OUTCOME), ("disposition", OUTCOME)),
        )

    def test_two_classes_that_differ_are_a_divergence(self):
        self.assertEqual(
            "DIVERGENT",
            driver.verdict_of(("error", "malformed-input"), ("error", "pack-not-conformant"), ("error", "malformed-input")),
        )

    def test_both_agree_with_each_other_and_not_with_the_rfc(self):
        answer = ("error", "pack-not-conformant")
        self.assertEqual("AGREE-OFF-RFC", driver.verdict_of(answer, answer, ("error", "unsupported-required-extension")))

    def test_two_that_agree_on_a_forbidden_or_unreadable_answer_do_not_agree(self):
        for kind in ("both", "unparsed"):
            with self.subTest(kind=kind):
                answer = (kind, "malformed-input")
                self.assertEqual("DIVERGENT", driver.verdict_of(answer, answer, answer))


class CasesFileTests(unittest.TestCase):
    def setUp(self):
        with open(CASES, encoding="utf-8") as handle:
            self.text = handle.read()
        self.document = json.loads(self.text)

    def test_the_file_is_what_the_script_writes(self):
        written = subprocess.run(
            [sys.executable, os.path.join(HERE, "make_rfc0016_cases.py")],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertEqual(written, self.text)

    def test_every_row_has_one_expected_answer_and_an_origin_in_the_rfc(self):
        self.assertEqual(60, len(self.document["cases"]))
        ids = [case["id"] for case in self.document["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        for case in self.document["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(1, len(case["expected"]))
                self.assertIn(list(case["expected"])[0], ("disposition", "errorClass"))
                self.assertTrue(case["origin"].startswith(("Conformance, ", "Examples, ")))
                self.assertIsInstance(case["optIn"], bool)

    def test_an_expected_disposition_is_written_in_its_canonical_form(self):
        for case in self.document["cases"]:
            expected = case["expected"].get("disposition")
            if expected is None:
                continue
            with self.subTest(case=case["id"]):
                decoded = json.loads(expected)
                self.assertEqual(
                    expected,
                    json.dumps(decoded, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                )
                if decoded["kind"] != "outcome":
                    self.assertNotIn("value", decoded)

    def test_the_rows_that_hold_an_escape_hold_it_as_text(self):
        rows = {case["id"]: case for case in self.document["cases"]}
        backslash = chr(92)
        self.assertIn(backslash + "ud83d" + backslash + "ude00", rows["document-constant-surrogate-pair"]["pack"])
        self.assertIn(backslash + "ud800", rows["document-string-constant-unpaired-surrogate"]["pack"])
        self.assertIn(backslash + "udc00", rows["adversarial-string-fact-unpaired-surrogate"]["facts"])
        self.assertIn("amount" + backslash + "n", rows["document-name-ends-in-line-feed"]["pack"])

    def test_every_known_row_is_a_row_and_gives_its_reason(self):
        ids = {case["id"] for case in self.document["cases"]}
        self.assertEqual(4, len(self.document["known"]))
        for name, known in self.document["known"].items():
            with self.subTest(row=name):
                self.assertIn(name, ids)
                self.assertIn(known["verdict"], ("AGREE-OFF-RFC", "DIVERGENT"))
                self.assertTrue(known["reason"])


if __name__ == "__main__":
    unittest.main()
