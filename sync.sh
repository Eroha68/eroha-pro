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

# 2) Сохраним незакоммиченные правки во временный stash (если есть)
STASHED=0
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  git stash push -u -m "autosync-stash" >/dev/null 2>&1 || true
  STASHED=1
fi

# 3) Подтянем изменения с origin и аккуратно примем их через rebase
git fetch origin "$BRANCH"
git checkout -B "$BRANCH"
git pull --rebase origin "$BRANCH"

# 4) Вернём stash, если он был
if [ "$STASHED" -eq 1 ]; then
  git stash pop
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
