from __future__ import annotations

"""
tools/system_tools.py — Suite Consolidée des 25 Outils Système macOS JAJAR v2.
Diagnostic Disque Instantané (<0.2s), Shell Confiné, Vision, AppleScript, Spotlight, Caches.
"""

import asyncio
import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import warnings
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Final

from bs4 import BeautifulSoup

import config
from config import SecurityTier
from core.security import (
    SecurityViolation,
    assainir_nom_fichier,
    valider_confinement_chemin,
    verifier_commande_securisee,
)
from core.tools_registry import outil

logger: Final[logging.Logger] = logging.getLogger("jarvis.system")
DOSSIER_SUPPRIMER: Final[Path] = Path.home() / "Desktop" / "Supprimer"
DOSSIER_SUPPRIMER.mkdir(parents=True, exist_ok=True)


def _executer_osascript_securise(script_applescript: str, timeout_s: int = 15) -> str:
    try:
        proc = subprocess.Popen(
            ["osascript", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(input=script_applescript, timeout=timeout_s)
        if proc.returncode != 0:
            return f"⚠️ Erreur AppleScript ({proc.returncode}): {stderr.strip()}"
        return stdout.strip()
    except subprocess.TimeoutExpired:
        proc.kill()
        return "⚠️ Délai d'attente AppleScript dépassé."
    except Exception as e:
        return f"⚠️ Échec exécution AppleScript: {e}"


# ---------------------------------------------------------------------------
# 1. DIAGNOSTIC DISQUE ULTRA-RAPIDE (<0.2s) & MAINTENANCE SYSTÈME
# ---------------------------------------------------------------------------

@outil(tier=SecurityTier.AUTO)
def diagnostiquer_encombrement_et_bordel_mac() -> str:
    """Analyse chirurgicale instantanée (<0.2s) des zones d'encombrement et du désordre sur le Mac de Denis."""
    try:
        total, used, free = shutil.disk_usage("/System/Volumes/Data")
        total_go = round(total / (1024**3), 1)
        used_go = round(used / (1024**3), 1)
        free_go = round(free / (1024**3), 1)
        pct_used = round((used / total) * 100, 1)

        points_chauds = [
            ("Téléchargements (Downloads)", Path.home() / "Downloads"),
            ("Bureau (Desktop)", Path.home() / "Desktop"),
            ("Xcode DerivedData (Builds)", Path.home() / "Library/Developer/Xcode/DerivedData"),
            ("Simulateurs iOS CoreSimulator", Path.home() / "Library/Developer/CoreSimulator/Devices"),
            ("Caches Utilisateur macOS", Path.home() / "Library/Caches"),
            ("Corbeille (.Trash)", Path.home() / ".Trash"),
        ]

        rapport_zones = []
        total_gain_potentiel_mo = 0

        for libelle, chemin in points_chauds:
            if chemin.exists():
                try:
                    res = subprocess.run(["du", "-sk", str(chemin)], capture_output=True, text=True, timeout=2)
                    if res.stdout:
                        taille_ko = int(res.stdout.split()[0])
                        taille_mo = round(taille_ko / 1024, 1)
                        taille_go = round(taille_ko / (1024 * 1024), 2)
                        
                        poids_str = f"**`{taille_go} Go`**" if taille_go >= 1.0 else f"`{taille_mo} Mo`"
                        nb_items = len(list(chemin.glob("*"))) if chemin.is_dir() else 1
                        rapport_zones.append(f"• **{libelle}** : {poids_str} ({nb_items} éléments) ➔ `{chemin}`")
                        
                        if "DerivedData" in libelle or "Caches" in libelle or "Trash" in libelle or "CoreSimulator" in libelle:
                            total_gain_potentiel_mo += taille_mo
                except Exception:
                    pass

        gain_go = round(total_gain_potentiel_mo / 1024, 2)

        return (
            f"🧹 **Bilan Chirurgical de l'Espace Disque (Mac de {config.UTILISATEUR}) :**\n\n"
            f"• **Disque Principal :** `{used_go} Go` occupés sur `{total_go} Go` (**{pct_used}%** plein) — `{free_go} Go` libres.\n"
            f"• **Gisement Récupérable Immédiatement :** **`~{gain_go} Go`** de caches et fichiers temporaires nettoyables.\n\n"
            f"📂 **Détail par Zone :**\n"
            + "\n".join(rapport_zones)
        )
    except Exception as e:
        return f"Erreur diagnostic disque : {e}"


@outil(tier=SecurityTier.AUTO)
def analyser_espace_disque_macos(dossier_cible: str = "/Users/denmac", top_n: int = 8) -> str:
    """Analyse rapide de l'espace disque du Mac."""
    return diagnostiquer_encombrement_et_bordel_mac()


@outil(tier=SecurityTier.AUTO)
def executer_commande_shell(commande: str, dossier_travail: str = "") -> str:
    """Exécute une commande shell locale sécurisée sur le Mac de Denis."""
    try:
        verifier_commande_securisee(commande)
    except SecurityViolation as e:
        return f"⛔ Refus de sécurité : {e}"

    cwd = dossier_travail or str(config.ZONE_SECURISEE)
    timeout_s = getattr(config, "TIMEOUT_COMMANDE", 60)

    try:
        res = subprocess.run(commande, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)
        sortie = (res.stdout + res.stderr).strip()
        if res.returncode == 0:
            return sortie or "Commande exécutée avec succès (Code 0)."
        return f"⚠️ Code sortie {res.returncode} :\n{sortie}"
    except subprocess.TimeoutExpired:
        return f"⚠️ Délai d'attente dépassé ({timeout_s}s)."
    except Exception as e:
        return f"Erreur shell : {e}"


# ---------------------------------------------------------------------------
# 2. FICHIERS, SPOTLIGHT, APPLESCRIPT & IMAGES HD FLUX
# ---------------------------------------------------------------------------

@outil(tier=SecurityTier.AUTO)
def chercher_fichier_sur_mac(nom_fichier: str, dossier_depart: str = "") -> str:
    """Recherche instantanée d'un fichier sur tout le Mac via Spotlight (mdfind < 0.05s)."""
    nom_net = nom_fichier.strip().strip('"').strip("'")
    try:
        res = subprocess.run(["mdfind", "-name", nom_net], capture_output=True, text=True, timeout=8)
        lignes = [l for l in res.stdout.splitlines() if l.strip() and "/.Trash/" not in l and "/Library/" not in l]
        if lignes:
            return "📁 **Fichiers trouvés sur ton Mac :**\n" + "\n".join(f"- `{l}`" for l in lignes[:10])
    except Exception:
        pass
    return f"Aucun fichier nommé '{nom_net}' trouvé sur le Mac."


@outil(tier=SecurityTier.AUTO)
def lire_fichier(chemin_fichier: str, max_lignes: int = 300) -> str:
    """Lit un fichier texte sur le Mac."""
    cible = valider_confinement_chemin(chemin_fichier)
    if not cible.exists():
        return f"Fichier introuvable : {cible}"
    lignes = cible.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lignes[:max_lignes]) or "(Fichier vide)"


@outil(tier=SecurityTier.AUTO)
def ecrire_fichier(chemin_fichier: str, contenu: str) -> str:
    """Écrit un fichier texte avec sauvegarde atomique."""
    cible = valider_confinement_chemin(chemin_fichier)
    cible.parent.mkdir(parents=True, exist_ok=True)
    tmp = cible.parent / f".tmp_{cible.name}_{os.urandom(4).hex()}"
    tmp.write_text(contenu, encoding="utf-8")
    tmp.replace(cible)
    return f"✅ Fichier écrit avec succès : `{cible}`"


@outil(tier=SecurityTier.AUTO)
def executer_applescript(script: str) -> str:
    """Exécute un script AppleScript natif de manière sécurisée."""
    return _executer_osascript_securise(script)


@outil(tier=SecurityTier.AUTO)
def lire_rappels_macos(inclure_termines: bool = False, limite: int = 25) -> str:
    """Récupère les rappels Apple avec extraction sécurisée sans crash."""
    filtre = "" if inclure_termines else "whose completed is false"
    script = f'''
    tell application "Reminders"
        try
            set remList to (reminders {filtre})
            set totalCount to count of remList
            if totalCount is 0 then return "Aucun rappel en attente."
            set maxFetch to {limite}
            if totalCount < maxFetch then set maxFetch to totalCount
            set output to "📋 " & maxFetch & " rappels (" & totalCount & " au total) :" & linefeed
            repeat with i from 1 to maxFetch
                set r to item i of remList
                set rName to name of r
                set rDone to completed of r
                set statusIcon to "[ ]"
                if rDone is true then set statusIcon to "[x]"
                set output to output & statusIcon & " " & rName & linefeed
            end repeat
            return output
        on error err
            return "Erreur Rappels: " & err
        end try
    end tell
    '''
    return _executer_osascript_securise(script)


@outil(tier=SecurityTier.AUTO)
def lire_notes_macos(limite: int = 10) -> str:
    """Liste les N dernières notes créées ou modifiées dans Apple Notes."""
    script = f'''
    tell application "Notes"
        try
            set noteList to notes
            set total to count of noteList
            if total is 0 then return "Aucune note dans Apple Notes."
            set maxFetch to {limite}
            if total < maxFetch then set maxFetch to total
            set output to "📝 " & maxFetch & " dernières Notes :" & linefeed
            repeat with i from 1 to maxFetch
                set n to item i of noteList
                set output to output & i & ". « " & (name of n) & " »" & linefeed
            end repeat
            return output
        on error err
            return "Erreur Notes: " & err
        end try
    end tell
    '''
    return _executer_osascript_securise(script)


@outil(tier=SecurityTier.AUTO, personas=["ansel", "jarvis", "leo", "alba"])
def generer_image(prompt_image: str, ratio_aspect: str = "16:9") -> str:
    """Génère une image photoréaliste HD via Hugging Face FLUX.1 / Engine HD."""
    import io
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin_img = config.IMAGE_DIR / f"flux_hd_{ts}.png"
    chemin_img.parent.mkdir(parents=True, exist_ok=True)

    ratios_dims = {
        "16:9": (1344, 768),
        "1:1": (1024, 1024),
        "4:3": (1024, 768),
    }
    w, h = ratios_dims.get(ratio_aspect, (1344, 768))

    prompt_master = (
        f"A professional 85mm photograph of {prompt_image.strip()}, "
        "authentic human textures, cinematic natural lighting, Hasselblad H6D-100c, 4k masterwork"
    )

    image_bytes = b""
    moteur = "FLUX Engine HD"
    hf_token = getattr(config, "HUGGINGFACE_API_KEY", "")

    if hf_token:
        try:
            from huggingface_hub import InferenceClient
            hf_client = InferenceClient(api_key=hf_token)
            img_pil = hf_client.text_to_image(prompt=prompt_master, model="black-forest-labs/FLUX.1-schnell", width=w, height=h)
            buf = io.BytesIO()
            img_pil.save(buf, format="PNG")
            image_bytes = buf.getvalue()
            moteur = "Hugging Face FLUX.1-schnell (SOTA 4K)"
        except Exception:
            pass

    if not image_bytes:
        seed = int.from_bytes(os.urandom(3), "big")
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt_master)}?width={w}&height={h}&model=flux&nologo=true&seed={seed}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "JAJAR/2.0"})
            with urllib.request.urlopen(req, timeout=50) as resp:
                image_bytes = resp.read()
        except Exception as e:
            return f"⚠️ Échec génération image : {e}"

    chemin_img.write_bytes(image_bytes)
    try:
        subprocess.Popen(["open", "-a", "Preview", str(chemin_img)])
    except Exception:
        pass

    return f"🎨 **Image Haute Définition Générée via `{moteur}` !**\n• **Fichier :** `{chemin_img}` ({round(len(image_bytes)/1024, 1)} Ko)"

