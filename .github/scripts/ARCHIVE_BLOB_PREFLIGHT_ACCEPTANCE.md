# EROHA — Git blob preflight resource-boundary audit (LAB)

**Date:** 2026-11-10  
**Research branch:** `research/archive-preflight-bounds-20261110`, based on Draft PR #44.  
**Result:** **LAB PASS** for bounded individual/aggregate Git blob reads; **G10 overall CPU/RAM resource enforcement remains NOT TESTED/NO-GO**.

## Observed defect (red test)

The proposed ZIP builder executed `git cat-file blob <oid>` via `subprocess.check_output`, which first allocated an entire Git blob into Python memory and only afterward compared `len(blob)` against `MAX_MEMBER_SIZE` and `MAX_TOTAL_SIZE`. A tracked huge object could exhaust process memory before the intended limit was enforced.

[GitHub Actions run 42809643560](https://github.com/Eroha68/eroha-pro/actions/runs/42809643560) **FAILED** as an intended negative reproduction. The two new tests instrumented Git calls to reject attempts to read a blob before size preflight: `test_oversized_git_blob_is_rejected_before_reading_it` and `test_total_limit_is_enforced_before_any_git_blob_read`. Both failed with `AssertionError` from a premature blob read. The baseline included 21 previously passing cases.

## Laboratory correction

The builder now queries **all selected committed object sizes** via `git cat-file -s` and enforces individual 32 MiB and aggregate 256 MiB logical limits **before reading any blob bytes**. Metadata must be a bounded decimal number. When fetching each blob for the ZIP, its actual uncompressed length must match preflight metadata; unexpected mismatch is rejected. Existing commit pinning, secret-path policy, no-symlink committed entries, path collision and deterministic ZIP behavior remain unchanged.

[GitHub Actions run 42809847486](https://github.com/Eroha68/eroha-pro/actions/runs/42809847486) **SUCCESS**: **23/23 tests normal Python and 23/23 under `python3 -O`**, including both formerly failing negative cases. This evidence covers synthetic Git object boundary handling, **not** actual measured peak RSS or arbitrary host-level memory constraints.

## Limits

- `git ls-tree -rz` still materializes complete tree metadata in memory; Git subprocess CPU/memory is not governed by this Python preflight.
- Python ZIP compression, CPU usage, memory allocator overhead, child processes, Windows/macOS behavior and full system-wide G10 isolation remain unmeasured.
- An independent Guardian and approved release authority remain unimplemented. **Do not merge as a security authorization gate.**
- The follow-on Draft PR #46 explores an exact release-member allowlist. That design intentionally requires manifest+SHA256 CLI arguments and **cannot be merged with PR #42's existing workflow without separately approved manifest custody and pipeline integration**.

**Safety:** disposable Ubuntu hosted runner, pinned checkout, GitHub `contents: read`, fake data and no release/HF write action. Production `main`, HF and MacBook unchanged.
