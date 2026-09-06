#!/bin/bash
# ==============================================================================
# lancer_studio_herdr.sh — Lancement Natif Herdr (Sans tmux)
# ==============================================================================
PROJ_DIR="/Users/denmac/Assistant_IA/jarvis"
cd "$PROJ_DIR" || exit 1

if [ -f "$PROJ_DIR/venv/bin/activate" ]; then
    PYTHON_EXE="$PROJ_DIR/venv/bin/python"
else
    PYTHON_EXE="python3"
fi

echo "🚀 Démarrage des agents du Studio JAJAR pour Herdr (Mode Natif)..."

# Arrêt des instances précédentes si présentes
pkill -f "run_jarvis.py herdr"

# Lancement de chaque agent en arrière-plan avec variables d'environnement Herdr
export HERDR_ENV=1

$PYTHON_EXE run_jarvis.py herdr jarvis > /dev/null 2>&1 &
$PYTHON_EXE run_jarvis.py herdr tesla > /dev/null 2>&1 &
$PYTHON_EXE run_jarvis.py herdr ansel > /dev/null 2>&1 &
$PYTHON_EXE run_jarvis.py herdr alfred > /dev/null 2>&1 &
$PYTHON_EXE run_jarvis.py herdr ray > /dev/null 2>&1 &
$PYTHON_EXE run_jarvis.py herdr cleo > /dev/null 2>&1 &
$PYTHON_EXE run_jarvis.py herdr leo > /dev/null 2>&1 &
$PYTHON_EXE run_jarvis.py herdr franklin > /dev/null 2>&1 &
$PYTHON_EXE run_jarvis.py herdr indiana > /dev/null 2>&1 &
$PYTHON_EXE run_jarvis.py herdr alba > /dev/null 2>&1 &
$PYTHON_EXE tools/jarvis_telegram_hub.py > /dev/null 2>&1 &

echo "✅ Tous les 10 agents et le pont Herdr sont actifs en arrière-plan."
echo "🌐 Ouvrez votre interface graphique Herdr pour interagir avec eux directement dans la barre latérale."
