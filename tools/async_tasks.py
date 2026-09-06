"""
tools/async_tasks.py — Outils permettant de délester les tâches lourdes en arrière-plan.
"""

from __future__ import annotations

import config
from config import SecurityTier
from core.background_worker import worker_manager
from core.tools_registry import outil


@outil(tier=SecurityTier.AUTO)
def lancer_deep_research_arriere_plan(sujet: str, profondeur: int = 3, max_sources: int = 6) -> str:
    """Lance un Deep Research en arrière-plan sans bloquer la conversation avec notification Telegram à la fin."""
    from tools.deep_research import recherche_profonde_web
    return worker_manager.lancer_en_arriere_plan(
        nom_tache=f"Deep Research : {sujet[:35]}",
        fonction_cible=recherche_profonde_web,
        args=(sujet, profondeur, max_sources),
        notifier_telegram=True,
    )


@outil(tier=SecurityTier.AUTO)
def generer_podcast_notebooklm_arriere_plan(notebook_id: str, instructions: str = "Focus on strategic decisions") -> str:
    """Déclenche la génération d'un podcast audio NotebookLM en tâche de fond."""
    from tools.notebooklm_tool import generer_podcast_audio_notebooklm
    return worker_manager.lancer_en_arriere_plan(
        nom_tache=f"Podcast NotebookLM ({notebook_id[:8]})",
        fonction_cible=generer_podcast_audio_notebooklm,
        args=(notebook_id, instructions),
        notifier_telegram=True,
    )


@outil(tier=SecurityTier.AUTO)
def verifier_taches_arriere_plan() -> str:
    """Consulte l'état de toutes les tâches d'arrière-plan."""
    return worker_manager.lister_statut_taches()
