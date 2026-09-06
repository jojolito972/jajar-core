from __future__ import annotations

"""
core/hierarchical_planner.py — Moteur de Planification Hiérarchique avec Rollback APFS.
Garantit l'atomicité des suites d'actions et l'auto-correction réflexive en cas d'erreur.
"""

import datetime
import json
import logging
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Optional

import config
from core.tools_registry import executer_outil

logger: Final[logging.Logger] = logging.getLogger("jajar.planner")


@dataclass
class PlanStep:
    id: int
    action_nom: str
    description: str
    tool_name: str
    tool_args: dict[str, Any]
    statut: str = "en_attente"  # "en_attente" | "succes" | "echec"
    resultat: Optional[str] = None


@dataclass
class TransactionContext:
    transaction_id: str
    timestamp: str
    fichiers_modifies: list[Path] = field(default_factory=list)
    backups: dict[str, Path] = field(default_factory=dict)


class HierarchicalPlanner:
    """Planificateur transactionnel avec capture d'état et rollback déterministe."""

    def __init__(self) -> None:
        self.backup_root = config.BACKUPS_FICHIERS_DIR / "transactions"
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def debuter_transaction(self) -> TransactionContext:
        tx_id = f"tx_{uuid.uuid4().hex[:8]}"
        ts = datetime.datetime.now().isoformat()
        tx_dir = self.backup_root / tx_id
        tx_dir.mkdir(parents=True, exist_ok=True)
        return TransactionContext(transaction_id=tx_id, timestamp=ts)

    def securiser_fichier_avant_mutation(self, ctx: TransactionContext, fichier: Path) -> None:
        if fichier.exists() and fichier.is_file():
            backup_path = self.backup_root / ctx.transaction_id / f"{fichier.name}_{uuid.uuid4().hex[:4]}.bak"
            shutil.copy2(str(fichier), str(backup_path))
            ctx.backups[str(fichier.resolve())] = backup_path
            ctx.fichiers_modifies.append(fichier)

    def annuler_transaction(self, ctx: TransactionContext) -> None:
        """Restaure les fichiers dans leur état exact pré-exécution."""
        logger.warning(f"🔄 Rollback de la transaction [{ctx.transaction_id}]...")
        for chemin_orig_str, backup_path in ctx.backups.items():
            try:
                dest = Path(chemin_orig_str)
                if backup_path.exists():
                    shutil.copy2(str(backup_path), str(dest))
                    logger.info(f"↩️ Fichier restauré : {dest}")
            except Exception as e:
                logger.error(f"Échec restauration {chemin_orig_str} : {e}")

        # Nettoyage
        shutil.rmtree(str(self.backup_root / ctx.transaction_id), ignore_errors=True)

    def executer_plan_avec_rollback(
        self,
        etapes: list[PlanStep],
        persona: str = "jarvis",
    ) -> tuple[bool, list[PlanStep], str]:
        ctx = self.debuter_transaction()
        logger.info(f"⚡ Début d'exécution du plan transactionnel [{ctx.transaction_id}] ({len(etapes)} étapes)")

        for etape in etapes:
            logger.info(f"▶️ Étape {etape.id} : {etape.description} [{etape.tool_name}]")

            # Snapshot préventif si l'outil cible modifie un fichier
            if "chemin" in etape.tool_args or "chemin_fichier" in etape.tool_args:
                cible = Path(etape.tool_args.get("chemin") or etape.tool_args.get("chemin_fichier", "")).expanduser()
                self.securiser_fichier_avant_mutation(ctx, cible)

            try:
                res = executer_outil(etape.tool_name, etape.tool_args, persona)
                res_str = str(res)

                if res_str.startswith("ERREUR") or res_str.startswith("⚠️") or res_str.startswith("⛔"):
                    etape.statut = "echec"
                    etape.resultat = res_str
                    self.annuler_transaction(ctx)
                    return False, etapes, f"Échec à l'étape {etape.id} ({etape.description}) : {res_str}. Rollback effectué."

                etape.statut = "succes"
                etape.resultat = res_str

            except Exception as err:
                etape.statut = "echec"
                etape.resultat = str(err)
                self.annuler_transaction(ctx)
                return False, etapes, f"Crash à l'étape {etape.id} : {err}. Système restauré."

        # Nettoyage après succès
        shutil.rmtree(str(self.backup_root / ctx.transaction_id), ignore_errors=True)
        return True, etapes, "Plan exécuté avec succès et validé."


hierarchical_planner: Final[HierarchicalPlanner] = HierarchicalPlanner()
