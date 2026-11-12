# R4 — DRAFT ONLY: direct publication cutover proposal

Research branch `research/r4-broker-only-cutover-20261112`. **Do not merge without approved maintenance window, designated independent Guardian/Broker owners and migration of production deployment credentials.**

## Exact proposed effects on merge
- `.github/workflows/eroha_core_ci.yml`: keep validate/build jobs; set `contents: read`; **remove** the legacy tag+GitHub-release job and its write-token code. NO new release route.
- `.github/workflows/deploy.yml`: replace legacy Hugging Face deploy with an **explicitly failing** NO-GO job (exit 78) on matching main pushes, not a skipped/green job; remove all direct HF token and push commands and previous deployment notifications. NO new deploy route. This deliberately makes the old deploy workflow RED until an approved Broker replaces it.
- `sync.sh`: refuse direct pushes to main, master, release/* and tag-like names; ordinary branch pushes still require existing GitHub rights. Existing default invocation `./sync.sh` will now refuse because the default branch is main.

**Expected business impact if merged:** automated GitHub releases and Hugging Face deployments stop; default sync fails deliberately. This PR must remain draft until an independently owned Broker is operational and the operator has accepted that downtime. It does not revoke any token, remove repository admin, prevent all alternate GitHub API / release routes or prove industrial isolation.

## Approval/verification before merge
1. Confirm all actual active publishing paths and notification dependencies with operators; inventory token names/scopes but never reveal values.
2. Establish external Guardian authority and separately owned Broker credentials; ensure Proposer cannot edit policy, approvals, code, tokens or environment controls.
3. Prove live service-side denials to direct GitHub/HF publication by a *non-admin* Proposer test identity in a safe, disposable target.
4. Demonstrate independent Broker-only authorized release, post-release witness and safe P1 rollback on a disposable resource.
5. Freeze and sign a rollback plan for reverting each of these changes if the maintenance window fails. Note: reverting code does not by itself restore revoked secrets.
6. Only after those prerequisites, operator approves merge and production activation.

**Current acceptance:** LAB CLOSED WITH RESTRICTIONS; R4 OPEN / P1 OPEN / independent custody NOT PROVEN; industrial NO-GO.

## Isolated safety correction and evidence (2026-11-12)
- Source commit `ba4e604ca0a5ee4c44a9b17c05b51f7990135b60` updates `sync.sh`: branch preflight, `fetch` before `stash`, no `checkout -B`, `stash apply` before `stash drop`.
- MacBook-Pro-Ermek.local (Desktop Commander Remote 0.3.2) ran `bash -n`: exit 0.
- A disposable local Git repository under a freshly created temporary directory tested a deliberately missing local `origin`: script exited with an error, the tracked unsaved modification remained, and no stash entry was made. Evidence marker: `R4_FETCH_FAILURE_LOCAL_CHANGE_PRESERVED=PASS`.
- The same disposable repository tested passing `main` to the script; the preflight rejected it with exit status 78. Evidence marker: `R4_PROTECTED_REF_REJECTED_BEFORE_MUTATION=PASS`.
- Temporary test directory removed by shell EXIT cleanup. No network publication, real tokens, working `main`, or user repository content was used.
- **Not verified:** a successful end-to-end push, failure during rebase with a stash present, partial conflict during `stash apply`, every alias or permission-based bypass, industrial role independence, or destructive rollback P1. Keep draft/NO-GO.

## Targeted rebase-conflict correction — 2026-11-12
- Commit `dca82ca2c9e47a3b572fd89c72744fadb1e49f6d` changes only the research-branch `sync.sh`. An actual `git pull --rebase` conflict formerly left a rebase in progress and stashed user edits unavailable in the working tree.
- The patched script detects a failed pull, aborts the active rebase, attempts `stash apply` before `stash drop`, and returns explicit status 78. If abort/apply fails it leaves the stash intact and exits; no automatic publication is attempted.
- One targeted disposable Git test used a local bare remote, two divergent commits touching the same tracked file, and an unsaved local file. No actual network service, publication identity, or private repo data was accessed.
- Exact test markers from MacBook (Desktop Commander Remote): `R4_REBASE_FAILURE_EXPLICIT_EXIT=PASS`; `R4_REBASE_FAILURE_LOCAL_EDIT_RESTORED=PASS`; `R4_REBASE_FAILURE_STASH_RESTORED_AND_CLEARED=PASS`; `R4_REBASE_FAILURE_REBASE_ABORTED=PASS`; `R4_REBASE_FAILURE_LOCAL_COMMIT_PRESERVED=PASS`. `bash -n` also succeeded.
- **Limit:** this validates only the simulated conflict on a local disposable Git repository. Other fetch/push errors, concurrent changes to the stash list, production publication, independent privilege custody, and P1 are not certified.

## Verified concurrent stash overwrite defect — 2026-11-12
- Reproduced before fix with an isolated local bare Git remote and a test-only `git` command shim that inserts a competing stash entry just before `pull`. Old `sync.sh` exited 0, restored the **wrong** stash (`BASELINE_WRONG_STASH_APPLIED=YES`) and did not restore the saved user edit (`BASELINE_CORRECT_EDIT_RESTORED=NO`).
- Draft-only source fix `9d3b056e0c27f64bbcdf4d249a974c79940f76f1` captures the immutable Git stash commit SHA immediately after creating the stash and applies **that exact SHA**, not `stash@{0}`. If the stash top has changed, it restores the captured user edits but refuses automated commit/push and retains backups (exit 78).
- On `MacBook-Pro-Ermek.local` the same isolated interference produced `R4_CONCURRENT_STASH_REJECTED=PASS`, `R4_OWN_STASH_RESTORED=PASS`, `R4_FOREIGN_STASH_NOT_APPLIED=PASS`, `R4_RECOVERY_STASH_BACKUPS_RETAINED=PASS`, `R4_CONCURRENT_STASH_NO_AUTOCOMMIT=PASS`. `bash -n`: PASS.
- Positive-path regression used only a local bare remote: `R4_NORMAL_STASH_RESTORED=PASS`, `R4_NORMAL_STASH_CLEARED=PASS`, `R4_NORMAL_LOCAL_REMOTE_PUSH=PASS`.
- The test fixtures were created in temporary directories with cleanup traps; no production endpoint, credential, real repository working tree, `main` or external publish channel was touched.
- Scope: reproducible tests establish only these specific interference and normal cases. An adversary concurrently mutating `refs/stash` *after the top check and before the drop* remains outside this proof; script-level checks are not independent Broker/GitHub permission enforcement. Industrial R2/P1/R4 and G1–G10 remain **NO-GO**.

## Reproduced indexed-stash deletion race and fail-closed correction — 2026-11-12
- **Baseline defect:** in a disposable local bare Git repository a test-only `git` shim inserted an unrelated entry immediately before `git stash drop 'stash@{0}'`. Pre-fix script exited **0**, and the injected unrelated stash was removed: `BASELINE_WRONG_STASH_DROP=YES`, `BASELINE_EXIT=0`.
- **Research-only fix:** source commit `c349ae6b735ce15a73b8a355e8c3f604558e2c00` removes the indexed `git stash drop` call entirely. The script still applies its exact saved stash commit OID, but intentionally **retains** backups for separate, human-reviewed cleanup. This sacrifices automatic stash garbage collection in favor of preservation of unrelated user data.
- **Isolated retest on MacBook:** `R4_BASH_SYNTAX=PASS`, `R4_LOCAL_EDITS_RESTORED=PASS`, `R4_STASHES_NOT_DELETED=PASS`, `R4_NO_DESTRUCTIVE_DROP=PASS`, `R4_LOCAL_BARE_REMOTE_PUSH=PASS`. The interfering test shim could no longer execute the targeted drop because the script never invoked it.
- **Scope and limit:** this proves removal of this specific destructive indexed-drop path and a narrow positive local publish flow. It does NOT provide full concurrency locking against other processes changing the working tree or refs, nor verify remote GitHub/Hugging Face rights, independent Guardian/Broker control or P1. Any future automatic cleanup must prove identity-bound deletion with separate owner authorization; retain **NO-GO** for production.
