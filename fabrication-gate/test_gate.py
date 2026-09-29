"""The fabrication-elimination demonstration (ADR-0002 item 3).

Wires the attestation store (item 1) and the derivation rule (item 2) through
the admission gate and shows, deterministically, that the one failure studies
005-007 saw reach a wrong DECISION -- a `not_found` acquisition turned into a
fabricated `matchCount: "0"` -- has no path to evaluation: the model cannot
author the fact, cannot tamper the attested bytes, and cannot forge a receipt.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "acquisition-proxy"))
sys.path.insert(0, os.path.join(HERE, "..", "derivation-rule"))

import attest
import derive
import gate

KEY = b"fabrication-gate-key-of-32-bytes"
AUTHORITY = "acquisition-proxy:test"
SUBJECT = "Northwind Analytics Ltd"
PARAMS = {"subject": SUBJECT, "asOf": "2026-07-30T12:00:00Z", "maxAgeSeconds": 86400}
RULE = json.load(open(os.path.join(HERE, "..", "derivation-rule", "rules", "screening.rule.json")))

FOUND_CLEAR = {"status": "found", "screenedLegalName": SUBJECT,
               "observedAt": "2026-07-30T06:00:00Z", "datedRecord": True, "matchCount": "0"}
NOT_FOUND = {"status": "not_found", "checkedSuccessfully": True, "screenedLegalName": SUBJECT}
ERROR = {"status": "error"}


class Gate(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store_dir = os.path.join(self.dir, "store")
        self.store = attest.Store(self.store_dir, KEY, AUTHORITY)
        self.session = "acq-session-0001"
        self._prev = None
        self._index = 0

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def acquire(self, artifact):
        """Simulate one attested acquisition: retain the source's bytes and
        stamp a chained receipt, exactly as the acquisition proxy would."""
        result_digest = self.store.retain(attest.canon(artifact))
        core = {
            "receiptVersion": "1", "sessionId": self.session, "callIndex": self._index,
            "prevHmac": self._prev, "tool": "screen",
            "argumentsDigest": self.store.keyed_digest("args", attest.canon({"legalName": SUBJECT})),
            "resultDigest": result_digest, "isError": False,
            "servedAt": "2026-07-30T11:00:00Z", "authority": AUTHORITY,
            "downstream": {"command": ["screening-source"], "serverInfo": {"name": "ofac", "version": "1"}},
        }
        stored = self.store.stamp(core)
        self._prev = stored["hmac"]
        index = self._index
        self._index += 1
        return index

    # --- the derived claim is a function of the attested bytes ---

    def test_found_clear_admits_the_matchcount_fact(self):
        idx = self.acquire(FOUND_CLEAR)
        claim = gate.admit(self.store_dir, KEY, self.session, idx, RULE, PARAMS, AUTHORITY)
        self.assertEqual(claim["facts"], {"screening": {"matchCount": "0"}})
        self.assertEqual(claim["evidenceAvailability"], {"screening-record": "present"})
        self.assertEqual(claim["acquisitionStatus"], "resolved")
        self.assertEqual(claim["lineage"]["authority"], AUTHORITY)

    def test_not_found_admits_no_fact_only_absent(self):
        # THE ELIMINATED FABRICATION: the source returned not_found. The derived
        # claim has NO matchCount fact -- evidence absent -- so a fabricated
        # matchCount: "0" simply is not, and cannot be, in the evaluator's input.
        idx = self.acquire(NOT_FOUND)
        claim = gate.admit(self.store_dir, KEY, self.session, idx, RULE, PARAMS, AUTHORITY)
        self.assertEqual(claim["facts"], {})
        self.assertNotIn("screening", claim["facts"])
        self.assertEqual(claim["evidenceAvailability"], {"screening-record": "absent"})
        self.assertEqual(claim["acquisitionStatus"], "absent")

    def test_error_admits_unknown(self):
        idx = self.acquire(ERROR)
        claim = gate.admit(self.store_dir, KEY, self.session, idx, RULE, PARAMS, AUTHORITY)
        self.assertEqual(claim["facts"], {})
        self.assertEqual(claim["evidenceAvailability"], {"screening-record": "unknown"})
        self.assertEqual(claim["acquisitionStatus"], "unknown")

    # --- fabrication has no path: author, tamper, or forge ---

    def test_no_authored_facts_channel_exists(self):
        # The gate's return IS the evaluator input; admit() takes no caller
        # facts argument at all. There is no parameter through which a model
        # could supply matchCount: "0". (A structural check on the interface.)
        import inspect
        names = set(inspect.signature(gate.admit).parameters)
        self.assertNotIn("facts", names)
        self.assertNotIn("evidence", names)

    def test_tampering_the_not_found_artifact_is_refused(self):
        # If a fabricator edits the retained not_found bytes to inject a
        # found/matchCount:"0" record, the artifact no longer re-digests to the
        # signed resultDigest: the store fails verification and the gate refuses.
        idx = self.acquire(NOT_FOUND)
        with open(os.path.join(self.store_dir, "receipts", self.session, "%d.json" % idx), "rb") as h:
            digest = json.loads(h.read())["resultDigest"]
        artifact_path = os.path.join(self.store_dir, "artifacts", digest.split(":", 1)[1])
        with open(artifact_path, "wb") as handle:
            handle.write(attest.canon(FOUND_CLEAR))  # forge a clear record over the not_found bytes
        with self.assertRaises(gate.GateError):
            gate.admit(self.store_dir, KEY, self.session, idx, RULE, PARAMS, AUTHORITY)

    def test_forged_receipt_without_the_key_is_refused(self):
        # A fabricator who writes a fresh receipt for a fabricated clear artifact
        # but does not hold the attestation key cannot produce a valid HMAC; the
        # store fails verification under the real key.
        forged = attest.Store(self.store_dir, b"the-wrong-key-also-32-bytes-long!", AUTHORITY)
        digest = forged.retain(attest.canon(FOUND_CLEAR))
        core = {
            "receiptVersion": "1", "sessionId": self.session, "callIndex": 0, "prevHmac": None,
            "tool": "screen", "argumentsDigest": forged.keyed_digest("args", attest.canon({})),
            "resultDigest": digest, "isError": False, "servedAt": "2026-07-30T11:00:00Z",
            "authority": AUTHORITY, "downstream": {"command": ["x"], "serverInfo": None},
        }
        forged.stamp(core)  # signed with the wrong key
        with self.assertRaises(gate.GateError):
            gate.admit(self.store_dir, KEY, self.session, 0, RULE, PARAMS, AUTHORITY)

    # --- the gate passes the caller's authority on, and asks for what is there ---

    def test_acquisition_under_another_authority_is_refused(self):
        # The receipt is stamped under AUTHORITY but admitted with a different
        # expected_authority. The gate must pass the argument to the verifier:
        # drop it and this found-clear record would admit its matchCount fact.
        idx = self.acquire(FOUND_CLEAR)
        with self.assertRaises(gate.GateError) as raised:
            gate.admit(self.store_dir, KEY, self.session, idx, RULE, PARAMS,
                       "acquisition-proxy:other")
        self.assertIn("authority-mismatch", str(raised.exception))

    def test_call_index_the_session_does_not_have_is_refused(self):
        # The store verifies; the named acquisition simply is not there. The
        # gate's own refusal names it, rather than escaping a bare OSError.
        idx = self.acquire(FOUND_CLEAR)
        with self.assertRaises(gate.GateError) as raised:
            gate.admit(self.store_dir, KEY, self.session, idx + 1, RULE, PARAMS, AUTHORITY)
        self.assertIn("no attested acquisition", str(raised.exception))

    def test_store_with_no_receipts_is_refused_by_the_gate(self):
        # An empty receipts directory verifies vacuously true: the verifier
        # cannot refuse what was never expected. The gate therefore confirms
        # the acquisition is present, and refuses the same way as above.
        ok, _findings = attest.verify(self.store_dir, KEY, AUTHORITY)
        self.assertTrue(ok)
        with self.assertRaises(gate.GateError) as raised:
            gate.admit(self.store_dir, KEY, self.session, 0, RULE, PARAMS, AUTHORITY)
        self.assertIn("no attested acquisition", str(raised.exception))

    def test_baseline_contrast_ungated_admits_the_fabrication(self):
        # The study-005 world for contrast: when the model authors the facts
        # document, a fabricated matchCount for a not_found acquisition is
        # exactly what the ungated pipeline would evaluate. The gate's derived
        # claim for the same acquisition contains no such fact -- that is the
        # difference this item demonstrates.
        agent_authored_facts = {"screening": {"matchCount": "0"}}  # fabricated on a not_found
        idx = self.acquire(NOT_FOUND)
        gated = gate.admit(self.store_dir, KEY, self.session, idx, RULE, PARAMS, AUTHORITY)
        self.assertEqual(gated["facts"], {})
        self.assertNotEqual(gated["facts"], agent_authored_facts)


# A synthetic screening MCP source: it returns the screening record as its
# tools/call result, so the proxy retains that record as the artifact and the
# gate derives over it. This one genuinely has no record for the subject
# (not_found) -- the case the fabrication would have papered over.
SCREENING_SOURCE = r"""
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    m = json.loads(line); mid = m.get("id"); method = m.get("method")
    if method == "initialize":
        out = {"jsonrpc":"2.0","id":mid,"result":{"protocolVersion":"2025-06-18","serverInfo":{"name":"ofac-screening","version":"1"},"capabilities":{}}}
    elif method == "tools/call":
        # The source has no dated record for this counterparty.
        out = {"jsonrpc":"2.0","id":mid,"result":{"status":"not_found","checkedSuccessfully":True,"screenedLegalName":"Northwind Analytics Ltd"}}
    elif mid is not None:
        out = {"jsonrpc":"2.0","id":mid,"result":{}}
    else:
        continue
    sys.stdout.write(json.dumps(out)+"\n"); sys.stdout.flush()
