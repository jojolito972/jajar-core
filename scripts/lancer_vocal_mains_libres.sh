#!/usr/bin/env bash
# scripts/lancer_vocal_mains_libres.sh — Lancement direct du mode vocal continu avec Alba ou JAJAR

set -euo pipefail

PROJECT_DIR="/Users/denmac/Assistant_IA/jarvis"
cd "$PROJECT_DIR"

PERSONA="${1:-alba}"

if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON_EXEC="$PROJECT_DIR/venv/bin/python"
else
    PYTHON_EXEC="python3"
fi

echo "🚀 Lancement de la conversation vocale mains libres avec $PERSONA..."
exec "$PYTHON_EXEC" automation/dialogue_vocal_continu.py "$PERSONA"
