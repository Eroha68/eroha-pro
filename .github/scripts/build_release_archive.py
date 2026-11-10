#!/usr/bin/env python3
"""Build a release ZIP from Git commit blobs only, never the runner worktree.

This check is not an independent Guardian or a signature of the build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import unicodedata
import zipfile

MAX_FILES = 10_000
MAX_MEMBER_SIZE = 32 * 1024 * 1024
MAX_TOTAL_SIZE = 256 * 1024 * 1024
MAX_MANIFEST_SIZE = 128 * 1024
FORBIDDEN_COMPONENTS = {".git", ".github", "artifacts", "__pycache__"}
FORBIDDEN_EXTENSIONS = {".pem", ".p12", ".pfx", ".key", ".kdbx"}
# Sensitive credential locations without necessarily dangerous file extensions.
SENSITIVE_DIRECTORIES = {".ssh", ".aws", ".azure", ".kube", ".gnupg"}
SENSITIVE_FILENAMES = {".npmrc", ".pypirc", ".netrc", "id_rsa",
                       "id_dsa", "id_ecdsa", "id_ed25519"}
WINDOWS_FORBIDDEN = re.compile(r'[<>:"\\|?*\x00-\x1f]')
WINDOWS_RESERVED = re.compile(
    r"(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$"
)


def git(repo: Path, *args: str) -> bytes:
    # Do not inherit caller-controlled Git discovery, object-store or
    # config overrides. These can redirect reads away from the pinned repo.
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith("GIT_")}
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    # Partial clones must fail on missing objects instead of silently
    # fetching unreviewed data through a configured promisor remote.
    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.PIPE, env=env
    )


def safe_name(path: str) -> str:
    if not path or path.startswith("/") or "\\" in path:
        raise ValueError("UNSAFE_ARCHIVE_PATH")
    if any(part in ("", ".", "..") for part in path.split("/")):
        raise ValueError("UNSAFE_ARCHIVE_PATH")
    if any(WINDOWS_FORBIDDEN.search(part) or WINDOWS_RESERVED.match(part)
           or part.endswith((" ", ".")) for part in path.split("/")):
        raise ValueError("UNSAFE_ARCHIVE_PATH")
    if unicodedata.normalize("NFC", path) != path:
        raise ValueError("NONCANONICAL_ARCHIVE_PATH")
    return path


def is_forbidden(path: str) -> bool:
    parts = [component.lower() for component in path.split("/")]
    basename = parts[-1]
    if any(component in FORBIDDEN_COMPONENTS for component in parts):
        return True
    # A directly tracked .env or .env.production file is excluded as before.
    # An *entire directory* of the same name is a different leak path:
    # fail the whole release rather than silently shipping nested secrets.
    if basename == ".env" or basename.startswith(".env."):
        return True
    if any(component == ".env" or component.startswith(".env.")
           for component in parts[:-1]):
        raise ValueError("SECRET_LIKE_TRACKED_FILE")
    if any(component in SENSITIVE_DIRECTORIES for component in parts):
        raise ValueError("SECRET_LIKE_TRACKED_FILE")
    if basename in SENSITIVE_FILENAMES:
        raise ValueError("SECRET_LIKE_TRACKED_FILE")
    if any(basename.endswith(extension) for extension in FORBIDDEN_EXTENSIONS):
        raise ValueError("SECRET_LIKE_TRACKED_FILE")
    return False


def load_approved_manifest(path: Path, commit: str,
                           approved_sha256: str) -> frozenset[str]:
    """Validate an exact-path allowlist against an out-of-band digest pin.

    This does NOT prove who approved the digest. Independent key custody
    and approval remain separate industrial requirements.
    """
    if not re.fullmatch(r"[0-9a-f]{64}", approved_sha256):
        raise ValueError("MANIFEST_DIGEST_INVALID")
    # Do not normalize away a traversed symlink/.. component.
    if ".." in path.parts:
        raise ValueError("MANIFEST_UNAVAILABLE")
    # Anchor every directory lookup to an already opened directory fd.
    # A path-wide is_symlink() precheck is racy: an ancestor can change
    # between that check and the final open().
    if (os.name != "posix" or not hasattr(os, "O_NOFOLLOW") or
            not hasattr(os, "O_DIRECTORY") or os.open not in os.supports_dir_fd):
        raise ValueError("MANIFEST_SAFE_OPEN_UNSUPPORTED")
    absolute_manifest = Path(os.path.abspath(path))
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    dir_fd = None
    try:
        dir_fd = os.open(absolute_manifest.anchor, dir_flags)
        for component in absolute_manifest.parts[1:-1]:
            child_fd = os.open(component, dir_flags, dir_fd=dir_fd)
            os.close(dir_fd)
            dir_fd = child_fd
        fd = os.open(absolute_manifest.name, file_flags, dir_fd=dir_fd)
        with os.fdopen(fd, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError("MANIFEST_UNSAFE_FILE_TYPE")
            raw = source.read(MAX_MANIFEST_SIZE + 1)
    except OSError as exc:
        raise ValueError("MANIFEST_UNAVAILABLE") from exc
    finally:
        if dir_fd is not None:
            os.close(dir_fd)
    if not raw or len(raw) > MAX_MANIFEST_SIZE:
        raise ValueError("MANIFEST_SIZE_LIMIT")
    if hashlib.sha256(raw).hexdigest() != approved_sha256:
        raise ValueError("MANIFEST_HASH_MISMATCH")

    def no_duplicate_keys(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("MANIFEST_DUPLICATE_KEY")
            result[key] = value
        return result

    def no_nonfinite(value):
        raise ValueError("MANIFEST_NONFINITE_NUMBER")

    manifest = json.loads(raw.decode("utf-8", "strict"),
                          object_pairs_hook=no_duplicate_keys,
                          parse_constant=no_nonfinite)
    if (type(manifest) is not dict or
            frozenset(manifest) != {"schema", "commit", "files"} or
            type(manifest["schema"]) is not int or
            manifest["schema"] != 1 or
            type(manifest["commit"]) is not str or
            manifest["commit"] != commit):
        raise ValueError("MANIFEST_SCHEMA_OR_COMMIT_MISMATCH")
    files = manifest["files"]
    if (type(files) is not list or not 0 < len(files) <= MAX_FILES or
            any(type(name) is not str for name in files)):
        raise ValueError("MANIFEST_FILE_LIST_INVALID")
    if files != sorted(files) or len(files) != len(set(files)):
        raise ValueError("MANIFEST_DUPLICATE_OR_UNSORTED_FILES")
    normalized = set()
    for name in files:
        safe_name(name)
        if (is_forbidden(name) or
                any(part in (".", "..") for part in name.split("/"))):
            raise ValueError("MANIFEST_FORBIDDEN_PATH")
        folded = unicodedata.normalize("NFC", name).casefold()
        if folded in normalized:
            raise ValueError("MANIFEST_COLLIDING_PATHS")
        normalized.add(folded)
    for name in files:
        parts = name.casefold().split("/")
        if any("/".join(parts[:depth]) in normalized
               for depth in range(1, len(parts))):
            raise ValueError("MANIFEST_COLLIDING_PATHS")
    return frozenset(files)


def build(repo: Path, commit: str, output: Path,
          approved_paths: frozenset[str]) -> tuple[int, int]:
    # An omitted or malformed approval must fail before touching Git or disk.
    if (type(approved_paths) is not frozenset or
            any(type(name) is not str for name in approved_paths)):
        raise ValueError("MANIFEST_APPROVAL_REQUIRED")
    repo = repo.resolve(strict=True)
    actual = git(repo, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
    if commit != actual or not re.fullmatch(r"[0-9a-f]{40}", actual):
        raise ValueError("COMMIT_PIN_MISMATCH")
    tree = git(repo, "ls-tree", "-rz", "--full-tree", commit)
    selected: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        metadata, separator, raw_name = entry.partition(b"\t")
        if not separator:
            raise ValueError("INVALID_GIT_TREE_ENTRY")
        mode, kind, object_id = metadata.decode("ascii").split()
        name = safe_name(raw_name.decode("utf-8", "strict"))
        if is_forbidden(name):
            continue
        if kind != "blob" or mode not in ("100644", "100755"):
            raise ValueError("UNSUPPORTED_COMMITTED_FILE_TYPE")
        normalized = unicodedata.normalize("NFC", name).casefold()
        if normalized in seen:
            raise ValueError("COLLIDING_ARCHIVE_PATHS")
        seen.add(normalized)
        selected.append((name, object_id, mode))
    # Case-insensitive extraction must not reinterpret a file as a directory.
    folded_members = {name.casefold() for name, _, _ in selected}
    for name, _, _ in selected:
        parts = name.casefold().split("/")
        if any("/".join(parts[:depth]) in folded_members
               for depth in range(1, len(parts))):
            raise ValueError("COLLIDING_ARCHIVE_PATHS")
    if not selected or len(selected) > MAX_FILES:
        raise ValueError("INVALID_ARCHIVE_MEMBER_COUNT")
    if {name for name, _, _ in selected} != approved_paths:
        raise ValueError("MANIFEST_MEMBER_SET_MISMATCH")
    # Check sizes of ALL committed blobs before reading even the first byte.
    # Git object identity is immutable; a size query cannot enlarge the
    # content but reading a blob with check_output could exhaust RAM.
    preflight: list[tuple[str, str, str, int]] = []
    planned_total = 0
    for name, object_id, mode in selected:
        size_raw = git(repo, "cat-file", "-s", object_id).decode("ascii").strip()
        if not re.fullmatch(r"[0-9]{1,20}", size_raw):
            raise ValueError("INVALID_GIT_OBJECT_SIZE")
        size = int(size_raw)
        planned_total += size
        if size > MAX_MEMBER_SIZE or planned_total > MAX_TOTAL_SIZE:
            raise ValueError("ARCHIVE_SIZE_LIMIT")
        preflight.append((name, object_id, mode, size))
    # Do not normalize away a traversed symlink/.. component.
    if ".." in output.parts:
        raise ValueError("UNSAFE_OUTPUT_PATH")
    # Anchor output directory creation and final replacement to open fds.
    # A string path can be redirected to another tree after is_symlink().
    if (os.name != "posix" or not hasattr(os, "O_NOFOLLOW") or
            not hasattr(os, "O_DIRECTORY") or
            any(fn not in os.supports_dir_fd
                for fn in (os.open, os.mkdir, os.unlink, os.stat))):
        raise ValueError("OUTPUT_SAFE_OPEN_UNSUPPORTED")
    absolute_output = Path(os.path.abspath(output))
    directory_flags = (os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                       getattr(os, "O_CLOEXEC", 0))
    parent_fd = None
    temp_name = None
    total = 0
    try:
        parent_fd = os.open(absolute_output.anchor, directory_flags)
        for component in absolute_output.parts[1:-1]:
            try:
                next_fd = os.open(component, directory_flags, dir_fd=parent_fd)
            except FileNotFoundError:
                os.mkdir(component, mode=0o700, dir_fd=parent_fd)
                next_fd = os.open(component, directory_flags, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = next_fd
        try:
            existing = os.stat(absolute_output.name, dir_fd=parent_fd,
                               follow_symlinks=False)
            if stat.S_ISLNK(existing.st_mode):
                raise ValueError("UNSAFE_OUTPUT_PATH")
        except FileNotFoundError:
            pass
        temp_name = ".eroha-archive-" + secrets.token_hex(16) + ".zip"
        temp_fd = os.open(
            temp_name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW |
            getattr(os, "O_CLOEXEC", 0), mode=0o600, dir_fd=parent_fd,
        )
        with os.fdopen(temp_fd, "w+b") as temp_file:
            with zipfile.ZipFile(
                temp_file, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9,
                allowZip64=False,
            ) as archive:
                for name, object_id, mode, expected_size in preflight:
                    blob = git(repo, "cat-file", "blob", object_id)
                    if len(blob) != expected_size:
                        raise ValueError("GIT_BLOB_SIZE_MISMATCH")
                    total += len(blob)
                    if total > MAX_TOTAL_SIZE:
                        raise ValueError("ARCHIVE_SIZE_LIMIT")
                    member = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    member.create_system = 3
                    member.external_attr = ((0o100755 if mode == "100755" else 0o100644) << 16)
                    member.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(member, blob, compress_type=zipfile.ZIP_DEFLATED,
                                     compresslevel=9)
            temp_file.flush()
            if not zipfile.is_zipfile(temp_file):
                raise ValueError("INVALID_OUTPUT_ZIP")
        os.replace(temp_name, absolute_output.name,
                   src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        temp_name = None
        return len(selected), total
    except OSError as exc:
        raise ValueError("UNSAFE_OUTPUT_PATH") from exc
    finally:
        if parent_fd is not None:
            if temp_name is not None:
                try:
                    os.unlink(temp_name, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass
            os.close(parent_fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        # Never allow the ZIP destination to overwrite its authorization input.
        # Catch both lexical aliases and existing hardlinks to the same inode.
        if (os.path.abspath(args.output) == os.path.abspath(args.manifest) or
                (args.output.exists() and args.manifest.exists() and
                 os.path.samefile(args.output, args.manifest))):
            raise ValueError("MANIFEST_OUTPUT_COLLISION")
        approved_paths = load_approved_manifest(args.manifest, args.commit,
                                                 args.manifest_sha256)
        count, total = build(args.repo, args.commit, args.output,
                             approved_paths=approved_paths)
    except (ValueError, OSError, subprocess.CalledProcessError,
            UnicodeError, zipfile.BadZipFile, OverflowError) as error:
        print(f"RELEASE_ARCHIVE_REJECTED:{type(error).__name__}:{error}",
              file=sys.stderr)
        return 41
    print(f"RELEASE_ARCHIVE_BUILT members={count} source_bytes={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
