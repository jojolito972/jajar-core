from __future__ import annotations

"""
tools/delegation_tools.py — Outil universel de délégation de tâches inter-agents.
Permet à n'importe quel Persona de commander un travail asynchrone à un autre spécialiste.
"""

import asyncio
from typing import Final

import config
from config import SecurityTier
from core.orchestrator_bus import TaskPriority, orchestrator_bus
from core.tools_registry import outil


@outil(tier=SecurityTier.AUTO)
def deleguer_travail_specialiste(agent_cible: str, mission_exacte: str, priorite_haute: bool = False) -> str:
    """Délègue une mission complexe en arrière-plan à un agent spécialiste (ansel, alba, tesla, ray, cleo, alfred, indiana)."""
    cible = agent_cible.lower().strip()
    if cible not in config.PERSONAS:
        return f"⚠️ Agent cible inconnu : `{cible}`. Disponibles : {', '.join(config.PERSONAS.keys())}"

    prio = TaskPriority.HIGH if priorite_haute else TaskPriority.NORMAL

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            task_id = pool.submit(
                lambda: asyncio.run(
                    orchestrator_bus.deleguer_tache(
                        source_agent="jarvis",
                        target_agent=cible,
                        instruction=mission_exacte,
                        priority=prio,
                    )
                )
            ).result()
    else:
        task_id = loop.run_until_complete(
            orchestrator_bus.deleguer_tache(
                source_agent="jarvis",
                target_agent=cible,
                instruction=mission_exacte,
                priority=prio,
            )
        )

    expert = config.PERSONAS[cible]
    return f"🚀 **Mission déléguée à {expert['nom']} en arrière-plan (ID: `{task_id}`) !**\nDenis peut continuer à me parler librement. Je notifierai le résultat dès que {expert['nom']} aura terminé."
