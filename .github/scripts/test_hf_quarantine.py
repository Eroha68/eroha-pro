"""Contract tests for the *proposed*, not deployed, HF quarantine workflow.

Static checks detect accidental removal of the block; they are not an
independent security authority and cannot stop a repository administrator.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import unittest

WORKFLOW = Path(__file__).resolve().parent.parent / "workflows" / "deploy.yml"


def validate_contract(source: str) -> list[str]:
    failures: list[str] = []
    required = [
        ("read-only token", "permissions:\n  contents: read"),
        ("main-only branch", "branches:\n      - main"),
        ("required failure code", "          exit 41"),
        ("refusal status", "::error title=EROHA HF deployment NO-GO::"),
    ]
    for name, fragment in required:
        if fragment not in source:
            failures.append("MISSING_" + name.replace(" ", "_").upper())
    forbidden = [
        ("REPOSITORY_WRITE_PERMISSION", r"(?m)^\s+contents:\s+write\s*$"),
        ("HF_TOKEN_REFERENCE", r"HF_TOKEN|secrets\.|vars\."),
        ("REMOTE_GIT_PUBLISH", r"\bgit\s+(?:push|clone|remote)\b"),
        ("NETWORK_COMMAND", r"\b(?:curl|wget|ssh|scp|rsync)\b"),
        ("ACTION_INJECTION", r"(?m)^\s+-\s+uses:\s*"),
        ("SKIP_AS_SUCCESS", r"(?m)^\s+if:\s*(?:false|\$\{\{\s*false\s*\}\})"),
        ("ERROR_SUPPRESSION", r"continue-on-error\s*:\s*true|\|\|\s*true"),
        ("MANUAL_TRIGGER", r"(?m)^\s+workflow_dispatch\s*:"),
        ("QUIET_EXIT", r"(?m)^\s+exit\s+0\s*$"),
    ]
    for name, pattern in forbidden:
        if re.search(pattern, source, re.IGNORECASE):
            failures.append(name)
    if source.count("\n  release-quarantine:") != 1:
        failures.append("INCORRECT_JOB_COUNT")
    if source.count("\n        run: |") != 1:
        failures.append("INCORRECT_RUN_STEP_COUNT")
    return failures


def script_from_workflow(source: str) -> str:
    marker = "\n        run: |\n"
    if source.count(marker) != 1:
        raise ValueError("INCORRECT_RUN_STEP_COUNT")
    remainder = source.split(marker, 1)[1]
    lines = [line for line in remainder.splitlines() if line]
    if any(not line.startswith("          ") for line in lines):
        raise ValueError("INVALID_INDENTATION")
    return "\n".join(line[10:] for line in lines)


class FailClosedHuggingFaceContract(unittest.TestCase):
    def setUp(self) -> None:
        self.source = WORKFLOW.read_text(encoding="utf-8")

    def test_current_candidate_obeys_contract(self) -> None:
        self.assertEqual([], validate_contract(self.source))

    def test_runtime_returns_explicit_failure_41(self) -> None:
        script = script_from_workflow(self.source)
        process = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", script],
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(41, process.returncode)
        self.assertIn("EROHA HF deployment NO-GO", process.stdout)

    def test_removing_exit_is_detected(self) -> None:
        self.assertIn("MISSING_REQUIRED_FAILURE_CODE",
                      validate_contract(self.source.replace("          exit 41", "")))

    def test_write_token_is_rejected(self) -> None:
        self.assertIn("REPOSITORY_WRITE_PERMISSION",
                      validate_contract(self.source.replace("contents: read", "contents: write")))

    def test_deployment_secret_is_rejected(self) -> None:
        self.assertIn("HF_TOKEN_REFERENCE",
                      validate_contract(self.source + "\n# secrets.HF_TOKEN\n"))

    def test_remote_push_is_rejected(self) -> None:
        self.assertIn("REMOTE_GIT_PUBLISH",
                      validate_contract(self.source + "\n          git push origin main\n"))

    def test_manual_trigger_is_rejected(self) -> None:
        self.assertIn("MANUAL_TRIGGER",
                      validate_contract(self.source + "\n  workflow_dispatch:\n"))

    def test_skip_as_success_is_rejected(self) -> None:
        self.assertIn("SKIP_AS_SUCCESS",
                      validate_contract(self.source + "\n    if: false\n"))

    def test_continuation_after_errors_is_rejected(self) -> None:
        self.assertIn("ERROR_SUPPRESSION",
                      validate_contract(self.source + "\n    continue-on-error: true\n"))

    def test_additional_action_is_rejected(self) -> None:
        self.assertIn("ACTION_INJECTION",
                      validate_contract(self.source + "\n      - uses: actions/checkout@v4\n"))

    def test_another_job_is_rejected(self) -> None:
        self.assertIn("INCORRECT_JOB_COUNT",
                      validate_contract(self.source.replace("  release-quarantine:", "  replaced-job:")))

    def test_runtime_with_optimization_is_not_bypassed(self) -> None:
        # Python -O must not turn a failed check into success.
        process = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", script_from_workflow(self.source)],
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertNotEqual(0, process.returncode)


if __name__ == "__main__":
    unittest.main()
