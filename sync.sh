#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-main}"

# Research R4: an ordinary source branch only, never a full ref or release target.
# Reject before stash, checkout, fetch, commit, or push can mutate local state.
case "$BRANCH" in
  main|master|release|release/*|refs/*|tags/*|v[0-9]*)
    echo "EROHA_R4_REFUSE_PROTECTED_PUSH: $BRANCH (Broker authorization required)" >&2
    exit 78
    ;;
esac

# Git's native validation rejects option-like names, malformed branch refs,
# control characters, revspecs and invalid separators before any side effect.
if ! git check-ref-format --branch "$BRANCH" >/dev/null 2>&1; then
  echo "EROHA_R4_REFUSE_INVALID_BRANCH" >&2
  exit 78
fi

# 1) Убедимся, что git знает имя и email (иначе GitHub отвергнет коммит)
if ! git config user.email >/dev/null; then
  git config user.email "autosync@replit.local"
fi
if ! git config user.name >/dev/null; then
  git config user.name "Replit Auto Sync"
fi

# 2) Безопасный preflight: работать только с текущей веткой.
# Не менять указатель другой ветки через checkout -B.
CURRENT_BRANCH="$(git symbolic-ref --quiet --short HEAD)" || {
  echo "EROHA_R4_REFUSE_DETACHED_HEAD" >&2
  exit 78
}
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
  echo "EROHA_R4_REFUSE_BRANCH_SWITCH: checked out $CURRENT_BRANCH" >&2
  exit 78
fi

# Сначала выполнить fetch: при ошибке локальные изменения ещё не спрятаны.
git fetch origin "$BRANCH"

# 3) Временное сохранение изменений. Ошибки stash нельзя игнорировать.
STASHED=0
STASH_OID=""
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  git stash push -u -m "autosync-stash"
  STASHED=1
  # Resolve our immutable stash commit immediately; never restore by moving index.
  STASH_OID="$(git rev-parse --verify 'refs/stash^{commit}')" || exit 78
fi

restore_own_stash() {
  [ "$STASHED" -eq 1 ] || return 0
  if ! git stash apply "$STASH_OID"; then
    echo "EROHA_R4_STASH_RESTORE_FAILED: original stash retained" >&2
    return 78
  fi
  # A competing process may have pushed a new stash during fetch/rebase.
  # Never drop or publish when the stash stack was changed by another actor.
  if [ "$(git rev-parse -q --verify refs/stash)" != "$STASH_OID" ]; then
    echo "EROHA_R4_CONCURRENT_STASH_CHANGE: edits restored, backup retained; no push" >&2
    return 78
  fi
  # Never delete a stash by mutable stack index. A second Git process can
  # push a different entry between the top check and "stash drop".
  # Retain our immutable backup for explicit owner-reviewed cleanup.
  echo "EROHA_R4_STASH_BACKUP_RETAINED: $STASH_OID" >&2
}

# Rebase may conflict after temporarily saving local edits. On failure,
# abort the in-progress rebase first, and only then restore the local stash.
# If abort/restoration fails, leave the stash intact and report a hard error.
if ! git pull --rebase origin "$BRANCH"; then
  echo "EROHA_R4_REBASE_FAILED: attempting safe recovery" >&2
  REBASE_MERGE="$(git rev-parse --git-path rebase-merge)"
  REBASE_APPLY="$(git rev-parse --git-path rebase-apply)"
  if [ -d "$REBASE_MERGE" ] || [ -d "$REBASE_APPLY" ]; then
    if ! git rebase --abort; then
      echo "EROHA_R4_REBASE_ABORT_FAILED: stash retained" >&2
      exit 78
    fi
  fi
  restore_own_stash || exit 78
  echo "EROHA_R4_SYNC_ABORTED: local changes restored" >&2
  exit 78
fi

# 4) Apply the exact stash commit and preserve its backup; no indexed deletion.
restore_own_stash || exit 78

# 5) Проверим, есть ли реальные изменения
CHANGED="$(git status --porcelain)"
if [ -z "$CHANGED" ]; then
  echo "No changes to commit. Nothing to push ✅"
  exit 0
fi

# 6) Сформируем вменяемое сообщение коммита: дата + до 5 имён файлов
git add -A
DATE="$(date '+%Y-%m-%d %H:%M')"
FILES="$(echo "$CHANGED" | awk '{print $2}' | head -5 | tr '\n' ' ')"
COUNT="$(echo "$CHANGED" | wc -l | xargs)"
if [ "$COUNT" -gt 5 ]; then
  FILES="$FILES …(+ $((COUNT-5)) more)"
fi
MSG="Auto-sync $DATE — $FILES"

# 7) Коммит и пуш
git commit -m "$MSG" || { echo "Nothing to commit after all"; exit 0; }
git push -u origin "$BRANCH"

echo "Pushed: $MSG ✅"
