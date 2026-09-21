#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$APP_DIR/data"
ENV_FILE="$APP_DIR/pokercoach.env"
SERVICE_FILE="/etc/systemd/system/pokercoach.service"
mkdir -p "$DATA_DIR"
read -rsp "Defina a senha do painel: " PC_PASSWORD; echo
if [ ${#PC_PASSWORD} -lt 8 ]; then echo "Use no mínimo 8 caracteres."; exit 1; fi
HASH_LINE="$(python3 "$APP_DIR/make_password.py" "$PC_PASSWORD")"
SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
umask 077
printf 'POKERCOACH_PASSWORD_HASH=%s\nPOKERCOACH_SESSION_SECRET=%s\nPOKERCOACH_HOST=0.0.0.0\nPOKERCOACH_PORT=8765\n' "$HASH_LINE" "$SECRET" > "$ENV_FILE"
sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=PokerCoach Local
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=/usr/bin/python3 $APP_DIR/app.py
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now pokercoach.service
echo "Pronto. Abra http://$(hostname -I | awk '{print $1}'):8765"

