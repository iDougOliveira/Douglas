#!/usr/bin/env bash
set -euo pipefail
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${1:-$HOME/PokerCoach}"

if [ ! -f "$TARGET_DIR/pokercoach.env" ] || [ ! -f "$TARGET_DIR/app.py" ]; then
  echo "Instalação existente não encontrada em $TARGET_DIR"
  exit 1
fi

mkdir -p "$TARGET_DIR/static"
cp "$SOURCE_DIR/app.py" "$TARGET_DIR/app.py"
cp "$SOURCE_DIR/strategy.py" "$TARGET_DIR/strategy.py"
cp "$SOURCE_DIR/VERSION" "$TARGET_DIR/VERSION"
cp "$SOURCE_DIR/make_password.py" "$TARGET_DIR/make_password.py"
cp "$SOURCE_DIR/install.sh" "$TARGET_DIR/install.sh"
cp "$SOURCE_DIR/test_app.py" "$TARGET_DIR/test_app.py"
cp "$SOURCE_DIR/test_strategy.py" "$TARGET_DIR/test_strategy.py"
cp "$SOURCE_DIR/README.md" "$TARGET_DIR/README.md"
cp "$SOURCE_DIR/static/index.html" "$TARGET_DIR/static/index.html"
cp "$SOURCE_DIR/static/app.js" "$TARGET_DIR/static/app.js"
cp "$SOURCE_DIR/static/style.css" "$TARGET_DIR/static/style.css"
cp "$SOURCE_DIR/static/positions.json" "$TARGET_DIR/static/positions.json"
chmod +x "$TARGET_DIR/install.sh" "$TARGET_DIR/make_password.py"

sudo systemctl restart pokercoach.service
sleep 1
curl --fail --silent http://127.0.0.1:8765/api/health
echo
echo "PokerCoach atualizado. Banco de dados e senha foram preservados."
