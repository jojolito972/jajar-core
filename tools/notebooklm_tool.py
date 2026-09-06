"""
tools/notebooklm_tool.py — Passerelle Réelle vers Google NotebookLM (CLI notebooklm-py).
Import datetime corrigé, timeout résistant et extraction JSON stricte.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Final

import config
from config import SecurityTier
from core.tools_registry import outil

logger: Final[logging.Logger] = logging.getLogger("jarvis.notebooklm")


def _trouver_binaire_notebooklm() -> str:
    binaire = shutil.which("notebooklm")
    if binaire:
        return binaire

    candidats = [
        Path.home() / ".local" / "bin" / "notebooklm",
        Path.home() / ".venvs" / "notebooklm" / "bin" / "notebooklm",
        Path("/Users/denmac/Assistant_IA/jarvis/venv/bin/notebooklm"),
        Path("/opt/homebrew/bin/notebooklm"),
        Path("/usr/local/bin/notebooklm"),
    ]
    for c in candidats:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)

    return "notebooklm"


@outil(tier=SecurityTier.AUTO)
def verifier_session_notebooklm() -> str:
    """Vérifie l'état réel de l'authentification Google NotebookLM."""
    bin_path = _trouver_binaire_notebooklm()
    try:
        res = subprocess.run([bin_path, "auth", "check", "--test"], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            status_res = subprocess.run([bin_path, "status"], capture_output=True, text=True, timeout=10)
            return f"✅ Session NotebookLM active et validée :\n{status_res.stdout.strip()}"
        return f"⚠️ Authentification requise (`notebooklm login`). Détail : {res.stderr.strip()}"
    except Exception as e:
        return f"Erreur vérification NotebookLM : {e}"


@outil(tier=SecurityTier.AUTO)
def creer_et_alimenter_carnet_notebooklm(titre_carnet: str, sources: list[str]) -> str:
    """Crée un carnet NotebookLM et y ajoute réellement une liste de fichiers sources."""
    bin_path = _trouver_binaire_notebooklm()
    try:
        res_create = subprocess.run([bin_path, "create", titre_carnet, "--json"], capture_output=True, text=True, timeout=30)
        if res_create.returncode != 0:
            return f"⚠️ Échec création carnet : {res_create.stderr.strip()}"

        data_nb = json.loads(res_create.stdout)
        nb_id = data_nb.get("notebook", {}).get("id") or data_nb.get("id")
    except Exception as e:
        return f"Erreur création carnet : {e}"

    rapport_sources = []
    for s in sources:
        try:
            res_add = subprocess.run([bin_path, "source", "add", s, "-n", nb_id, "--json"], capture_output=True, text=True, timeout=120)
            rapport_sources.append(f"• Source indexée : `{s}`" if res_add.returncode == 0 else f"• Échec `{s}` : {res_add.stderr.strip()[:80]}")
        except Exception as err_s:
            rapport_sources.append(f"• Erreur `{s}` : {err_s}")

    return f"✅ Carnet « **{titre_carnet}** » créé (ID: `{nb_id}`)\n" + "\n".join(rapport_sources)


@outil(tier=SecurityTier.AUTO)
def interroger_carnet_notebooklm(notebook_id: str, question: str) -> str:
    """Interroge un carnet NotebookLM existant et retourne la synthèse RAG."""
    bin_path = _trouver_binaire_notebooklm()
    try:
        res = subprocess.run([bin_path, "ask", question, "-n", notebook_id, "--json"], capture_output=True, text=True, timeout=60)
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            return f"📖 **Réponse NotebookLM :**\n\n{data.get('answer') or data.get('text') or res.stdout.strip()}"
        return f"⚠️ Erreur interrogation : {res.stderr.strip()}"
    except Exception as e:
        return f"Erreur interrogation carnet : {e}"


@outil(tier=SecurityTier.CONFIRM)
def generer_podcast_audio_notebooklm(notebook_id: str, instructions_focus: str = "Focus on strategic points", nom_fichier_sortie: str = "") -> str:
    """Génère un podcast audio de discussion (Deep Dive) depuis un carnet NotebookLM."""
    bin_path = _trouver_binaire_notebooklm()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin_cible = config.DEPOT_DIR / (nom_fichier_sortie.strip() or f"podcast_notebooklm_{ts}.mp3")

    try:
        res_gen = subprocess.run([bin_path, "generate", "audio", instructions_focus, "-n", notebook_id, "--json"], capture_output=True, text=True, timeout=120)
        if res_gen.returncode != 0:
            return f"⚠️ Échec lancement audio : {res_gen.stderr.strip()}"

        data_gen = json.loads(res_gen.stdout)
        task_id = data_gen.get("task_id") or data_gen.get("id")

        if task_id:
            subprocess.run([bin_path, "artifact", "wait", task_id, "-n", notebook_id, "--timeout", "1200"], capture_output=True, text=True, timeout=1210)
            res_dl = subprocess.run([bin_path, "download", "audio", str(chemin_cible), "-a", task_id, "-n", notebook_id], capture_output=True, text=True, timeout=60)
            if res_dl.returncode == 0 and chemin_cible.exists():
                return f"🎙️ **Podcast Audio généré :** `{chemin_cible}` ({round(chemin_cible.stat().st_size / (1024*1024), 2)} Mo)"

        return f"Génération audio achevée : {res_gen.stdout.strip()}"
    except Exception as e:
        return f"Erreur génération podcast : {e}"
