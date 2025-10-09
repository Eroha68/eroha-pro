#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-main}"

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
git fetch origin "$BRANCH" || true
git checkout -B "$BRANCH"
git pull --rebase origin "$BRANCH" || true

# 4) Вернём stash, если он был
if [ "$STASHED" -eq 1 ]; then
  git stash pop || true
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
