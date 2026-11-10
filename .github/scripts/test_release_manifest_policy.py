"""Synthetic acceptance for commit-bound, digest-pinned release member manifests.

A fixture-derived checksum is NOT an independent production approval.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from build_release_archive import build, load_approved_manifest


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        stderr=subprocess.PIPE, text=True
    ).strip()


class ApprovedMemberManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="eroha-manifest-fixture-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "EROHA Synthetic Test")
        git(self.repo, "config", "user.email", "nobody@example.invalid")
        (self.repo / "app.py").write_text(
            "print('synthetic committed code')\n", encoding="utf-8"
        )
        git(self.repo, "add", "app.py")
        git(self.repo, "commit", "-qm", "Synthetic source")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        self.manifest_path = root / "approved-release-manifest.json"
        self.output = root / "dist" / "synthetic.zip"
        self.builder = Path(__file__).with_name("build_release_archive.py")

    def approve(self, files: list[str], commit: str | None = None) -> str:
        data = json.dumps({
            "schema": 1, "commit": commit or self.commit, "files": files
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.manifest_path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def loaded(self, pin: str):
        return load_approved_manifest(self.manifest_path, self.commit, pin)

    def test_exact_approved_members_build_pinned_git_bytes(self):
        pin = self.approve(["app.py"])
        allowed = self.loaded(pin)
        (self.repo / "app.py").write_text(
            "print('uncommitted tampering')\n", encoding="utf-8"
        )
        members, total = build(self.repo, self.commit, self.output, allowed)
        self.assertEqual(members, 1)
        self.assertEqual(total, len(b"print('synthetic committed code')\n"))
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.namelist(), ["app.py"])
            self.assertEqual(archive.read("app.py"),
                             b"print('synthetic committed code')\n")

    def test_new_unapproved_tracked_member_blocks_entire_archive(self):
        (self.repo / "config.json").write_bytes(
            b'{"password":"SYNTHETIC_NOT_REAL"}'
        )
        git(self.repo, "add", "config.json")
        git(self.repo, "commit", "-qm", "Unapproved committed file")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        pin = self.approve(["app.py"], self.commit)
        with self.assertRaisesRegex(ValueError, "MANIFEST_MEMBER_SET_MISMATCH"):
            build(self.repo, self.commit, self.output, self.loaded(pin))
        self.assertFalse(self.output.exists())

    def test_wrong_manifest_digest_rejected(self):
        pin = self.approve(["app.py"])
        self.manifest_path.write_bytes(self.manifest_path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "MANIFEST_HASH_MISMATCH"):
            self.loaded(pin)

    def test_manifest_bound_to_wrong_git_commit_rejected(self):
        pin = self.approve(["app.py"], "0" * 40)
        with self.assertRaisesRegex(ValueError, "MANIFEST_SCHEMA_OR_COMMIT_MISMATCH"):
            self.loaded(pin)

    def test_duplicate_keys_rejected(self):
        payload = (
            '{"schema":1,"schema":1,"commit":"' + self.commit +
            '","files":["app.py"]}'
        ).encode()
        self.manifest_path.write_bytes(payload)
        pin = hashlib.sha256(payload).hexdigest()
        with self.assertRaisesRegex(ValueError, "MANIFEST_DUPLICATE_KEY"):
            self.loaded(pin)

    def test_duplicate_or_unsorted_files_rejected(self):
        for files in (["app.py", "app.py"], ["z.txt", "app.py"]):
            pin = self.approve(files)
            with self.assertRaisesRegex(ValueError,
                                        "MANIFEST_DUPLICATE_OR_UNSORTED_FILES"):
                self.loaded(pin)

    def test_manifest_casefolded_file_directory_collision_rejected(self):
        pin = self.approve(["APP.PY/nested.txt", "app.py"])
        with self.assertRaisesRegex(ValueError, "MANIFEST_COLLIDING_PATHS"):
            self.loaded(pin)
        self.assertFalse(self.output.exists())

    def test_case_insensitive_member_collision_rejected(self):
        pin = self.approve(["APP.PY", "app.py"])
        with self.assertRaisesRegex(ValueError, "MANIFEST_COLLIDING_PATHS"):
            self.loaded(pin)

    def test_secret_like_manifest_paths_rejected(self):
        for name in (".env/credentials.json", ".ssh/id_rsa",
                     "config/.npmrc", "private.pem"):
            pin = self.approve([name])
            with self.assertRaises(ValueError):
                self.loaded(pin)

    def test_missing_and_symlinked_manifest_rejected(self):
        self.manifest_path.unlink(missing_ok=True)
        with self.assertRaisesRegex(ValueError, "MANIFEST_UNAVAILABLE"):
            self.loaded("0" * 64)
        pin = self.approve(["app.py"])
        legit = self.manifest_path.with_name("legit.json")
        self.manifest_path.rename(legit)
        self.manifest_path.symlink_to(legit)
        with self.assertRaisesRegex(ValueError, "MANIFEST_UNAVAILABLE"):
            self.loaded(pin)

    def test_manifest_parent_traversal_rejected_before_read(self):
        pin = self.approve(["app.py"])
        redirected = Path(self.temp.name) / "unused" / ".." / self.manifest_path.name
        with self.assertRaisesRegex(ValueError, "MANIFEST_UNAVAILABLE"):
            load_approved_manifest(redirected, self.commit, pin)
        self.assertFalse(self.output.exists())

    def test_manifest_symlinked_parent_directory_rejected(self):
        pin = self.approve(["app.py"])
        root = Path(self.temp.name)
        alias = root / "manifest-directory-link"
        alias.symlink_to(root, target_is_directory=True)
        redirected = alias / self.manifest_path.name
        with self.assertRaisesRegex(ValueError, "MANIFEST_UNAVAILABLE"):
            load_approved_manifest(redirected, self.commit, pin)
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO required")
    def test_named_pipe_manifest_fails_closed_without_blocking(self):
        self.manifest_path.unlink(missing_ok=True)
        os.mkfifo(self.manifest_path)
        process = subprocess.run(
            [sys.executable, str(self.builder), "--repo", str(self.repo),
             "--commit", self.commit, "--output", str(self.output),
             "--manifest", str(self.manifest_path),
             "--manifest-sha256", "0" * 64],
            capture_output=True, text=True, check=False, timeout=5,
        )
        self.assertEqual(process.returncode, 41)
        self.assertIn("MANIFEST_UNSAFE_FILE_TYPE", process.stderr)
        self.assertFalse(self.output.exists())

    def test_boolean_schema_is_not_integer(self):
        payload = json.dumps({
            "schema": True, "commit": self.commit, "files": ["app.py"]
        }).encode()
        self.manifest_path.write_bytes(payload)
        with self.assertRaisesRegex(ValueError, "MANIFEST_SCHEMA_OR_COMMIT_MISMATCH"):
            self.loaded(hashlib.sha256(payload).hexdigest())

    def test_cli_fails_closed_without_manifest(self):
        process = subprocess.run(
            [sys.executable, str(self.builder), "--repo", str(self.repo),
             "--commit", self.commit, "--output", str(self.output)],
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("--manifest", process.stderr)
        self.assertFalse(self.output.exists())

    def test_cli_refuses_output_overwriting_approved_manifest(self):
        pin = self.approve(["app.py"])
        before = self.manifest_path.read_bytes()
        for destination in (
            self.manifest_path,
            self.manifest_path.parent / "." / self.manifest_path.name,
        ):
            with self.subTest(destination=str(destination)):
                process = subprocess.run(
                    [sys.executable, str(self.builder), "--repo", str(self.repo),
                     "--commit", self.commit, "--output", str(destination),
                     "--manifest", str(self.manifest_path),
                     "--manifest-sha256", pin],
                    capture_output=True, text=True, check=False, timeout=10,
                )
                self.assertEqual(process.returncode, 41)
                self.assertIn("MANIFEST_OUTPUT_COLLISION", process.stderr)
                self.assertEqual(self.manifest_path.read_bytes(), before)

    def test_cli_refuses_hardlink_alias_of_manifest(self):
        pin = self.approve(["app.py"])
        alias = Path(self.temp.name) / "approved-manifest-alias.json"
        os.link(self.manifest_path, alias)
        before = self.manifest_path.read_bytes()
        process = subprocess.run(
            [sys.executable, str(self.builder), "--repo", str(self.repo),
             "--commit", self.commit, "--output", str(alias),
             "--manifest", str(self.manifest_path), "--manifest-sha256", pin],
            capture_output=True, text=True, check=False, timeout=10,
        )
        self.assertEqual(process.returncode, 41)
        self.assertIn("MANIFEST_OUTPUT_COLLISION", process.stderr)
        self.assertEqual(self.manifest_path.read_bytes(), before)
        self.assertEqual(alias.read_bytes(), before)

    def test_cli_exact_manifest_positive(self):
        pin = self.approve(["app.py"])
        process = subprocess.run(
            [sys.executable, str(self.builder), "--repo", str(self.repo),
             "--commit", self.commit, "--output", str(self.output),
             "--manifest", str(self.manifest_path), "--manifest-sha256", pin],
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.namelist(), ["app.py"])


if __name__ == "__main__":
    unittest.main()
