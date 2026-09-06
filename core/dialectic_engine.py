"""
core/dialectic_engine.py — Moteur de raisonnement contradictoire (Thèse / Antithèse / Synthèse).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Final

import config
from core.llm_router import router
from core.schemas import FaitVerifie, PenseeDialectique

logger: Final[logging.Logger] = logging.getLogger("jajar.dialectic")


class DialecticEngine:
    def __init__(self) -> None:
        self.router = router

    def raisonner(self, probleme: str, contexte: str = "", persona: str = "jarvis") -> PenseeDialectique:
        expert = config.PERSONAS.get(persona.lower(), config.PERSONAS["jarvis"])

        prompt_dialectique = (
            f"Tu es le Module de Réflexion Dialectique du Studio JAJAR pour {config.UTILISATEUR}.\n"
            f"Tu analyses pour {expert['nom']} le problème suivant : '{probleme}'\n"
            f"Contexte d'exécution :\n{contexte[:4000]}\n\n"
            "STRUCTURE DIALECTIQUE STRICTE EN 4 ÉTAPES :\n"
            "1. THÈSE : L'approche directe la plus immédiate.\n"
            "2. ANTITHÈSE : 3 objections critiques, risques ou points de rupture invalidant la thèse.\n"
            "3. SYNTHÈSE : Arbitrage pragmatique formulant la solution révisée.\n"
            "4. ÉPISTÉMOLOGIE : Extraction des affirmations factuelles et des incertitudes assumées.\n\n"
            "FORMAT JSON STRICT OBLIGATOIRE :\n"
            "{\n"
            '  "these": "...",\n'
            '  "antithese": "...",\n'
            '  "synthese": "...",\n'
            '  "doutes": ["doute 1", "doute 2"],\n'
            '  "faits": [\n'
            '    {"affirmation": "...", "statut": "verifie" | "hypothese" | "inverifiable", "source": "fichier:..." | null}\n'
            "  ],\n"
            '  "niveau_certitude": "preuve" | "forte_presomption" | "hypothese" | "doute_majeur"\n'
            "}"
        )

        try:
            res_raw, _ = self.router.generer(
                system_prompt=prompt_dialectique,
                user_prompt=f"Problème soumis : {probleme}",
                temperature=0.2,
            )
            res_clean = re.sub(r"^```(?:json)?", "", res_raw.strip()).removesuffix("```").strip()
            data = json.loads(res_clean)

            faits_objs = []
            for f in data.get("faits", []):
                try:
                    faits_objs.append(FaitVerifie(**f))
                except Exception:
                    pass

            return PenseeDialectique(
                these=data.get("these", "Approche primaire."),
                antithese=data.get("antithese", "Objections identifiées."),
                synthese=data.get("synthese", "Synthèse arbitrée."),
                doutes=data.get("doutes", []),
                faits_evalues=faits_objs,
                niveau_certitude=data.get("niveau_certitude", "hypothese"),
            )
        except Exception as e:
            logger.warning(f"Repli dialectique : {e}")
            return PenseeDialectique(
                these=f"Traitement direct de : {probleme[:80]}",
                antithese="Incertitude sur les données fournies.",
                synthese=f"Exécution prudente pour {config.UTILISATEUR}.",
                doutes=["Validation manuelle recommandée."],
                faits_evalues=[],
                niveau_certitude="hypothese",
            )


dialectic_engine: Final[DialecticEngine] = DialecticEngine()
