#!/usr/bin/env python3
"""Build a release ZIP from Git commit blobs only, never the runner worktree.

This check is not an independent Guardian or a signature of the build.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unicodedata
import zipfile

MAX_FILES = 10_000
MAX_MEMBER_SIZE = 32 * 1024 * 1024
MAX_TOTAL_SIZE = 256 * 1024 * 1024
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
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.PIPE
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


def build(repo: Path, commit: str, output: Path) -> tuple[int, int]:
    repo = repo.resolve(strict=True)
    actual = git(repo, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
    if commit != actual or not re.fullmatch(r"[0-9a-f]{40}", actual):
        raise ValueError("COMMIT_PIN_MISMATCH")
    tree = git(repo, "ls-tree", "-rz", "--full-tree", commit)
    selected: list[tuple[str, str]] = []
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
        selected.append((name, object_id))
    if not selected or len(selected) > MAX_FILES:
        raise ValueError("INVALID_ARCHIVE_MEMBER_COUNT")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink() or output.parent.is_symlink():
        raise ValueError("UNSAFE_OUTPUT_PATH")
    temp_path: str | None = None
    total = 0
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".eroha-archive-", suffix=".zip",
            dir=output.parent, delete=False
        ) as temp:
            temp_path = temp.name
        with zipfile.ZipFile(
            temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9,
            allowZip64=False
        ) as archive:
            for name, object_id in selected:
                blob = git(repo, "cat-file", "blob", object_id)
                total += len(blob)
                if len(blob) > MAX_MEMBER_SIZE or total > MAX_TOTAL_SIZE:
                    raise ValueError("ARCHIVE_SIZE_LIMIT")
                member = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                member.create_system = 3
                member.external_attr = (0o100644 << 16)
                member.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(member, blob, compress_type=zipfile.ZIP_DEFLATED,
                                 compresslevel=9)
        if not zipfile.is_zipfile(temp_path):
            raise ValueError("INVALID_OUTPUT_ZIP")
        os.replace(temp_path, output)
        temp_path = None
        return len(selected), total
    finally:
        if temp_path is not None:
            Path(temp_path).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        count, total = build(args.repo, args.commit, args.output)
    except (ValueError, OSError, subprocess.CalledProcessError,
            UnicodeError, zipfile.BadZipFile, OverflowError) as error:
        print(f"RELEASE_ARCHIVE_REJECTED:{type(error).__name__}:{error}",
              file=sys.stderr)
        return 41
    print(f"RELEASE_ARCHIVE_BUILT members={count} source_bytes={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
