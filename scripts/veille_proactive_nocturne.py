"""
scripts/veille_proactive_nocturne.py — Veille technologique autonome, association sémantique et mise à jour du Graphe
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

# Ancrage racine
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from core.llm_router import router
from tools.graph_memory import enregistrer_relation_graphe
from tools.second_cerveau import synchroniser_second_cerveau
from tools.web_tool import rechercher_web


def executer_veille_proactive():
    ts = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"🛰️ Lancement de la Veille Proactive Autonome ({ts})...")

    # 1. Lecture des projets actifs dans le Second Cerveau
    projets_dir = config.VAULT_DIR / "01_Projets"
    projets_texte = ""
    if projets_dir.exists():
        for p in projets_dir.glob("*.md"):
            projets_texte += f"\n--- PROJET ACTIF : {p.stem} ---\n{p.read_text(encoding='utf-8')[:1200]}\n"

    if not projets_texte:
        projets_texte = "Projets IA souveraine, automatisation macOS, FastAPi Micro-SaaS, Telegram Bot, LanceDB RAG."

    # 2. Recherche ciblée sur les dernières innovations
    sujets_veille = [
        "Python AI agents frameworks SOTA 2026",
        "FastAPI async production best practices 2026",
        "LanceDB vector search optimization",
        "macOS automation local LLM tooling"
    ]

    resultats_veille = []
    for s in sujets_veille:
        res = rechercher_web(s, max_resultats=2)
        resultats_veille.append(f"Recherche '{s}' :\n{res}")

    corpus_veille = "\n\n".join(resultats_veille)

    # 3. Analyse d'association sémantique par l'IA
    prompt_association = (
        f"Tu es RAY, Analyste de Veille Stratégique du Studio JAJAR pour {config.UTILISATEUR}.\n"
        f"Date : {ts}\n\n"
        f"PROJETS ACTIFS DE DEN :\n{projets_texte}\n\n"
        f"DERNIÈRES NOUVEAUTÉS DU WEB TECH :\n{corpus_veille}\n\n"
        "TÂCHES DE VEILLE & RAPPROCHEMENT :\n"
        "1. Identifie au moins 2 connexions sémantiques directes entre les nouveautés du web et les projets de Den.\n"
        "2. Formule une recommandation technique concrète pour améliorer un de ses projets existants.\n"
        "3. Définis 2 nouvelles relations d'entités à enregistrer dans le Graphe de Connaissances.\n\n"
        "Format JSON strict :\n"
        "{\n"
        '  "connexions": [{"projet": "...", "nouveaute": "...", "impact": "..."}],\n'
        '  "recommandation_action": "...",\n'
        '  "relations_graphe": [{"source": "...", "relation": "...", "cible": "...", "details": "..."}]\n'
        "}"
    )

    try:
        res_raw, _ = router.generer(prompt_association, "Analyse les connexions de veille.", temperature=0.1)
        res_clean = res_raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(res_clean)

        # 4. Enregistrement des nouvelles connexions dans le Graphe de Connaissances
        for rel in data.get("relations_graphe", []):
            msg_g = enregistrer_relation_graphe(rel["source"], rel["relation"], rel["cible"], rel.get("details", ""))
            print(f"  🔗 {msg_g}")

        # 5. Archivage de la note de veille
        dossier_veille = config.VAULT_DIR / "03_Veille_Technologique"
        dossier_veille.mkdir(parents=True, exist_ok=True)
        f_veille = dossier_veille / f"veille_{ts}.md"

        rapport_md = (
            f"# Veille Technologique & Rapprochement Projets ({ts})\n\n"
            f"## Connexions Sémantiques Découvertes\n\n"
        )
        for c in data.get("connexions", []):
            rapport_md += f"### 💡 Impact sur `{c.get('projet')}`\n- **Nouveauté :** {c.get('nouveaute')}\n- **Application concrète :** {c.get('impact')}\n\n"

        rapport_md += f"## Recommandation Stratégique\n{data.get('recommandation_action')}\n"
        f_veille.write_text(rapport_md, encoding="utf-8")
        print(f"  ✅ Rapport de veille archivé : `{f_veille}`")

    except Exception as e:
        print(f"  ⚠️ Erreur analyse de veille : {e}")

    # 6. Re-synchronisation globale LanceDB
    synchroniser_second_cerveau()
    print("✨ Veille proactive terminée.")


if __name__ == "__main__":
    executer_veille_proactive()
