#!/usr/bin/env bash
set -euo pipefail

APP_USER="$(id -un)"
TARGET="$HOME/PokerCoach"
STAGE="$HOME/PokerCoach.new"
PREVIOUS="$HOME/PokerCoach.previous"
REPO_URL="https://github.com/iDougOliveira/Douglas.git"
STOPPED=0
SWAPPED=0

if [ "$(id -u)" -eq 0 ]; then
  echo "Execute como douglas, sem sudo antes de bash."
  exit 1
fi
if [ ! -f "$TARGET/pokercoach.env" ] || [ ! -f "$TARGET/app.py" ]; then
  echo "Instalação atual não encontrada em $TARGET"
  exit 1
fi
if [ -e "$PREVIOUS" ]; then
  echo "Pasta de recuperação existente: $PREVIOUS. Nada foi alterado."
  exit 1
fi
for command_name in git python3 curl flock; do
  command -v "$command_name" >/dev/null || { echo "Comando necessário: $command_name"; exit 1; }
done
exec 8>"$HOME/.pokercoach-migration.lock"
flock -n 8 || { echo "Outra migração está em andamento."; exit 1; }

if [ -e "$STAGE" ]; then
  if [ -L "$STAGE" ] || [ ! -d "$STAGE/.git" ] ||
     [ "$(git -C "$STAGE" remote get-url origin)" != "$REPO_URL" ]; then
    echo "A pasta .new não é o clone esperado; preservada sem alterações."
    exit 1
  fi
  # A primeira tentativa alterou apenas permissões dos scripts.
  git -C "$STAGE" config core.filemode false
  if [ -n "$(git -C "$STAGE" status --porcelain --untracked-files=no)" ]; then
    echo "Há edições locais na pasta .new; preservadas sem alterações."
    exit 1
  fi
  git -C "$STAGE" fetch origin main
  git -C "$STAGE" merge --ff-only origin/main
else
  git clone --depth 1 "$REPO_URL" "$STAGE"
  git -C "$STAGE" config core.filemode false
fi

bash -n "$STAGE/auto_update.sh"
python3 -m py_compile "$STAGE/app.py"
EXPECTED_VERSION="$(tr -d '\r\n' < "$STAGE/VERSION")"

recover() {
  local result=$?
  trap - EXIT
  if [ "$result" -ne 0 ] && [ "$STOPPED" -eq 1 ]; then
    echo "Migração interrompida; restaurando instalação anterior."
    sudo systemctl stop pokercoach.service || true
    if [ "$SWAPPED" -eq 1 ]; then
      mv "$TARGET" "$STAGE"
      mv "$PREVIOUS" "$TARGET"
    elif [ -d "$PREVIOUS" ] && [ ! -e "$TARGET" ]; then
      mv "$PREVIOUS" "$TARGET"
    fi
    sudo systemctl start pokercoach.service || true
  fi
  exit "$result"
}
trap recover EXIT
sudo -v
sudo systemctl stop pokercoach.service
STOPPED=1
# Copiar SQLite somente com o serviço parado, incluindo eventuais WAL/SHM.
cp "$TARGET/pokercoach.env" "$STAGE/pokercoach.env"
chmod 600 "$STAGE/pokercoach.env"
mkdir -p "$STAGE/data"
if [ -d "$TARGET/data" ]; then
  cp -a "$TARGET/data/." "$STAGE/data/"
fi
mv "$TARGET" "$PREVIOUS"
mv "$STAGE" "$TARGET"
SWAPPED=1
sudo systemctl start pokercoach.service

READY=0
for attempt in {1..20}; do
  if HEALTH="$(curl --fail --silent --connect-timeout 1 --max-time 2 http://127.0.0.1:8765/api/health)" &&
     python3 -c 'import json,sys; r=json.loads(sys.argv[1]); sys.exit(not (r.get("status")=="ok" and r.get("version")==sys.argv[2]))' "$HEALTH" "$EXPECTED_VERSION"; then
    READY=1
    break
  fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then
  echo "A versão esperada não respondeu no prazo."
  sudo journalctl -u pokercoach.service -n 30 --no-pager
  exit 1
fi
STOPPED=0
printf '%s\n' "$HEALTH"

# Migração confirmada: Git é o histórico; não manter cópia duplicada.
if [ -d "$PREVIOUS" ]; then
  rm -rf "$PREVIOUS"
fi

sudo tee /etc/systemd/system/pokercoach-update.service >/dev/null <<EOF
[Unit]
Description=Atualização do PokerCoach
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
Environment=POKERCOACH_USER=$APP_USER
ExecStart=/bin/bash $TARGET/auto_update.sh
EOF

sudo tee /etc/systemd/system/pokercoach-update.timer >/dev/null <<EOF
[Unit]
Description=Verificar atualizações do PokerCoach

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now pokercoach-update.timer
echo "Migração concluída. Versão: $EXPECTED_VERSION"
echo "Senha e histórico preservados. Atualização automática ativada."
echo "Instalação consolidada em $TARGET; cópia temporária removida após health check."
