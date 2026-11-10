#!/usr/bin/env python3
"""Read-only, lab-only guard for a merged draft of two fail-closed workflows.

These tests are structural regression guards, NOT a protected rule, independent
Guardian attestation or proof that production credentials are inaccessible.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HF = (ROOT / "deploy.yml").read_text(encoding="utf-8")
CORE = (ROOT / "eroha_core_ci.yml").read_text(encoding="utf-8")


class IntegratedHoldTests(unittest.TestCase):
    def test_both_main_push_workflows_present(self):
        for source in (HF, CORE):
            self.assertRegex(source, r"(?m)^on:\s*$")
            self.assertRegex(source, r"(?m)^\s+push:\s*$")
            self.assertIn("main", source)

    def test_hf_has_no_token_reference(self):
        self.assertNotIn("secrets.HF_TOKEN", HF)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", HF)

    def test_hf_has_no_direct_remote_operations(self):
        for forbidden in ("git push", "git clone", "huggingface.co", "curl ", "rsync ", "actions/checkout"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, HF)

    def test_hf_is_explicit_quarantine(self):
        self.assertIn("release-quarantine:", HF)
        self.assertIn("exit 41", HF)
        self.assertIn("contents: read", HF)
        self.assertNotIn("contents: write", HF)

    def test_core_guardian_fails_closed(self):
        self.assertIn("guardian-authorization:", CORE)
        self.assertIn("independently managed Guardian", CORE)
        self.assertRegex(CORE, r"(?s)guardian-authorization:.*?exit 41")

    def test_core_release_job_is_absent_until_independent_broker(self):
        self.assertNotRegex(CORE, r"(?m)^  release:\\s*$")
        self.assertNotIn("gh release create", CORE)
        self.assertNotIn("gh release edit", CORE)
        self.assertNotIn("gh release upload", CORE)
        self.assertNotIn("git push", CORE)
        self.assertNotIn("GH_TOKEN:", CORE)
        self.assertIn("guardian-authorization:", CORE)

    def test_no_core_job_receives_write_token_before_broker(self):
        self.assertIn("permissions:\n  contents: read", CORE)
        self.assertNotIn("contents: write", CORE)
        self.assertIn("guardian-authorization:", CORE)

    def test_hf_workflow_has_no_unguarded_deploy_job(self):
        self.assertNotRegex(HF, r"(?m)^  deploy:")
        self.assertEqual(len(re.findall(r"(?m)^  [a-zA-Z][a-zA-Z0-9-]*:\s*$", HF.split("\njobs:\n", 1)[1])), 1)

    def test_no_publisher_credentials_in_quarantine(self):
        self.assertNotIn("secrets.", HF)
        self.assertNotIn("GH_TOKEN", HF)
        self.assertIn("no checkout, secrets, network or deployment", HF)


if __name__ == "__main__":
    unittest.main(verbosity=2)