"""


class EndToEndThroughTheProxy(unittest.TestCase):
    """The full chain: the real acquisition proxy (item 1) wraps a screening
    source, attests its not_found result, and the gate admits only the derived
    claim -- absent, no fabricated matchCount -- across the whole pipeline."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store_dir = os.path.join(self.dir, "store")
        self.key_path = os.path.join(self.dir, "key")
        with open(self.key_path, "wb") as handle:
            handle.write(KEY)
        self.source = os.path.join(self.dir, "screening_source.py")
        with open(self.source, "w") as handle:
            handle.write(SCREENING_SOURCE)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_proxy_attests_not_found_and_gate_admits_absent(self):
        import subprocess
        proxy = os.path.join(HERE, "..", "acquisition-proxy", "attest.py")
        init = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "t", "version": "0"}}})
        inited = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        call = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                           "params": {"name": "screen", "arguments": {"legalName": SUBJECT}}})
        proc = subprocess.Popen(
            [sys.executable, proxy, "wrap", self.store_dir, self.key_path,
             "--authority", AUTHORITY, "--", sys.executable, self.source],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        out, err = proc.communicate(("\n".join([init, inited, call]) + "\n").encode(), timeout=30)
        self.assertEqual(proc.returncode, 0, err)

        # Find the attested acquisition the proxy wrote and gate it.
        sessions = os.listdir(os.path.join(self.store_dir, "receipts"))
        self.assertEqual(len(sessions), 1)
        claim = gate.admit(self.store_dir, KEY, sessions[0], 0, RULE, PARAMS, AUTHORITY)
        self.assertEqual(claim["facts"], {})                       # no fabricated matchCount
        self.assertEqual(claim["evidenceAvailability"], {"screening-record": "absent"})
        self.assertEqual(claim["acquisitionStatus"], "absent")


if __name__ == "__main__":
    unittest.main()