#!/usr/bin/env python3
"""Read-only, lab-only guard for a merged draft of two fail-closed workflows.

These tests are structural regression guards, NOT a protected rule, independent
Guardian attestation or proof that production credentials are inaccessible.
"""
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HF = (ROOT / "deploy.yml").read_text(encoding="utf-8")
CORE = (ROOT / "eroha_core_ci.yml").read_text(encoding="utf-8")
SYNC_PATH = ROOT.parent.parent / "sync.sh"
SYNC = SYNC_PATH.read_text(encoding="utf-8")
AUDIT = (ROOT / "integrated-release-hold-audit.yml").read_text(encoding="utf-8")


def job_text(source, name):
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\s*\n(.*?)(?=^  [a-zA-Z][\w-]*:\s*$|\Z)",
        source,
    )
    if match is None:
        return None
    return match.group(1)


def active_fail_closed(source, job_name, require_always=True):
    block = job_text(source, job_name)
    if not block or "continue-on-error:" in block:
        return False
    # A denied job cannot be skipped, or preceded by another executable step.
    conditions = re.findall(r"(?m)^\s+if:\s*(.+?)\s*$", block)
    expected_conditions = ["always()"] if require_always else []
    if conditions != expected_conditions:
        return False
    if len(re.findall(r"(?m)^      - ", block)) != 1:
        return False
    if re.search(r"(?m)^\s+uses:\s*\S", block):
        return False
    if len(re.findall(r"(?m)^        run:\s*\|", block)) != 1:
        return False

    lines = block.splitlines()
    scripts = []
    for index, line in enumerate(lines):
        if line != "        run: |":
            continue
        commands = []
        for subsequent in lines[index + 1:]:
            if not subsequent.startswith("          "):
                break
            command = subsequent.strip()
            if command and not command.startswith("#"):
                commands.append(command)
        scripts.append(commands)

    expected_echo = {
        "release-quarantine": 'echo "::error title=EROHA HF deployment NO-GO::Direct Hugging Face deploy is disabled until independent Guardian approval, protected environment, and credential rotation are independently verified."',
        "guardian-authorization": 'echo "::error title=EROHA Guardian NO-GO::No independently signed, non-replayable release authorization from a separately controlled Guardian is configured."',
    }.get(job_name)
    return (
        expected_echo is not None
        and len(scripts) == 1
        and len(scripts[0]) == 3
        and scripts[0][0] == "set -euo pipefail"
        and scripts[0][1] == expected_echo
        and scripts[0][2] == "exit 41"
    )


