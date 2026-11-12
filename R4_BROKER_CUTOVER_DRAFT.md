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
