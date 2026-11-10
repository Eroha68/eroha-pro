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

## 2026-11-11 — verified independent-ownership blocker (read-only audit)

GitHub connector checks of the current repository state:
- `Eroha68/eroha-pro`: user `Eroha68` has **admin** permission; `main` is `protected: true`; protection-details API returned **403 Resource not accessible by integration**; repository rulesets API returned `[]`. These results do **not** reveal all effective branch exceptions or enterprise policies.
- `Eroha68/eroha-trusted-ci-gate`: user `Eroha68` also has **admin** permission; `main` is `protected: false`; rulesets API returned **403** with a feature/plan limitation.
- Draft PR #48 remained unmerged at commit `b7e8b7ef974fbb73496c64fa9152c47677fa4171` when checked.
- The same GitHub administrative identity spans both repositories. **Independent trust-root custody is not established**. Existing synthetically signed grants, repository separation and passing CI cannot satisfy R2/R4.

**Decision:** FAIL for the demonstrated independent-administrator separation criterion; NO-GO for any industrial release. Do not infer actual compromise. No settings, roles or publishing credentials were changed.

### Independent acceptance evidence: exact tests and their prerequisites

| ID | Scenario / pass condition | Evidence owner | Status |
| --- | --- | --- | --- |
| I01 | Independent administrator selected and their scope explicitly approved | Human owner | NOT TESTED |
| I02 | Proposer attempts to edit protected policy and is denied by GitHub/API | Independent administrator | NOT TESTED |
| I03 | Proposer attempts to modify Guardian trust-anchor and signer and is denied | Guardian owner | NOT TESTED |
| I04 | Independent Guardian owner can authorize exact non-production request | Guardian owner | NOT TESTED |
| I05 | Proposer attempts to obtain Broker publisher token and is denied, without disclosing secrets | Broker owner | NOT TESTED |
| I06 | Proposer cannot publish a GitHub Release, push tags or deploy to HF outside Broker | Independent auditor | NOT TESTED |
| I07 | All required status checks and bypass actors are independently inventoried; exceptions verified | Policy administrator | BLOCKED: GitHub protection API 403 |
| I08 | Signed grant binds exact repo, commit, artifact SHA-256, run, target, action, policy, nonce and expiry | Guardian + Broker owners | NOT TESTED |
| I09 | Tampered/expired/replayed grants are rejected after Broker restart and concurrent requests | Broker owner | NOT TESTED |
| I10 | Real per-operation macOS user consent is verified; cancellation denies | Native Mac owner | NOT TESTED |
| I11 | Unauthorized XPC peer is rejected by signed peer identity | Native Mac owner | NOT TESTED |
| I12 | Kernel-enforced aggregate CPU/RAM/process/network budget holds across children and restarts | Native Mac owner | NOT TESTED |
| I13 | An explicitly scoped disposable deployment uses only Broker-held credentials | Broker owner | NOT TESTED |
| I14 | Remote deployed digest matches signed artifact and independently retained provenance | Independent auditor | NOT TESTED |
| I15 | Controlled failure triggers tested rollback; remote state and log evidence verified | Broker + auditor | NOT TESTED |
| I16 | Real user-plan execution and limits are observed without inferring API/Plus entitlements | Subscription owner | NOT TESTED |

These **16 proposed evidence checkpoints are not an exhaustive G7–G10 test plan**. They overlap G1–G6 and R2–R4 and MUST NOT be added numerically to the existing 24 scenarios or 18 A01–F18 items. Conclusive unique-test counting requires a jointly approved ID-to-gate coverage matrix.

**Immediate stop conditions:** do not appoint a second identity by merely renaming an account, do not loosen branch protections to demonstrate a bypass, do not rotate or inspect secret values, do not enable publishing, and do not merge release-hold changes without approved interruption and rollback ownership. In the absence of independently observed I01–I07, remain NO-GO.

## 2026-11-11 — release authorization dependency audit: two distinct approvals required

