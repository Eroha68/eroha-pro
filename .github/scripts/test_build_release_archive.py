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

    def approved_fixture_paths(self) -> frozenset[str]:
        # Test-only self-approval. This is not an independent Guardian grant.
        raw = subprocess.check_output(
            ["git", "-C", str(self.repo), "ls-files", "-z", "--cached"]
        )
        names = (entry.decode("utf-8") for entry in raw.split(bytes([0])) if entry)
        return frozenset(
            name for name in names
            if not name.lower().startswith(".github/")
            and not (name.lower() == ".env" or name.lower().startswith(".env."))
        )

    def fixture_build(self, repo: Path, commit: str, output: Path):
        return build(repo, commit, output, self.approved_fixture_paths())

    def test_missing_approval_rejected_before_archive_creation(self):
        with self.assertRaises(TypeError):
            build(self.repo, self.commit, self.output)
        with self.assertRaisesRegex(ValueError, "MANIFEST_APPROVAL_REQUIRED"):
            build(self.repo, self.commit, self.output, None)
        self.assertFalse(self.output.exists())

    def names(self) -> list[str]:
        with zipfile.ZipFile(self.output) as archive:
            return archive.namelist()

    def test_tracked_content_exact_and_worktree_modification_ignored(self):
        (self.repo / "app.py").write_text("print('uncommitted mutation')\n",
                                          encoding="utf-8")
        self.assertEqual(self.fixture_build(self.repo, self.commit, self.output), (1, 19))
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.read("app.py"), b"print('committed')\n")

    def test_untracked_environment_and_previous_archives_excluded(self):
        (self.repo / ".env").write_text("SYNTHETIC_ONLY", encoding="utf-8")
        (self.repo / "scratch.txt").write_text("not committed", encoding="utf-8")
        self.output.parent.mkdir()
        (self.output.parent / "old.zip").write_bytes(b"not a zip")
        self.fixture_build(self.repo, self.commit, self.output)
        self.assertEqual(self.names(), ["app.py"])

    def test_tracked_dot_env_never_included(self):
        self.add_commit(".env", b"synthetic-not-a-secret")
        self.fixture_build(self.repo, self.commit, self.output)
        self.assertEqual(self.names(), ["app.py"])

    def test_tracked_secret_like_key_rejected(self):
        self.add_commit("private.pem", b"synthetic marker")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            self.fixture_build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())

    def test_symlink_in_committed_tree_rejected(self):
        link = self.repo / "jump"
        link.symlink_to("app.py")
        git(self.repo, "add", "jump")
        git(self.repo, "commit", "-qm", "Synthetic symlink")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_COMMITTED_FILE_TYPE"):
            self.fixture_build(self.repo, self.commit, self.output)

    def test_case_insensitive_collision_rejected(self):
        self.add_commit("App.PY", b"duplicate case")
        with self.assertRaisesRegex(ValueError, "COLLIDING_ARCHIVE_PATHS"):
            self.fixture_build(self.repo, self.commit, self.output)

    def test_windows_reserved_filename_rejected(self):
        self.add_commit("CON.txt", b"reserved")
        with self.assertRaisesRegex(ValueError, "UNSAFE_ARCHIVE_PATH"):
            self.fixture_build(self.repo, self.commit, self.output)

    def test_unicode_noncanonical_filename_rejected(self):
        self.add_commit("e\u0301.txt", b"unicode")
        with self.assertRaisesRegex(ValueError, "NONCANONICAL_ARCHIVE_PATH"):
            self.fixture_build(self.repo, self.commit, self.output)

    def test_control_character_filename_rejected(self):
        self.add_commit("line\nbreak.txt", b"control")
        with self.assertRaisesRegex(ValueError, "UNSAFE_ARCHIVE_PATH"):
            self.fixture_build(self.repo, self.commit, self.output)

    def test_git_reads_disable_promisor_lazy_fetch_and_optional_locks(self):
        import build_release_archive as module
        from unittest.mock import patch

        approved = self.approved_fixture_paths()
        underlying = module.subprocess.check_output
        git_environments = []

        def inspect_git(*args, **kwargs):
            if args and args[0] and args[0][0] == "git":
                git_environments.append(kwargs["env"])
            return underlying(*args, **kwargs)

        with patch.object(module.subprocess, "check_output", side_effect=inspect_git):
            build(self.repo, self.commit, self.output, approved)
        self.assertTrue(git_environments)
        for env in git_environments:
            self.assertEqual(env.get("GIT_NO_LAZY_FETCH"), "1")
            self.assertEqual(env.get("GIT_NO_REPLACE_OBJECTS"), "1")
            self.assertEqual(env.get("GIT_OPTIONAL_LOCKS"), "0")

    def test_inherited_git_environment_cannot_redirect_object_reads(self):
        from unittest.mock import patch

        original = (self.repo / "app.py").read_bytes()
        approved = self.approved_fixture_paths()
        with patch.dict(os.environ, {
            "GIT_DIR": str(self.repo / "nonexistent-foreign-git-dir"),
            "GIT_WORK_TREE": str(self.repo / "other-worktree"),
            "GIT_OBJECT_DIRECTORY": str(self.repo / "foreign-objects"),
            "GIT_NO_REPLACE_OBJECTS": "0",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.bare",
            "GIT_CONFIG_VALUE_0": "true",
        }):
            build(self.repo, self.commit, self.output, approved)
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.read("app.py"), original)

    def test_git_replace_ref_cannot_substitute_pinned_commit_tree(self):
        original_commit = self.commit
        original_bytes = (self.repo / "app.py").read_bytes()
        (self.repo / "app.py").write_bytes(b"synthetic substituted content")
        git(self.repo, "add", "app.py")
        replacement_tree = git(self.repo, "write-tree")
        replacement_commit = git(self.repo, "commit-tree", replacement_tree, "-m",
                                 "Synthetic replace-only commit")
        git(self.repo, "reset", "--hard", original_commit)
        git(self.repo, "replace", original_commit, replacement_commit)
        self.addCleanup(lambda: subprocess.run(
            ["git", "-C", str(self.repo), "replace", "-d", original_commit],
            capture_output=True, check=False,
        ))
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), original_commit)
        self.assertNotEqual(
            subprocess.check_output(
                ["git", "-C", str(self.repo), "show", f"{original_commit}:app.py"]
            ), original_bytes,
        )
        self.fixture_build(self.repo, original_commit, self.output)
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.read("app.py"), original_bytes)

    def test_commit_pin_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "COMMIT_PIN_MISMATCH"):
            self.fixture_build(self.repo, "0" * 40, self.output)
        self.assertFalse(self.output.exists())

    def test_output_parent_traversal_rejected_before_directory_creation(self):
        destination = self.repo / "unused" / ".." / "artifacts" / "release.zip"
        with self.assertRaisesRegex(ValueError, "UNSAFE_OUTPUT_PATH"):
            self.fixture_build(self.repo, self.commit, destination)
        self.assertFalse(self.output.parent.exists())

    def test_symlinked_output_ancestor_rejected_before_directory_creation(self):
        external = Path(self.temp.name) / "external"
        external.mkdir()
        link = self.repo / "redirect"
        link.symlink_to(external, target_is_directory=True)
        destination = link / "nested" / "release.zip"
        with self.assertRaisesRegex(ValueError, "UNSAFE_OUTPUT_PATH"):
            self.fixture_build(self.repo, self.commit, destination)
        self.assertFalse((external / "nested").exists())

    def test_size_policy_fails_closed_and_keeps_previous_output(self):
        import build_release_archive
        original = build_release_archive.MAX_MEMBER_SIZE
        self.addCleanup(setattr, build_release_archive, "MAX_MEMBER_SIZE", original)
        self.fixture_build(self.repo, self.commit, self.output)
        old = self.output.read_bytes()
        build_release_archive.MAX_MEMBER_SIZE = 1
        with self.assertRaisesRegex(ValueError, "ARCHIVE_SIZE_LIMIT"):
            self.fixture_build(self.repo, self.commit, self.output)
        self.assertEqual(self.output.read_bytes(), old)

    def test_archive_is_deterministic(self):
        first = self.repo / "artifacts" / "release-a.zip"
        second = self.repo / "artifacts" / "release-b.zip"
        self.fixture_build(self.repo, self.commit, first)
        self.fixture_build(self.repo, self.commit, second)
        self.assertEqual(hashlib.sha256(first.read_bytes()).digest(),
                         hashlib.sha256(second.read_bytes()).digest())

    def test_only_excluded_files_fails_closed(self):
        (self.repo / "app.py").unlink()
        git(self.repo, "add", "-u")
        git(self.repo, "commit", "-qm", "No included files")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "INVALID_ARCHIVE_MEMBER_COUNT"):
            self.fixture_build(self.repo, self.commit, self.output)


    def test_tracked_nested_dotenv_directory_must_not_leak(self):
        self.add_commit(".env/credentials.txt",
                        b"EROHA_SYNTHETIC_SECRET_SENTINEL_NOT_REAL")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            self.fixture_build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())

    def test_tracked_nested_environment_variant_must_not_leak(self):
        self.add_commit("config/.env.production/credentials.json",
                        b"EROHA_SYNTHETIC_SECRET_SENTINEL_NOT_REAL")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            self.fixture_build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())

    def test_tracked_npmrc_must_not_leak(self):
        self.add_commit(".npmrc", b"//registry.example.invalid/:_authToken=SYNTHETIC_ONLY")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            self.fixture_build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())

    def test_tracked_ssh_private_key_without_suffix_must_not_leak(self):
        self.add_commit(".ssh/id_ed25519", b"SYNTHETIC_PRIVATE_KEY_NOT_REAL")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            self.fixture_build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())


    def test_tracked_aws_credentials_directory_is_rejected(self):
        self.add_commit(".aws/credentials", b"[default]\nSYNTHETIC_NOT_REAL\n")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            self.fixture_build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())

    def test_tracked_nested_kube_config_is_rejected(self):
        self.add_commit("deploy/.kube/config", b"SYNTHETIC_NOT_REAL")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            self.fixture_build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())

    def test_tracked_pypirc_is_rejected(self):
        self.add_commit(".pypirc", b"[distutils]\npassword=SYNTHETIC_ONLY\n")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            self.fixture_build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())

    def test_case_variant_dotenv_directory_is_rejected(self):
        self.add_commit("config/.ENV.Staging/key.json", b"SYNTHETIC_NOT_REAL")
        with self.assertRaisesRegex(ValueError, "SECRET_LIKE_TRACKED_FILE"):
            self.fixture_build(self.repo, self.commit, self.output)
        self.assertFalse(self.output.exists())


    def test_oversized_git_blob_is_rejected_before_reading_it(self):
        import build_release_archive as module
        from unittest.mock import patch

        original_limit = module.MAX_MEMBER_SIZE
        self.addCleanup(setattr, module, "MAX_MEMBER_SIZE", original_limit)
        module.MAX_MEMBER_SIZE = 4
        original_git = module.git
        read_attempts = []

        def counted_git(repo, *args):
            if args[:2] == ("cat-file", "blob"):
                read_attempts.append(args)
                raise AssertionError("UNBOUNDED_BLOB_READ_ATTEMPTED")
            return original_git(repo, *args)

        with patch.object(module, "git", side_effect=counted_git):
            with self.assertRaisesRegex(ValueError, "ARCHIVE_SIZE_LIMIT"):
                self.fixture_build(self.repo, self.commit, self.output)
        self.assertEqual([], read_attempts)
        self.assertFalse(self.output.exists())

    def test_total_limit_is_enforced_before_any_git_blob_read(self):
        import build_release_archive as module
        from unittest.mock import patch

        self.add_commit("second.txt", b"12345")
        old_total = module.MAX_TOTAL_SIZE
        self.addCleanup(setattr, module, "MAX_TOTAL_SIZE", old_total)
        module.MAX_TOTAL_SIZE = 20  # existing app.py 19 + second.txt 5 = 24
        original_git = module.git
        read_attempts = []

        def counted_git(repo, *args):
            if args[:2] == ("cat-file", "blob"):
                read_attempts.append(args)
                raise AssertionError("BLOB_READ_BEFORE_TOTAL_PREFLIGHT")
            return original_git(repo, *args)

        with patch.object(module, "git", side_effect=counted_git):
            with self.assertRaisesRegex(ValueError, "ARCHIVE_SIZE_LIMIT"):
                self.fixture_build(self.repo, self.commit, self.output)
        self.assertEqual([], read_attempts)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
