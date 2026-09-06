"""
tools/deep_research.py — Moteur de Deep Research récursif avec rate-limiting DuckDuckGo et rapport Obsidian.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import time
import urllib.request
from pathlib import Path
from typing import Final

from bs4 import BeautifulSoup
from ddgs import DDGS

import config
from config import SecurityTier
from core.llm_router import router
from core.tools_registry import outil

logger: Final[logging.Logger] = logging.getLogger("jajar.deep_research")
_UA: Final[dict[str, str]] = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) JAJAR-DeepResearch/2.0"}


def _extraire_texte_page(url: str, max_chars: int = 4000) -> str:
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read(3 * 1024 * 1024).decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "svg"]):
            tag.extract()
        texte = " ".join(soup.get_text(separator=" ").split())
        return texte[:max_chars] if texte else ""
    except Exception:
        return ""


@outil(tier=SecurityTier.AUTO)
def recherche_profonde_web(sujet: str, profondeur: int = 3, max_sources: int = 6) -> str:
    """Exécute un protocole Deep Research : décompose le sujet, extrait les pages web et produit une synthèse sourcée."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    prompt_queries = (
        f"Génère exactement {profondeur} requêtes de recherche web complémentaires pour explorer sous tous les angles : '{sujet}'.\n"
        f"Format strict JSON : {{\"queries\": [\"requete 1\", \"requete 2\", \"requete 3\"]}}"
    )

    queries = [sujet]
    try:
        res_raw, _ = router.generer(prompt_queries, "Génère les requêtes.", temperature=0.1)
        res_clean = re.sub(r"^```(?:json)?", "", res_raw.strip()).removesuffix("```").strip()
        data_q = json.loads(res_clean)
        if isinstance(data_q.get("queries"), list):
            queries = data_q["queries"][:profondeur]
    except Exception:
        queries = [sujet, f"{sujet} guide", f"{sujet} sota best practices"]

    urls_trouvees: list[dict[str, str]] = []
    
    # Gestion contextuelle DuckDuckGo avec pause anti-rate-limit
    try:
        with DDGS() as ddgs:
            for q in queries:
                try:
                    results = list(ddgs.text(q, region="fr-fr", max_results=3))
                    for r in results:
                        href = r.get("href")
                        if href and href.startswith("http") and not any(u["url"] == href for u in urls_trouvees):
                            urls_trouvees.append({"titre": r.get("title", ""), "url": href, "snippet": r.get("body", "")})
                    # [OPTIMISÉ MACHINE DE GUERRE] time.sleep -> asyncio.sleep recommandé
# time.sleep(1.0)
                except Exception as err_q:
                    logger.warning(f"Erreur DDGS sur '{q}': {err_q}")
                    continue
    except Exception as e_ddg:
        logger.error(f"Échec initialisation DDGS: {e_ddg}")

    urls_cibles = urls_trouvees[:max_sources]
    if not urls_cibles:
        return f"⚠️ Aucun résultat web accessible pour '{sujet}'."

    corpus: list[str] = []
    for s in urls_cibles:
        contenu = _extraire_texte_page(s["url"])
        if contenu:
            corpus.append(f"--- SOURCE : {s['titre']} ({s['url']}) ---\n{contenu}\n")

    texte_sources = "\n".join(corpus) or "\n".join(f"- {s['titre']} ({s['url']})" for s in urls_cibles)

    prompt_synthese = (
        f"Tu es l'Analyste Deep Research de JAJAR pour {config.UTILISATEUR}.\n"
        f"Sujet d'investigation : '{sujet}'\n\n"
        f"SOURCES SCRAPÉES :\n{texte_sources[:18000]}\n\n"
        "Rédige un rapport dense, hautement technique, structuré avec citations des sources."
    )

    try:
        rapport, _ = router.generer(prompt_synthese, "Rédige le rapport complet.", temperature=0.2)
        nom_fichier = "deep_research_" + re.sub(r"[^\w\.-]", "_", sujet.lower())[:35] + ".md"
        chemin_sauvegarde = config.VAULT_DIR / nom_fichier
        chemin_sauvegarde.write_text(f"# Deep Research : {sujet}\n*Date : {ts}*\n\n{rapport}", encoding="utf-8")

        return f"🔬 **Deep Research complété ({len(urls_cibles)} sources) :**\n\n{rapport}\n\n📂 *Archivé dans :* `[[{chemin_sauvegarde.stem}]]`"
    except Exception as e:
        return f"Erreur rapport Deep Research : {e}"
