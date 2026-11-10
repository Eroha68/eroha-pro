# EROHA — exact release member manifest acceptance

**Date:** 2026-11-10  
**Candidate:** [Draft PR #46](https://github.com/Eroha68/eroha-pro/pull/46), based on Draft PR #45, which is based on Draft PR #44, itself based on Draft PR #42. No production `main` changes.  
**Verdict:** **LAB PASS** for exact synthetic release member selection; **industrial Guardian/Release Broker NO-GO**.

## Problem addressed

Even after sensitive filename denial, an ordinary tracked file such as `config.json` could contain a credential. A path denylist has no authoritative basis for deciding which files a release **should** contain. In this laboratory candidate the ZIP-builder CLI requires a separately supplied manifest and an exact SHA-256 digest.

Manifest format (synthetic example only):

```json
{
  "schema": 1,
  "commit": "1111111111111111111111111111111111111111",
  "files": ["app.py"]
}
```

The actual manifest is bound to the **exact Git HEAD commit**. The pin is the SHA-256 digest of the exact manifest bytes, with no canonicalization implied. The loader rejects missing, oversized, non-regular or symlinked files; digest mismatch; duplicate JSON fields; unexpected keys; invalid schema and commit; duplicate, unsorted, casefold-colliding or unsafe names. The builder rejects any mismatch between the full selected committed Git file set and the approved list **before** reading any of their bytes.

### Critical distinction: integrity vs authority

A separately checked hash proves bytes match an expected value, **not that a trusted human or independent Guardian authorized it**. In tests the digest is generated locally from synthetic fixtures. In a real pipeline the same repository/workflow author could change both manifest and hash; this would be **insufficient** for a release authorization. A separately controlled signed approval (or out-of-band pinned digest with owner-enforced custody), policy scope, expiry, revocation and unforgeable provenance must be independently implemented and tested.

### Intentional fail-closed rollout blocker

The new CLI requires `--manifest` and `--manifest-sha256`; the *existing* proposed release workflow in Draft PR #42 does **not** pass these parameters. Combining and merging these research branches today would cause the build stage to fail, which is safer than silently accepting an unapproved archive. **No release manifest for real `eroha-pro` has been chosen or approved.** Do not merge until the production release file list, custodian and exact rollout contract are authorized and independently verified.

## Actual GitHub-hosted runner evidence

[Run 42810510349](https://github.com/Eroha68/eroha-pro/actions/runs/42810510349) — **SUCCESS**. `35/35` unittest cases in normal Python and `35/35` with `python3 -O`. The 12 new synthetic tests verify exact allowed members, rejection of an additional tracked `config.json`, digest tampering, wrong commit, duplicate JSON keys, path collisions, forbidden paths, missing/symlinked manifests, type-safe schema, CLI refusal without approval and CLI success with explicit test approval.

The 23 pre-existing tests cover tracked blob content, deterministic ZIP, committed symlink rejection, secret-path policy and preflight-size enforcement.

**No deployed artifact attestation, off-host permission, actual release, MacBook or HF change is implied.**

## Industrial open items

- Independent custody of release manifest and signed/pinned approval, with policy versioning and expiry.
- Actual product release inventory, reviewed expected file list and integration of CLI manifest parameters into the protected release workflow.
- Independent Guardian signed grant and exclusive Broker publish rights.
- Immutable CI run/source provenance, GitHub protected status checks and release environment; Hugging Face direct-deploy bypass closure.
- Crash recovery, real rollback and G10 enforced aggregate memory/CPU budgets.
- Industrial matrices: 18 A01–F18 scenarios, >=24 partially overlapping G1–G6 external scenarios; research R2–R4 and G10 still open.

**Decision: Keep DRAFT, laboratory verification PASS, industrial release NO-GO.**
