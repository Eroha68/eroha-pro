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
