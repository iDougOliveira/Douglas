#!/usr/bin/env bash
set -euo pipefail

APP_USER="$(id -un)"
USER_HOME="$HOME"
TARGET="$USER_HOME/PokerCoach"
STAGE="$USER_HOME/PokerCoach.new"
PREVIOUS="$USER_HOME/PokerCoach.previous"
REPO_URL="https://github.com/iDougOliveira/Douglas.git"

if [ ! -f "$TARGET/pokercoach.env" ]; then
  echo "Instalação atual não encontrada em $TARGET"
  exit 1
fi
if [ -e "$STAGE" ] || [ -e "$PREVIOUS" ]; then
  echo "Há uma migração incompleta. Remova PokerCoach.new/PokerCoach.previous após verificar o conteúdo."
  exit 1
fi
command -v git >/dev/null || { echo "Git não instalado. Execute: sudo apt install git"; exit 1; }

git clone --depth 1 "$REPO_URL" "$STAGE"
cp "$TARGET/pokercoach.env" "$STAGE/pokercoach.env"
mkdir -p "$STAGE/data"
if [ -d "$TARGET/data" ]; then
  cp -a "$TARGET/data/." "$STAGE/data/"
fi
chmod 600 "$STAGE/pokercoach.env"
chmod +x "$STAGE/install.sh" "$STAGE/update.sh" "$STAGE/auto_update.sh" "$STAGE/make_password.py"

sudo systemctl stop pokercoach.service
mv "$TARGET" "$PREVIOUS"
mv "$STAGE" "$TARGET"
sudo systemctl start pokercoach.service

if ! curl --fail --silent --retry 5 --retry-delay 2 http://127.0.0.1:8765/api/health; then
  echo
  echo "Nova versão falhou. Restaurando a instalação anterior."
  sudo systemctl stop pokercoach.service
  mv "$TARGET" "$STAGE"
  mv "$PREVIOUS" "$TARGET"
  sudo systemctl start pokercoach.service
  exit 1
fi
echo

sudo tee /etc/systemd/system/pokercoach-update.service >/dev/null <<EOF
[Unit]
Description=Atualização segura do PokerCoach
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
Environment=POKERCOACH_USER=$APP_USER
ExecStart=$TARGET/auto_update.sh
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
mv "$PREVIOUS" "/tmp/PokerCoach.previous.$(date +%s)"

echo "PokerCoach migrado para GitHub e atualização automática ativada."
echo "Versão instalada: $(cat "$TARGET/VERSION")"