def active_sync_hold(source):
    commands = [
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return (
        len(commands) == 3
        and commands[0] == "set -euo pipefail"
        and commands[1] == "printf '%s\\n' 'EROHA NO-GO: automatic Git sync is suspended in this draft until a separately controlled owner approves branch writes and release authority.' >&2"
        and commands[2] == "exit 41"
    )


class IntegratedHoldTests(unittest.TestCase):
    def test_sync_has_active_fail_closed_without_write_commands(self):
        self.assertTrue(active_sync_hold(SYNC))
        self.assertNotRegex(SYNC, r"(?m)^\s*git\s+(push|commit|checkout|add|fetch|pull|stash)")
        self.assertNotIn("secrets.", SYNC)

    def test_sync_denies_main_and_other_branch_without_using_git(self):
        with tempfile.TemporaryDirectory(prefix="eroha-sync-hold-test-") as folder:
            root = pathlib.Path(folder)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            marker = root / "git-called"
            fake_git = bin_dir / "git"
            fake_git.write_text(
                "#!/bin/sh\nprintf 'called' >> \"$EROHA_GIT_MARKER\"\nexit 0\n",
                encoding="utf-8",
            )
            fake_git.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
            env["EROHA_GIT_MARKER"] = str(marker)
            for arguments in ((), ("main",), ("test-only",)):
                with self.subTest(arguments=arguments):
                    run = subprocess.run(
                        ["/bin/bash", str(SYNC_PATH), *arguments],
                        cwd=root, env=env, capture_output=True, text=True, timeout=5,
                        check=False,
                    )
                    self.assertEqual(run.returncode, 41)
                    self.assertIn("EROHA NO-GO", run.stderr)
                    self.assertFalse(marker.exists())

    def test_sync_bypass_mutations_rejected(self):
        self.assertIn("exit 41", SYNC)
        self.assertFalse(active_sync_hold(SYNC.replace("exit 41", "exit 0", 1)))
        self.assertFalse(active_sync_hold(SYNC.replace("exit 41", "git push origin main\nexit 41", 1)))

    def test_three_path_audit_triggers_and_production_inventory(self):
        self.assertEqual(AUDIT.count("- 'sync.sh'"), 2)
        self.assertIn("MAIN_SYNC_AUTOMATIC_MAIN", AUDIT)
        self.assertIn("MAIN_SYNC_DIRECT_GIT_PUSH", AUDIT)

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
        self.assertTrue(active_fail_closed(HF, "release-quarantine", require_always=False))
        self.assertIn("contents: read", HF)
        self.assertNotIn("contents: write", HF)

    def test_hf_shell_substitution_in_error_message_is_rejected(self):
        marker = 'echo "::error title=EROHA HF deployment NO-GO::'
        self.assertIn(marker, HF)
        tampered = HF.replace(marker, marker + '$(touch /tmp/eroha-injected) ', 1)
        self.assertFalse(active_fail_closed(tampered, "release-quarantine", require_always=False))

    def test_guardian_shell_substitution_in_error_message_is_rejected(self):
        marker = 'echo "::error title=EROHA Guardian NO-GO::'
        self.assertIn(marker, CORE)
        tampered = CORE.replace(marker, marker + '$(touch /tmp/eroha-injected) ', 1)
        self.assertFalse(active_fail_closed(tampered, "guardian-authorization"))

    def test_sync_embedded_shell_commands_are_rejected(self):
        marker = "automatic Git sync is suspended in this draft"
        self.assertIn(marker, SYNC)
        tampered = SYNC.replace(marker, marker + "'; git push origin main; printf '", 1)
        self.assertFalse(active_sync_hold(tampered))

    def test_disabled_hf_exit_is_detected(self):
        prefix, marker, suffix = HF.rpartition("          exit 41")
        self.assertEqual(marker, "          exit 41")
        tampered = prefix + "          # exit 41\n          exit 0" + suffix
        self.assertFalse(active_fail_closed(tampered, "release-quarantine", require_always=False))

    def test_hf_continue_on_error_is_detected(self):
        tampered = HF.replace(
            "  release-quarantine:\n",
            "  release-quarantine:\n    continue-on-error: true\n",
            1,
        )
        self.assertNotEqual(tampered, HF)
        self.assertFalse(active_fail_closed(tampered, "release-quarantine", require_always=False))

    def test_hf_conditional_skip_is_detected(self):
        tampered = HF.replace(
            "  release-quarantine:\n",
            "  release-quarantine:\n    if: false\n",
            1,
        )
        self.assertNotEqual(tampered, HF)
        self.assertFalse(active_fail_closed(tampered, "release-quarantine", require_always=False))

    def test_hf_extra_action_step_is_detected(self):
        tampered = HF.replace(
            "    steps:\n",
            "    steps:\n      - uses: actions/checkout@v4\n",
            1,
        )
        self.assertNotEqual(tampered, HF)
        self.assertFalse(active_fail_closed(tampered, "release-quarantine", require_always=False))

    def test_guardian_conditional_step_skip_is_detected(self):
        header = "      - name: Fail closed until independently managed Guardian is deployed\n"
        self.assertIn(header, CORE)
        tampered = CORE.replace(header, header + "        if: false\n", 1)
        self.assertFalse(active_fail_closed(tampered, "guardian-authorization"))

    def test_core_guardian_fails_closed(self):
        self.assertTrue(active_fail_closed(CORE, "guardian-authorization"))
        self.assertIn("independently managed Guardian", CORE)

    def test_disabled_guardian_exit_is_detected(self):
        prefix, marker, suffix = CORE.rpartition("          exit 41")
        self.assertEqual(marker, "          exit 41")
        tampered = prefix + "          # exit 41\n          exit 0" + suffix
        self.assertNotEqual(tampered, CORE)
        self.assertFalse(active_fail_closed(tampered, "guardian-authorization"))

    def test_guardian_continue_on_error_is_detected(self):
        tampered = CORE.replace(
            "  guardian-authorization:\n",
            "  guardian-authorization:\n    continue-on-error: true\n",
            1,
        )
        self.assertNotEqual(tampered, CORE)
        self.assertFalse(active_fail_closed(tampered, "guardian-authorization"))

    def test_core_release_job_is_absent_until_independent_broker(self):
        self.assertNotRegex(CORE, r"(?m)^  release:\s*$")
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
