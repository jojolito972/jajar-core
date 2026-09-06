#!/bin/bash
# Script de sauvegarde quotidienne de /Users/denmac/Assistant_IA/jarvis vers ios@192.168.1.33:Desktop/JAJAR

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ZIP_NAME="jarvis_backup_$TIMESTAMP.zip"
LOCAL_ZIP="/tmp/$ZIP_NAME"
REMOTE_HOST="ios@192.168.1.33"
REMOTE_DIR="Desktop/JAJAR"

echo "[1/3] Compression du dossier /Users/denmac/Assistant_IA/jarvis..."
cd /Users/denmac/Assistant_IA
zip -r "$LOCAL_ZIP" jarvis -x "*/.git/*" "*/node_modules/*" "*/.DS_Store"

echo "[2/3] Vérification et création du dossier distant si nécessaire..."
ssh -o ConnectTimeout=5 "$REMOTE_HOST" "mkdir -p ~/Desktop/JAJAR"

echo "[3/3] Transfert de l'archive vers $REMOTE_HOST:$REMOTE_DIR..."
scp -o ConnectTimeout=10 "$LOCAL_ZIP" "$REMOTE_HOST:$REMOTE_DIR/"

# Nettoyage local
rm -f "$LOCAL_ZIP"
echo "Sauvegarde terminée avec succès le $(date)"