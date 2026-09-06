#!/bin/zsh
set -e
CIBLE_SSH="ios@192.168.1.33"
DOSSIER_DISTANT="~/Desktop/JAJAR"
DOSSIER_SOURCE="/Users/denmac/Assistant_IA"
NOM_DOSSIER="jarvis"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_LOCALE="/tmp/jarvis_backup_${TIMESTAMP}.tar.gz"

tar --exclude="${NOM_DOSSIER}/venv" --exclude="${NOM_DOSSIER}/.git" --exclude="${NOM_DOSSIER}/**/__pycache__" --exclude="${NOM_DOSSIER}/audio_temp/*" --exclude="${NOM_DOSSIER}/logs/*.log" --exclude="${NOM_DOSSIER}/.DS_Store" -czf "${ARCHIVE_LOCALE}" -C "${DOSSIER_SOURCE}" "${NOM_DOSSIER}"
ssh -o ConnectTimeout=8 -o BatchMode=yes "${CIBLE_SSH}" "mkdir -p ${DOSSIER_DISTANT}"
scp -o ConnectTimeout=10 -o BatchMode=yes "${ARCHIVE_LOCALE}" "${CIBLE_SSH}:${DOSSIER_DISTANT}/"
rm -f "${ARCHIVE_LOCALE}"
echo "SUCCESS"
