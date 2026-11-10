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


def job_text(source, name):
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\\s*\\n(.*?)(?=^  [a-zA-Z][\\w-]*:\\s*$|\\Z)",
        source,
    )
    if match is None:
        return None
    return match.group(1)


def active_fail_closed(source, job_name):
    block = job_text(source, job_name)
    if not block or "continue-on-error:" in block:
        return False
    if not re.search(r"(?m)^    if: always\\(\\)\\s*$", block):
        return False
    match = re.search(r"(?m)^        run: \\|\\s*\\n((?:^          .*\\n?)+)", block)
    if match is None:
        return False
    commands = [
        line.strip() for line in match.group(1).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return (
        len(commands) == 3
        and commands[0] == "set -euo pipefail"
        and commands[1].startswith('echo "::error title=EROHA ')
        and commands[2] == "exit 41"
    )



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
        self.assertTrue(active_fail_closed(CORE, "guardian-authorization"))
        self.assertIn("independently managed Guardian", CORE)

    def test_disabled_guardian_exit_is_detected(self):
        tampered = CORE.replace(
            "          exit 41",
            "          # exit 41\\n          exit 0",
            1,
        )
        self.assertNotEqual(tampered, CORE)
        self.assertFalse(active_fail_closed(tampered, "guardian-authorization"))

    def test_guardian_continue_on_error_is_detected(self):
        tampered = CORE.replace(
            "  guardian-authorization:\\n",
            "  guardian-authorization:\\n    continue-on-error: true\\n",
            1,
        )
        self.assertNotEqual(tampered, CORE)
        self.assertFalse(active_fail_closed(tampered, "guardian-authorization"))

    def test_core_release_job_is_absent_until_independent_broker(self):
        self.assertNotRegex(CORE, r"(?m)^  release:\\s*$")
        self.assertNotIn("gh release create", CORE)
        self.assertNotIn("gh release edit", CORE)
        self.assertNotIn("gh release upload", CORE)
        self.assertNotIn("git push", CORE)
        self.assertEqual(CORE.count("GH_TOKEN:"), 1)
        self.assertIn("gh release view", CORE)
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
