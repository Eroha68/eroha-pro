# EROHA release archive: tracked credential path hardening

**Date:** 2026-11-10.  
**Context:** Research-only Draft PR #44, based on Draft PR #42; no edits to production main.  
**Verdict:** **LAB PASS** for 21 synthetic archive tests in normal Python and `python3 -O`; **industrial release still NO-GO**.

## Original defect, confirmed by a RED runner

PR #42's Git-blob ZIP builder applied `is_forbidden()` to the **basename** of a tracked file. It excluded `.env` itself but did not reject `.env/credentials.txt` or `config/.env.production/credentials.json`; it also lacked explicit handling for `.npmrc` and `.ssh/id_ed25519`. A committed file at these paths would be selected for the release archive. This is a **possible secret-disclosure path**, not evidence that any actual credential was present or released.

[GitHub Actions run 42808211047](https://github.com/Eroha68/eroha-pro/actions/runs/42808211047) — **RED / expected FAIL**. The four new tests rejected none of these paths: each failed with `AssertionError: ValueError not raised`. Baseline: 13 earlier tests, 4 new failures, total 17.

## Correction

- Continue silently excluding direct `.env` and `.env.*` files, as the previous builder did.
- Fail closed with `SECRET_LIKE_TRACKED_FILE` if any **parent directory** is `.env` or starts `.env.` (case-insensitive).
- Fail closed for components `.ssh`, `.aws`, `.azure`, `.kube`, `.gnupg`, and names `.npmrc`, `.pypirc`, `.netrc`, `id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519`, including nested occurrences.
- Preserve existing fatal extensions `.pem`, `.p12`, `.pfx`, `.key`, `.kdbx`, Git commit pinning, deterministic ZIP output and path-collision checks.

## Actual acceptance evidence

- [Run 42808453296](https://github.com/Eroha68/eroha-pro/actions/runs/42808453296): **17/17 PASS** normal Python; **17/17 PASS** with `-O`. The same four formerly failing cases now pass.
- [Run 42808715410](https://github.com/Eroha68/eroha-pro/actions/runs/42808715410): **21/21 PASS** normal Python; **21/21 PASS** with `-O`. Four additional cases cover `.aws/credentials`, nested `.kube/config`, `.pypirc` and upper-case `.ENV.Staging`.

The jobs are hosted Ubuntu 24.04, read-only `contents: read`, pinned `actions/checkout`, no `sudo`, real keys, network publish, or production branch changes. No main workflow was activated by the research branch.

## Design limitations and industrial acceptance

This is a **path-policy denylist**, not secret scanning or a positive manifest. A committed credential hidden in an ordinary file such as `src/settings.py` or `data/config.json` could still be packaged. Future release policy should prefer a reviewed **allowlist/manifest of release members**, content scanning with appropriate false-positive handling, and independently verified provenance/authorization. Those changes require validation against actual intended release contents; none is implied or completed here.

Official GitHub documentation confirms artifact attestations can provide build provenance, but an attestation of a repository-controlled build does **not** itself establish an independent Guardian approval or restrict who may release. For public repositories artifact attestations are available across current plans; for private/internal repositories, plan restrictions apply. GitHub environment required reviewers and administrator-bypass controls are additional deployment gates that must be **configured and independently verified**; merely placing an `environment` name in workflow YAML does not enforce a security policy.

**NO-GO remains** for Draft PR #42: independent Guardian/Release Broker, exclusive write credentials, protected branch/environments, orphan-release remediation, trusted upload provenance, rollback, and A01–F18/G1–G6/G10 industrial acceptance. Do not merge or publish from this Draft.
