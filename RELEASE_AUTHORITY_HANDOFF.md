# EROHA — controlled release-authority handoff

Status: **PROPOSAL / DRAFT / NOT DEPLOYED / INDUSTRIAL NO-GO**  
Evidence checked: 2026-11-10. This file describes a migration, not user approval to execute it.

## Verified boundary at handoff

- The current `main` contains **three identified write-capable paths in source**: `.github/workflows/eroha_core_ci.yml` has an active `release` job, `contents: write`, and `git push`; `.github/workflows/deploy.yml` uses `secrets.HF_TOKEN` and pushes to Hugging Face; `sync.sh` defaults to `main` and runs `git push -u origin "$BRANCH"`. Actual execution, external credentials and effective bypass rights of `sync.sh` have **not** been demonstrated.
- The candidate in draft PR #48 removes the direct HF deploy and GitHub Release job, replaces `sync.sh` with an explicit non-writing exit 41, and keeps a fail-closed Guardian placeholder. **It is not merged, not an independent enforcement point, and merging the sync hold would deliberately interrupt existing Replit/Git autosync if used.**
- `eroha-pro/main` reports `protected: true` but no named required status checks in the queried branch response. The queried repository rulesets endpoint returned an empty list; **other protections or effective bypass rights are not fully enumerated**.
- `eroha-trusted-ci-gate/main` reports `protected: false`. Separate repository names, in-repo tests, an Ed25519 lab-generated key or a green CI run do **not** make a trusted root independent.
- Desktop Commander reported `MacBook-Pro-Ermek.local: Offline`. No native R2/G9/G10 acceptance can be concluded from GitHub.
- The PR #48 laboratory audit passed 16 checks twice (standard Python and `-O`) in run 42854803892. The production-no-go job deliberately failed with exit code 41 and independently inspected current `main` workflow source.

## Non-delegable responsibilities

| Principal | Allowed | Must be denied |
| --- | --- | --- |
| Proposer | Suggest changes, prepare artifact and release request, read only approved evidence | Guardian private key, Broker publisher credentials, release/tag publishing, editing trusted verifier or mandatory review policy |
| Guardian owner | Independently review exact action, manage signer identity/policy and one-time signature | Accepting Proposer-supplied trust anchor, unsigned permission, unbound generic owner approval |
| Release Broker owner | Verify independently pinned Guardian public key and immutable artifact evidence, consume nonce, execute approved disposable deployment | Accepting a self-issued or replayed grant; publishing based solely on passing mutable repo CI |
| Independent policy administrator | Own required checks, bypass exceptions, signer pinning and reviewer policy | Allowing the Proposer/admin to replace the gate or grant itself GO |
| Auditor | Independently read signed decision, immutable run/artifact data and deployment/rollback logs | Possessing signer or publisher credentials |

**Identity condition:** assigning a different name, repository or file is NOT enough. Different effective administrators must be proven by rejected write attempts from the Proposer principal and positive authorized access by the independent owner. If the same Proposer can disable protected checks or reissue credentials, stop.

## Eight independently verifiable acceptance milestones

1. **Read-only baseline (R4):** Inventory all effective release/tag/branch/environment rules, bypass actors, GitHub Actions permissions, secrets consumers, Hugging Face deployment routes, `sync.sh` and any Replit invocation/credential context, other CI actors and scheduled jobs. Capture APIs, access limitations, and current commit IDs. Unknown is not a PASS.
2. **External owner appointment (R2/R4):** Record the explicitly approved independent Guardian owner and independent policy/Broker administrators. Verify with separate identities that Proposer cannot edit protected policy, public-key pin, private signer or publishing credentials. No production secrets should be opened for this canary.
3. **Native Guardian identity (R2/G9):** On a connected Mac, verify a trusted signer identity, separate system principal, XPC peer requirements, protected key access and real per-operation user consent. A cancelled authentication stays DENY.
4. **Broker authority isolation (R4):** Provision a separate publisher identity and Broker-controlled destination credential in an approved change window. Verify Proposer has neither the token nor a bypass route, including GitHub Releases, tags, Hugging Face, local `git push` and Replit/autosync credentials. Do not delete or rotate existing credentials before rollback ownership is approved.
5. **Signed single-use authorization (R4/G9):** Verify independently pinned signer, exact repository/commit/run/artifact digest/action/target/policy/TTL/nonce binding and durable replay rejection after process restart. Reject unknown clock, store failure, tampering and missing context.
6. **Native worker/resource envelope (G7/G8/G10):** Verify network policy, hostile XPC peer rejection, crash/restart/concurrency, aggregate CPU/RAM/process caps across Host + XPC + children. Collect kernel/OS observed denials; simulation and process-local limits are insufficient.
7. **Codex/Plus reality check (R3):** Execute an explicitly authorized real operation within actual subscription limits; retain observed quota and fail-closed behavior, without paid API substitution. Do not infer entitlements from subscription marketing.
8. **Disposable release and rollback (R4):** Only after explicit scope-specific owner approval, publish a non-production artifact once using Broker-held credentials. Verify remote digest, provenance, rejected replay/expiry/bypass, induced controlled Broker failure, and actually observed rollback; preserve independently audited evidence.

## Counting and stop conditions

- G1–G6: **24 planned external scenarios**, none industrially accepted on available evidence. G7–G10 have no exhaustive independently validated scenario counts.
- A01–F18: **18 open cases** that overlap G1–G6; do not add them to 24 as distinct tests.
- R2–R4: **three unresolved investigations** overlapping G gates.
- G1–G10: **zero of ten industrial gates accepted**. Unique remaining test count cannot be computed until overlapping cases and G7–G10 test plans are enumerated and owner-approved.
- Always STOP/NO-GO for unverified principals, editable required protection, missing signer proof, replay or malformed authorization, incomplete evidence, process limit failure, unapproved publication, or missing rollback.

## Change order: requires separate explicit approval

1. Obtain the independent owner and authorization to examine/administer specified policy settings. Reading is not permission to change.
2. Create a separately controlled Guardian and Broker in an isolated environment. Verify denial to Proposer first.
3. Approve a production interruption window and documented rollback owner; secure and test a disposable deployment.
4. Apply the integrated no-publish/quarantine candidate to production **only after the owner approves expected service disruption**; never auto-merge PR #48.
5. Migrate exclusive publisher credentials and enforce required independent check protection **only after** external controls are verifiably operational.
6. Replace hardcoded code-owned NO-GO with a separately owned, mandatory, independently evaluated decision. A proposer-owned workflow cannot approve its own promotion.
7. Run the enumerated industrial scenarios and independently sign acceptance. Absent any single proof, keep NO-GO and do not publish.

## Confirmed CI evidence

- PR #48: https://github.com/Eroha68/eroha-pro/pull/48
- GitHub Actions three-channel source inventory and 40 laboratory test executions (20 each under normal Python and `-O`): https://github.com/Eroha68/eroha-pro/actions/runs/42865686253
- Trusted-root laboratory PR #11: https://github.com/Eroha68/eroha-trusted-ci-gate/pull/11

**No production changes, credential changes, branch protection changes, release publication, paid API use or macOS system modifications are authorized or performed by this document.**
