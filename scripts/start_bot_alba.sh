#!/usr/bin/env bash
# scripts/start_bot_alba.sh — Lanceur d'Atelier pour Madame Laura Puntillo & Alba

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

# 1. Nettoyage préventif des processus résiduels
echo "🧹 Nettoyage des anciennes instances..."
pkill -f "bot_laura_puntillo.py" 2>/dev/null || true
sleep 0.5

# 2. Détection et activation du venv Python
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
    PYTHON_EXEC="$SCRIPT_DIR/venv/bin/python"
else
    PYTHON_EXEC="python3"
fi

# 3. Lancement du Bot et du Serveur Mains Libres (Port 8765)
echo "🚀 Démarrage du Studio Atelier..."
exec "$PYTHON_EXEC" automation/bot_laura_puntillo.py
