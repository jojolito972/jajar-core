"""
core/fact_checker.py — Vérification physique des assertions du modèle contre le système hôte.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

import config
from core.schemas import FaitVerifie

logger: Final[logging.Logger] = logging.getLogger("jajar.fact_checker")


class FactChecker:
    def verifier_affirmation_systeme(self, affirmation: str) -> FaitVerifie:
        aff_clean = affirmation.strip()

        for mot in aff_clean.split():
            if "/" in mot and not mot.startswith("http"):
                p = Path(mot.strip("'`\",;()")).expanduser()
                if p.exists():
                    desc = f"{p.stat().st_size} octets" if p.is_file() else "répertoire valide"
                    return FaitVerifie(
                        affirmation=aff_clean,
                        statut="verifie",
                        source=f"fichier:{p}",
                        preuve_brute=f"FS vérifié : {desc} (mtime: {int(p.stat().st_mtime)})",
                    )

        if "192.168." in aff_clean or "localhost" in aff_clean or "127.0.0.1" in aff_clean:
            return FaitVerifie(
                affirmation=aff_clean,
                statut="hypothese",
                source="reseau_declare",
                preuve_brute="Cible déclarée dans le contexte sans sondage actif",
            )

        return FaitVerifie(
            affirmation=aff_clean,
            statut="hypothese",
            source=None,
            preuve_brute=None,
        )

    def filtrer_faits_non_verifies(self, faits: list[FaitVerifie]) -> tuple[list[FaitVerifie], list[FaitVerifie]]:
        verifies = []
        douteux = []
        for f in faits:
            if f.source and f.statut == "verifie":
                verifies.append(f)
            else:
                douteux.append(f)
        return verifies, douteux


fact_checker: Final[FactChecker] = FactChecker()
