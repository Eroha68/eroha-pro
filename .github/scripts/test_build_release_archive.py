"""Synthetic negative tests for the commit-only release archive builder."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from build_release_archive import build


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.PIPE,
        text=True
    ).strip()


class ArchiveBoundaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="eroha-archive-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "EROHA Synthetic Test")
        git(self.repo, "config", "user.email", "nobody@example.invalid")
        (self.repo / "app.py").write_text("print('committed')\n", encoding="utf-8")
        (self.repo / ".github").mkdir()
        (self.repo / ".github" / "workflow.yml").write_text("name: fixture\n",
                                                               encoding="utf-8")
        git(self.repo, "add", "app.py", ".github/workflow.yml")
        git(self.repo, "commit", "-qm", "Committed fixture only")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        self.output = self.repo / "artifacts" / "release.zip"

    def add_commit(self, name: str, data: bytes = b"x") -> None:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        git(self.repo, "add", name)
        git(self.repo, "commit", "-qm", "Synthetic modification")
        self.commit = git(self.repo, "rev-parse", "HEAD")

    def names(self) -> list[str]:
        with zipfile.ZipFile(self.output) as archive:
            return archive.namelist()

    def test_tracked_content_exact_and_worktree_modification_ignored(self):
        (self.repo / "app.py").write_text("print('uncommitted mutation')\n",
                                          encoding="utf-8")
        self.assertEqual(build(self.repo, self.commit, self.output), (1, 19))
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.read("app.py"), b"print('committed')\n")

    def test_untracked_environment_and_previous_archives_excluded(self):
        (self.repo / ".env").write_text("SYNTHETIC_ONLY", encoding="utf-8")
        (self.repo / "scratch.txt").write_text("not committed", encoding="utf-8")
        self.output.parent.mkdir()
        (self.output.parent / "old.zip").write_bytes(b"not a zip")
        build(self.repo, self.commit, self.output)
        self.assertEqual(self.names(), ["app.py"])

    def test_tracked_dot_env_never_included(self):
        self.add_commit(".env", b"synthetic-not-a-secret")
        build(self.repo, self.commit, self.output)
        self.assertEqual(self.names(), ["app.py"])

    def test_tracked_secret_like_key_rejected(self):
        self.add_commit("private.pem", b"synthetic marker")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())

    def test_symlink_in_committed_tree_rejected(self):
        link = self.repo / "jump"
        link.symlink_to("app.py")
        git(self.repo, "add", "jump")
        git(self.repo, "commit", "-qm", "Synthetic symlink")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_COMMITTED_FILE_TYPE"):
            build(self.repo, self.commit, self.output)

    def test_case_insensitive_collision_rejected(self):
        self.add_commit("App.PY", b"duplicate case")
        with self.assertRaisesRegex(ValueError, "COLLIDING_ARCHIVE_PATHS"):
            build(self.repo, self.commit, self.output)

    def test_windows_reserved_filename_rejected(self):
        self.add_commit("CON.txt", b"reserved")
        with self.assertRaisesRegex(ValueError, "UNSAFE_ARCHIVE_PATH"):
            build(self.repo, self.commit, self.output)

    def test_unicode_noncanonical_filename_rejected(self):
        self.add_commit("e\u0301.txt", b"unicode")
        with self.assertRaisesRegex(ValueError, "NONCANONICAL_ARCHIVE_PATH"):
            build(self.repo, self.commit, self.output)

    def test_control_character_filename_rejected(self):
        self.add_commit("line\nbreak.txt", b"control")
        with self.assertRaisesRegex(ValueError, "UNSAFE_ARCHIVE_PATH"):
            build(self.repo, self.commit, self.output)

    def test_commit_pin_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "COMMIT_PIN_MISMATCH"):
            build(self.repo, "0" * 40, self.output)
        self.assertFalse(self.output.exists())

    def test_size_policy_fails_closed_and_keeps_previous_output(self):
        import build_release_archive
        original = build_release_archive.MAX_MEMBER_SIZE
        self.addCleanup(setattr, build_release_archive, "MAX_MEMBER_SIZE", original)
        build(self.repo, self.commit, self.output)
        old = self.output.read_bytes()
        build_release_archive.MAX_MEMBER_SIZE = 1
        with self.assertRaisesRegex(ValueError, "ARCHIVE_SIZE_LIMIT"):
            build(self.repo, self.commit, self.output)
        self.assertEqual(self.output.read_bytes(), old)

    def test_archive_is_deterministic(self):
        first = self.repo / "artifacts" / "release-a.zip"
        second = self.repo / "artifacts" / "release-b.zip"
        build(self.repo, self.commit, first)
        build(self.repo, self.commit, second)
        self.assertEqual(hashlib.sha256(first.read_bytes()).digest(),
                         hashlib.sha256(second.read_bytes()).digest())

    def test_only_excluded_files_fails_closed(self):
        (self.repo / "app.py").unlink()
        git(self.repo, "add", "-u")
        git(self.repo, "commit", "-qm", "No included files")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "INVALID_ARCHIVE_MEMBER_COUNT"):
            build(self.repo, self.commit, self.output)


    def test_tracked_nested_dotenv_directory_must_not_leak(self):
        self.add_commit(".env/credentials.txt",
                        b"EROHA_SYNTHETIC_SECRET_SENTINEL_NOT_REAL")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())

    def test_tracked_nested_environment_variant_must_not_leak(self):
        self.add_commit("config/.env.production/credentials.json",
                        b"EROHA_SYNTHETIC_SECRET_SENTINEL_NOT_REAL")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())

    def test_tracked_npmrc_must_not_leak(self):
        self.add_commit(".npmrc", b"//registry.example.invalid/:_authToken=SYNTHETIC_ONLY")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())

    def test_tracked_ssh_private_key_without_suffix_must_not_leak(self):
        self.add_commit(".ssh/id_ed25519", b"SYNTHETIC_PRIVATE_KEY_NOT_REAL")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
