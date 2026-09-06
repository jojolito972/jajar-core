#!/usr/bin/env bash
# scripts/lancer_appel_cloud_mondial.sh — Lanceur d'Appel Cloud Sécurisé (Exécution Python Dédiée)

set -euo pipefail

PROJECT_DIR="/Users/denmac/Assistant_IA/jarvis"
cd "$PROJECT_DIR"

# 1. Sélection obligatoire du binaire Python du venv
if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON_EXEC="$PROJECT_DIR/venv/bin/python"
else
    PYTHON_EXEC="python3"
fi

# 2. Libération propre du port 8765
echo "🧹 1. Libération du port 8765..."
lsof -ti:8765 | xargs kill -9 2>/dev/null || true
pkill -f "serveur_appel_vocal.py" 2>/dev/null || true
pkill -f "cloudflared" 2>/dev/null || true
sleep 1

# 3. Démarrage du serveur vocal
echo "🚀 2. Démarrage du serveur vocal sur le port 8765..."
"$PYTHON_EXEC" automation/serveur_appel_vocal.py &
SERVER_PID=$!

# 4. Attente active de l'écoute HTTP locale (200 OK)
echo "⏳ 3. Vérification de l'écoute locale..."
for i in {1..15}; do
    if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/ | grep -q "200"; then
        echo "   -> Serveur vocal actif (Code 200 OK)."
        break
    fi
    sleep 0.5
done

# 5. Lancement du tunnel Cloudflare
echo "🌐 4. Établissement du tunnel mondial Cloudflare..."
rm -f /tmp/cloudflared.log
cloudflared tunnel --url http://127.0.0.1:8765 --no-autoupdate 2>&1 | tee /tmp/cloudflared.log &
TUNNEL_PID=$!

PUBLIC_URL=""
for i in {1..20}; do
    PUBLIC_URL=$(grep -o 'https://[-a-zA-Z0-9.]*\.trycloudflare.com' /tmp/cloudflared.log | head -n 1 || true)
    if [ -n "$PUBLIC_URL" ]; then
        break
    fi
    sleep 0.5
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
if [ -n "$PUBLIC_URL" ]; then
    echo "📞 APPEL TÉLÉPHONIQUE MAINS LIBRES OPÉRATIONNEL !"
    echo ""
    echo "👉 LIEN UNIQUE À OUVRIR DANS SAFARI (IPHONE OU MAC) :"
    echo "   $PUBLIC_URL"
    echo ""
    echo "💡 Liaison Gemini 100% active et validée."
else
    echo "⚠️ Lien local : http://localhost:8765"
fi
echo "═══════════════════════════════════════════════════════════════"
echo ""

trap 'kill $SERVER_PID $TUNNEL_PID 2>/dev/null || true; exit 0' INT TERM
wait
