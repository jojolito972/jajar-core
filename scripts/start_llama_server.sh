#!/bin/bash
# Lance le serveur llama.cpp exposant une API compatible OpenAI sur http://localhost:8080/v1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../.env" ]; then
    set -a
    source "$SCRIPT_DIR/../.env"
    set +a
fi

MODEL_PATH="${JARVIS_MODEL_PATH:-$HOME/Assistant_IA/modeles/gemma-4-12b-it-UD-Q4_K_XL.gguf}"
MMPROJ_PATH="${JARVIS_MMPROJ_PATH:-$HOME/Assistant_IA/modeles/mmproj-F16.gguf}"

# Par défaut : Mode Turbo (Vision Désactivée pour vitesse d'inférence maximale).
# Passe USE_VISION=1 si tu veux charger le module multimédia.
USE_VISION="${USE_VISION:-0}"

if [ ! -f "$MODEL_PATH" ]; then
    echo "❌ Modèle introuvable : $MODEL_PATH"
    exit 1
fi

MMPROJ_ARGS=()
if [ "$USE_VISION" = "1" ] && [ -f "$MMPROJ_PATH" ]; then
    echo "👁️  Mode Vision ACTIVÉ ($MMPROJ_PATH)"
    MMPROJ_ARGS=(--mmproj "$MMPROJ_PATH")
else
    echo "⚡ Mode Turbo Texte/Code ACTIVÉ (Vision désactivée pour vitesse maximale)"
fi

if [ -f "$SCRIPT_DIR/llama-server" ]; then
    LLAMA_BIN="$SCRIPT_DIR/llama-server"
else
    LLAMA_BIN="llama-server"
fi

echo "🚀 Démarrage du serveur local sur http://localhost:8080 avec $MODEL_PATH"

$LLAMA_BIN \
    --model "$MODEL_PATH" \
    "${MMPROJ_ARGS[@]}" \
    --host 127.0.0.1 \
    --port 8080 \
    -c 8192 \
    --n-gpu-layers 99 \
    --parallel 1 \
    --flash-attn on \
    --context-shift \
    --jinja \
    --reasoning off \
    --threads 6
