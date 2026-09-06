"""
tools/debat_agents.py — Débat contradictoire autonome multi-agents avec archivage Obsidian.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Final

import config
from config import SecurityTier
from core.llm_router import router
from core.tools_registry import outil


@outil(tier=SecurityTier.AUTO)
def orchestrer_debat_studio(sujet_complexe: str, agents_participants: list[str] = ["ray", "tesla", "cleo"]) -> str:
    """Convoque un débat contradictoire entre spécialistes et produit un arbitrage ferme dans Obsidian."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    opinions: list[dict[str, str]] = []

    for agent_key in agents_participants:
        k = agent_key.lower().strip()
        expert = config.PERSONAS.get(k, config.PERSONAS["jarvis"])

        prompt_agent = (
            f"Tu es {expert['nom']} ({expert['role']}) pour {config.UTILISATEUR}.\n"
            f"Domaine : {expert['domaine']}.\n\n"
            f"SUJET SOUMIS AU DÉBAT : '{sujet_complexe}'\n\n"
            "Interviens en 3 points concis :\n"
            "1. Opportunité majeure selon ta spécialité.\n"
            "2. Risque critique ou point de rupture.\n"
            "3. Ta recommandation ferme."
        )

        try:
            avis, _ = router.generer(prompt_agent, "Donne ton avis d'expert.", temperature=0.3)
            opinions.append({"nom": expert["nom"], "role": expert["role"], "avis": avis.strip()})
        except Exception as e:
            opinions.append({"nom": expert["nom"], "role": expert["role"], "avis": f"Indisponible ({e})"})

    retranscription = ""
    for op in opinions:
        retranscription += f"### 👤 Position de [[{op['nom']}]] ({op['role']}) :\n{op['avis']}\n\n"

    prompt_arbitrage = (
        f"Tu es JAJAR, Arbitre Suprême du Studio pour {config.UTILISATEUR}.\n"
        f"Date : {ts}\n\n"
        f"SUJET DU DÉBAT : '{sujet_complexe}'\n\n"
        f"AVIS DES SPÉCIALISTES :\n{retranscription}\n\n"
        "DIRECTIVES D'ARBITRAGE :\n"
        "1. Tranche le paradoxe dialectique.\n"
        "2. Rends :\n"
        "   ### ⚖️ L'ARBITRAGE FERME DE JAJAR\n"
        "   ### 📋 PLAN D'ACTION IMMÉDIAT"
    )

    try:
        verdict, _ = router.generer(prompt_arbitrage, "Arbitre le débat.", temperature=0.1)

        dossier_debats = config.VAULT_DIR / "01_Projets" / "Debats_Strategiques"
        dossier_debats.mkdir(parents=True, exist_ok=True)
        f_nom = f"debat_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        f_debat = dossier_debats / f_nom

        frontmatter = f"---\ntitle: \"Débat : {sujet_complexe}\"\ndate: {ts}\ntags: [\"debat\", \"studio\", \"arbitrage\"]\n---\n\n"
        contenu = f"{frontmatter}# Débat Stratégique : {sujet_complexe}\n\n{retranscription}\n## Verdict Final\n\n{verdict}\n"
        f_debat.write_text(contenu, encoding="utf-8")

        return f"🏛️ **Débat Multi-Agents Arbitré :**\n\n{retranscription}{verdict}\n\n📂 *Archivé dans :* `[[{f_debat.stem}]]`"
    except Exception as e:
        return f"Erreur arbitrage débat : {e}"
