"""
tools/gui_control.py — Contrôle de l'interface graphique macOS avec validation stdin.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Final

import config
from config import SecurityTier
from core.tools_registry import outil

logger: Final[logging.Logger] = logging.getLogger("jajar.gui")


def _executer_osascript_securise(script_applescript: str, timeout_s: int = 8) -> str:
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
            return f"⚠️ Erreur GUI ({proc.returncode}): {stderr.strip()}"
        return stdout.strip()
    except Exception as e:
        return f"⚠️ Échec GUI : {e}"


def _obtenir_resolution_ecran_principale() -> tuple[int, int]:
    script = '''
    tell application "Finder"
        set b to bounds of window of desktop
        return (item 3 of b as string) & "x" & (item 4 of b as string)
    end tell
    '''
    res = _executer_osascript_securise(script)
    if "x" in res:
        try:
            w, h = res.split("x")
            return int(w), int(h)
        except Exception:
            pass
    return 1920, 1080


@outil(tier=SecurityTier.CONFIRM)
def simuler_clic_coordonnees(x: int, y: int, double_clic: bool = False) -> str:
    """Effectue un clic souris physique aux coordonnées d'écran (x, y)."""
    clic_type = "c" if not double_clic else "dc"
    if subprocess.run(["which", "cliclick"], capture_output=True).returncode == 0:
        try:
            subprocess.run(["cliclick", f"{clic_type}:{x},{y}"], check=True, timeout=5)
            return f"🖱️ Clic souris exécuté aux coordonnées ({x}, {y})."
        except Exception:
            pass

    script = f'''
    tell application "System Events"
        click at {{{x}, {y}}}
    end tell
    '''
    res = _executer_osascript_securise(script)
    return f"🖱️ Clic exécuté aux coordonnées ({x}, {y})." if not res.startswith("⚠️") else res


@outil(tier=SecurityTier.CONFIRM)
def simuler_frappe_texte(texte: str, appuyer_entree: bool = True) -> str:
    """Saisit du texte au clavier dans l'application active."""
    texte_clean = texte.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
    press_enter = '\nkey code 36' if appuyer_entree else ''
    script = f'''
    tell application "System Events"
        keystroke "{texte_clean}"
        {press_enter}
    end tell
    '''
    res = _executer_osascript_securise(script)
    return f"⌨️ Texte saisi : « {texte} »" if not res.startswith("⚠️") else res


@outil(tier=SecurityTier.CONFIRM)
def simuler_raccourci_clavier(touche: str, modificateurs: list[str] = ["command"]) -> str:
    """Exécute un raccourci clavier macOS."""
    mods_valides = [m for m in modificateurs if m in ("command", "shift", "option", "control")]
    mods_str = ", ".join(f"{m} down" for m in mods_valides)
    touche_clean = re.sub(r'[^a-zA-Z0-9]', '', touche)
    script = f'''
    tell application "System Events"
        keystroke "{touche_clean}" using {{{mods_str}}}
    end tell
    '''
    res = _executer_osascript_securise(script)
    return f"⌨️ Raccourci exécuté : {['+'.join(mods_valides)]}+{touche_clean}" if not res.startswith("⚠️") else res


@outil(tier=SecurityTier.CONFIRM)
def vision_et_clic_sur_element(nom_application: str, description_cible: str) -> str:
    """Localise visuellement un élément d'interface avec Gemini et clique dessus."""
    app_clean = re.sub(r'[^a-zA-Z0-9_\- ]', '', nom_application).strip()
    _executer_osascript_securise(f'tell application "{app_clean}" to activate')
    # [OPTIMISÉ MACHINE DE GUERRE] time.sleep -> asyncio.sleep recommandé
# time.sleep(0.6)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    cap_path = config.IMAGE_DIR / f"gui_click_{ts}.jpg"
    try:
        subprocess.run(["screencapture", "-x", "-t", "jpg", str(cap_path)], check=True, timeout=6)
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "75", "-Z", "1280", str(cap_path)], capture_output=True, timeout=4)
    except Exception as e:
        return f"Erreur capture pour Vision-to-Click : {e}"

    try:
        from google.genai import types
        client = config.GENAI_CLIENT
        with open(cap_path, "rb") as f:
            img_bytes = f.read()

        prompt_spatial = (
            f"Tu es l'Analyseur Spatial GUI de JAJAR sur macOS.\n"
            f"CIBLE À LOCALISER : '{description_cible}' dans l'application '{app_clean}'.\n\n"
            "Retourne UNIQUEMENT un objet JSON strict indiquant le centre de l'élément cible sur une échelle de 0 à 1000 :\n"
            "{\"x\": 450, \"y\": 120, \"element_trouve\": true, \"label\": \"Nom du bouton\"}\n"
            "Si l'élément est introuvable : {\"element_trouve\": false}"
        )

        res = client.models.generate_content(
            model=config.MODELE_TEXTE_GEMINI,
            contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"), prompt_spatial],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
        )

        data = json.loads(res.text.strip()) if res.text else {}
        if not data.get("element_trouve"):
            return f"⚠️ Élément « {description_cible} » non repéré dans {app_clean}."

        norm_x = data.get("x", 500)
        norm_y = data.get("y", 500)

        screen_w, screen_h = _obtenir_resolution_ecran_principale()
        real_x = int((norm_x / 1000.0) * screen_w)
        real_y = int((norm_y / 1000.0) * screen_h)

        res_clic = simuler_clic_coordonnees(real_x, real_y)
        return f"🎯 Élément « {description_cible} » localisé ({data.get('label', '')}). {res_clic}"
    except Exception as e:
        return f"Erreur Vision-to-Click : {e}"