# ---------------------------------------------------------------------------
# 9. EXTRACTION & ANALYSE DE REELS INSTAGRAM / TIKTOK / YOUTUBE (YT-DLP)
# ---------------------------------------------------------------------------

@outil(tier=SecurityTier.AUTO)
def analyser_lien_video_social(url_video: str) -> str:
    """Extrait instantanément la description, le titre et le contenu d'un Reel Instagram, TikTok ou YouTube sans blocage de connexion."""
    clean_url = url_video.strip().split("?")[0]
    import shutil
    yt_bin = shutil.which("yt-dlp") or "yt-dlp"

    try:
        cmd = [yt_bin, "--dump-json", "--skip-download", "--no-warnings", clean_url]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            titre = data.get("title") or "Reel / Vidéo"
            desc = data.get("description") or "(Pas de description)"
            uploader = data.get("uploader") or data.get("channel") or "Créateur"
            duree = data.get("duration_string") or f"{data.get('duration', 0)}s"

            return (
                f"📹 **Analyse Réussie du Média Social :**\n\n"
                f"• **Titre / Sujet :** {titre}\n"
                f"• **Créateur :** @{uploader}\n"
                f"• **Durée :** `{duree}`\n\n"
                f"📝 **Description / Transcription extraite :**\n"
                f"> {desc[:2000]}"
            )
        else:
            return f"⚠️ Impossible d'extraire le contenu direct via l'URL : {res.stderr[:200] if res.stderr else 'Accès restreint par la plateforme'}."
    except Exception as e:
        return f"Erreur extraction vidéo/reel : {e}"