**Verified candidate source:** `.github/workflows/eroha_core_ci.yml` has `build-archive.needs = [validate-core, powershell-check, eligibility, guardian-authorization]` and requires a successful Guardian result. The Guardian currently returns `exit 41` without signing. The build job would calculate `archive_sha256` **only after** it runs. A single pre-build authorization cannot include the digest of an artifact that does not yet exist.

**Architecture defect (transition design, not current quarantine):** treating a pre-build manifest approval as a final release grant would authorize a not-yet-observed artifact. Requiring a final artifact digest before building it creates an ordering deadlock. Never weaken the intentional NO-GO just to make the pipeline green.

### Proposed two-stage authorization protocol (NOT IMPLEMENTED)

1. **Independent pre-build approval (A):** The independent Guardian/policy owner authorizes the exact repository, immutable commit, approved manifest digest, policy version, build action, target staging namespace, TTL and unique request ID. This is permission to **build a non-publishable candidate**, not to release it. The proposer must not choose or replace the Guardian trust anchor. Without A, stop before building.
2. **Isolated candidate build (B):** A read-only, least-privilege runner verifies A from an independently managed trust root, fetches the exact Git commit, validates the separately approved exact-file manifest, builds the deterministic archive, computes the archive SHA-256, and stores the candidate in non-public staging with immutable run/provenance IDs. No GitHub Release/tag/HF credentials or publication network route is available to B.
3. **Independent final approval (C):** The Guardian verifies B's independently trusted provenance and signs the **actual artifact digest**, plus exact repository/commit/run/action/target, trusted policy version, expiry and one-time nonce. An approval of manifest bytes or a passed mutable repository check is **not** C.
4. **Broker-only publication (D):** An independently administered Broker, holding the **sole target publishing credential**, validates C against an externally pinned signer and independent policy; verifies the fetched artifact digest and provenance, checks expiry and a persistent atomic single-use nonce, then publishes only the specified immutable bytes. A crash/retry must not double-publish.
5. **Audit and rollback (E):** An independent auditor verifies external artifact digest and remote state, requested target, decision provenance, denied replay and bypass routes, then exercises explicitly approved disposable rollback. Without an observed remote rollback, no industrial acceptance.

### Mandatory transition invariants

- A `manifest-sha256` value supplied by the same workflow author is integrity metadata, **not independent authority**.
- The pre-build grant cannot be reused as the final publishing grant; separate `action` values, purpose-bound signatures and nonce domains are required.
- B must not hold or inherit publisher secrets; C's signature must commit to B's actual bytes and run identity.
- The Broker must verify C **after** B, independently of the proposer-controlled workflow; branch protection alone is not a Broker.
- No test key generated by the proposer, same-admin second repository, in-repo required check or synthetic CI approval establishes separation.
- Neither a switch to green CI nor automatic acceptance of a reviewer is an authorized migration step.

### Dependency checks that must precede industrial GO

| Control | Evidence needed | Current verdict |
| --- | --- | --- |
| T01 | Proposer denied changes to independently owned Guardian signer and policy | NOT TESTED; current same-admin ownership blocks proof |
| T02 | Invalid/missing/expired pre-build grant stops B before candidate creation | NOT TESTED |
| T03 | Candidate B executes without publishing credentials, outputs verified digest/provenance | NOT TESTED |
| T04 | Final grant cannot predate/omit/alter actual archive digest and run ID | NOT TESTED |
| T05 | Broker refuses A as publication grant and rejects missing/forged C | NOT TESTED |
| T06 | Broker atomic replay check holds across crash, retry and concurrency | NOT TESTED |
| T07 | Proposer denied all direct releases, tag pushes and HF/local/other deployment paths | NOT TESTED |
| T08 | A single disposable publish and independently verified rollback complete | NOT TESTED |

T01–T08 are a **dependency crosswalk**, not eight new independent tests to add to G1–G10 or I01–I16. Map them to I01–I16 and R2–R4 before unique counting.

**Immediate safe implementation posture:** Keep `guardian-authorization` at `exit 41`, keep `build-archive` blocked and DO NOT merge this research PR. A later authorized implementation should replace the single hardcoded Guardian gate with separately owned A and C trust checks; no current code author may self-approve an external trust root or enable publishing. A real isolated build only follows verified ownership and approval, not this document alone.

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
