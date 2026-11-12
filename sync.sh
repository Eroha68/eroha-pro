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
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  git stash push -u -m "autosync-stash"
  STASHED=1
fi

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
  if [ "$STASHED" -eq 1 ]; then
    if ! git stash apply 'stash@{0}'; then
      echo "EROHA_R4_STASH_RESTORE_FAILED: stash retained" >&2
      exit 78
    fi
    git stash drop 'stash@{0}'
  fi
  echo "EROHA_R4_SYNC_ABORTED: local changes restored" >&2
  exit 78
fi

# 4) Apply first, drop only after successful restoration.
if [ "$STASHED" -eq 1 ]; then
  git stash apply 'stash@{0}'
  git stash drop 'stash@{0}'
fi

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
