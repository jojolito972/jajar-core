"""
tools/web_tool.py — Recherche web et téléchargement sécurisé avec gestionnaire de contexte.
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path
from typing import Final

import config
from config import SecurityTier
from core.tools_registry import outil

TAILLE_MAX_TELECHARGEMENT: Final[int] = 500 * 1024 * 1024
TAILLE_MAX_LECTURE_PAGE: Final[int] = 5 * 1024 * 1024
DOSSIER_TELECHARGEMENTS: Final[Path] = config.DEPOT_DIR

_UA: Final[dict[str, str]] = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) JARVIS/2.0"}


@outil(tier=SecurityTier.AUTO)
def rechercher_web(requete: str, max_resultats: int = 5) -> str:
    """Recherche sur le web via DuckDuckGo avec gestionnaire de contexte."""
    from ddgs import DDGS
    try:
        with DDGS() as ddgs:
            resultats = list(ddgs.text(requete, region="fr-fr", max_results=max_resultats))
        
        if not resultats:
            return f"Aucun résultat trouvé pour « {requete} »."

        rendu = [f"🌐 **Résultats pour « {requete} » :**\n"]
        for i, r in enumerate(resultats, 1):
            rendu.append(f"{i}. **{r.get('title', 'Sans titre')}**\n   {r.get('href', '#')}\n   {r.get('body', '')}\n")
        return "\n".join(rendu)
    except Exception as e:
        return f"Erreur lors de la recherche web : {e}"


@outil(tier=SecurityTier.AUTO)
def lire_page_web(url: str, max_caracteres: int = 3000) -> str:
    """Charge une page web et en extrait le texte brut."""
    from bs4 import BeautifulSoup
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=15) as reponse:
            html = reponse.read(TAILLE_MAX_LECTURE_PAGE).decode("utf-8", errors="ignore")

        soup = BeautifulSoup(html, "html.parser")
        for elem in soup(["script", "style", "nav", "header", "footer", "aside"]):
            elem.extract()

        texte = " ".join(soup.get_text(separator=" ").split())
        return texte[:max_caracteres] if texte else "Page vide ou contenu non extractible."
    except Exception as e:
        return f"Impossible de charger la page : {e}"


def _nom_fichier_sur(nom: str, url: str) -> str:
    candidat = nom.strip() or url.split("/")[-1].split("?")[0] or "fichier_telecharge"
    candidat = Path(candidat).name
    return re.sub(r'[<>:"|?*\x00-\x1f]', "_", candidat) or "fichier_telecharge"


@outil(tier=SecurityTier.AUTO)
def telecharger_fichier(url: str, nom_fichier_cible: str = "") -> str:
    """Télécharge un fichier distant de manière sécurisée dans depot/."""
    DOSSIER_TELECHARGEMENTS.mkdir(parents=True, exist_ok=True)
    chemin_dest = DOSSIER_TELECHARGEMENTS / _nom_fichier_sur(nom_fichier_cible, url)

    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=30) as reponse:
            taille = reponse.headers.get("Content-Length")
            if taille and int(taille) > TAILLE_MAX_TELECHARGEMENT:
                return "⚠️ Téléchargement refusé : fichier trop volumineux (> 500 Mo)."

            with open(chemin_dest, "wb") as f_out:
                f_out.write(reponse.read(TAILLE_MAX_TELECHARGEMENT))

        return f"✅ Téléchargé : `{chemin_dest}` ({round(chemin_dest.stat().st_size / 1024, 1)} Ko)"
    except Exception as e:
        if chemin_dest.exists():
            chemin_dest.unlink()
        return f"Erreur lors du téléchargement : {e}"
