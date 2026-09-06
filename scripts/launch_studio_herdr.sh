#!/usr/bin/env bash
# scripts/launch_studio_herdr.sh — Lancement automatique des agents du Studio dans Herdr

set -euo pipefail

PROJECT_DIR="/Users/denmac/Assistant_IA/jarvis"
cd "$PROJECT_DIR"

AGENTS=("jarvis" "alba" "tesla" "ray" "cleo")

echo "═══════════════════════════════════════════════════════════════"
echo "🚀 INITIALISATION DU STUDIO HERDR AVEC ALBA"
echo "═══════════════════════════════════════════════════════════════"

for AGENT in "${AGENTS[@]}"; do
    echo "  • Démarrage du profil agent : $AGENT..."
    # Si exécuté via herdr CLI
    if command -v herdr &>/dev/null && [ -n "${HERDR_ENV:-}" ]; then
        herdr agent report "$AGENT" --state idle --message "$AGENT prêt"
    fi
done

echo "✅ Studio configuré. Pour lancer Alba dans ce volet :"
echo "   python run_jarvis.py herdr alba"
