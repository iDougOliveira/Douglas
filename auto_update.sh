#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_USER="${POKERCOACH_USER:-douglas}"
BRANCH="${POKERCOACH_BRANCH:-main}"
LOCK_FILE="/run/pokercoach-update.lock"

if [ "$(id -u)" -ne 0 ]; then
  exec sudo env POKERCOACH_USER="$APP_USER" POKERCOACH_BRANCH="$BRANCH" bash "$APP_DIR/auto_update.sh"
fi

exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

git_as_user() {
  runuser -u "$APP_USER" -- git -C "$APP_DIR" "$@"
}

git_as_user fetch --quiet origin "$BRANCH"
LOCAL_COMMIT="$(git_as_user rev-parse HEAD)"
REMOTE_COMMIT="$(git_as_user rev-parse "origin/$BRANCH")"

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
  echo "PokerCoach já está atualizado: ${LOCAL_COMMIT:0:8}"
  exit 0
fi

echo "Atualizando PokerCoach: ${LOCAL_COMMIT:0:8} -> ${REMOTE_COMMIT:0:8}"
git_as_user merge --ff-only "origin/$BRANCH"

if ! runuser -u "$APP_USER" -- python3 -m py_compile "$APP_DIR/app.py" "$APP_DIR/strategy.py" "$APP_DIR/make_password.py"; then
  echo "Validação Python falhou; restaurando versão anterior."
  git_as_user reset --hard "$LOCAL_COMMIT"
  exit 1
fi

if command -v node >/dev/null 2>&1; then
  if ! runuser -u "$APP_USER" -- node --check "$APP_DIR/static/app.js"; then
    echo "Validação JavaScript falhou; restaurando versão anterior."
    git_as_user reset --hard "$LOCAL_COMMIT"
    exit 1
  fi
fi

systemctl restart pokercoach.service
for _ in 1 2 3 4 5; do
  if curl --fail --silent http://127.0.0.1:8765/api/health >/dev/null; then
    echo "PokerCoach atualizado com sucesso para ${REMOTE_COMMIT:0:8}."
    exit 0
  fi
  sleep 2
done

echo "Health check falhou; executando rollback."
git_as_user reset --hard "$LOCAL_COMMIT"
systemctl restart pokercoach.service
exit 1
