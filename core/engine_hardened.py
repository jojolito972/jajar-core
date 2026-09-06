"""
core/engine_hardened.py — Moteur d'Inférence et d'Orchestration Haute Fiabilité.
Intègre le typage Pydantic v2 natif, la résilience aux erreurs d'outils et l'arbitrage dialectique.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Final, Optional

from google.genai import types
from pydantic import BaseModel, Field

import config
from core.schemas import Decision, FaitVerifie, PenseeDialectique
from core.skills_engine import skill_registry
from core.state import AgentState
from core.tools_registry import (
    ConfirmCallback,
    REGISTRE_OUTILS,
    description_outils_pour_prompt,
    executer_outil,
)
from core.tracing import AgentTrace

logger: Final[logging.Logger] = logging.getLogger("jajar.engine.hardened")


class DecisionContract(BaseModel):
    thinking: str = Field(..., description="Raisonnement dialectique et déduction factuelle.")
    est_dilemme_ou_idee: bool = Field(default=False, description="True si arbitrage requis.")
    action: str = Field(..., description="'tool_call' | 'final_answer' | 'ask_clarification'")
    tool_name: Optional[str] = Field(default=None, description="Nom exact de l'outil cible.")
    tool_args: dict[str, Any] = Field(default_factory=dict, description="Arguments de l'outil.")
    answer: str = Field(..., description="Réponse finale rédigée pour l'utilisateur.")
    doute_exprime: Optional[str] = Field(default=None, description="Point de doute ou d'incertitude.")
    faits: list[dict[str, Any]] = Field(default_factory=list, description="Assertions vérifiées extraites.")


class HardenedEngine:
    def __init__(self) -> None:
        self.client = config.GENAI_CLIENT
        self.model_name = config.MODELE_TEXTE_GEMINI

    @staticmethod
    def _obtenir_date_fr() -> str:
        jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        now = time.localtime()
        return f"{jours[now.tm_wday]} {now.tm_mday} {mois[now.tm_mon - 1]} {now.tm_year}, {time.strftime('%H:%M:%S', now)}"

    def compiler_system_prompt(self, persona: str, mode_op: str, contexte_memoire: str) -> str:
        expert = config.PERSONAS.get(persona.lower(), config.PERSONAS["jarvis"])
        outils_desc = description_outils_pour_prompt(persona)
        
        return (
            f"Tu es JAJAR (incarnant {expert['nom']}, {expert['role']}) sur le Mac de {config.UTILISATEUR}.\n"
            f"HORODATAGE : {self._obtenir_date_fr()}\n"
            f"DOMAINE : {expert['domaine']} | MODE OPÉRATIONNEL : {mode_op.upper()}\n\n"
            f"═══════════════════════════════════════════════════════════════════════════════\n"
            f"DIRECTIVES OPÉRATIONNELLES STRICTES (ZERO-SIMULATION) :\n"
            f"1. Si une action système est nécessaire, utilise l'outil approprié. Interdiction d'inventer des sorties.\n"
            f"2. Pour les dilemmes, formule une synthèse tranchée sans hésitation passive.\n"
            f"3. La sortie DOIT être rigoureusement conforme au schéma d'état interne.\n"
            f"═══════════════════════════════════════════════════════════════════════════════\n\n"
            f"OUTILS DISPONIBLES :\n{outils_desc}\n\n"
            f"CONTEXTE MÉMOIRE :\n{contexte_memoire}"
        )

    def executer_tour_decision(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.15,
    ) -> tuple[Decision, int]:
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=DecisionContract,
                ),
            )
            raw_text = response.text or "{}"
            data = json.loads(raw_text)
            
            faits_objs = [
                FaitVerifie(
                    affirmation=f.get("affirmation", ""),
                    statut=f.get("statut", "hypothese"),
                    source=f.get("source"),
                    preuve_brute=f.get("preuve_brute"),
                )
                for f in data.get("faits", []) if isinstance(f, dict)
            ]

            action_valide = data.get("action", "final_answer")
            if action_valide not in ("tool_call", "final_answer", "ask_clarification"):
                action_valide = "final_answer"

            tool_name = data.get("tool_name")
            if action_valide == "tool_call" and (not tool_name or tool_name not in REGISTRE_OUTILS):
                action_valide = "final_answer"
                tool_name = None

            decision = Decision(
                thinking=data.get("thinking", ""),
                est_dilemme_ou_idee=bool(data.get("est_dilemme_ou_idee", False)),
                solutions=[],
                synergie_recommandee=None,
                action=action_valide,
                tool_name=tool_name,
                tool_args=data.get("tool_args", {}) if isinstance(data.get("tool_args"), dict) else {},
                answer=data.get("answer") or data.get("thinking") or "Opération complétée.",
                confidence="haute",
                faits=faits_objs,
                doute_exprime=data.get("doute_exprime"),
            )
            
            tokens_utilises = int(getattr(response, "usage_metadata", {}).get("total_token_count", 0))
            if tokens_utilises == 0:
                tokens_utilises = (len(system_prompt) + len(user_prompt) + len(raw_text)) // 4

            return decision, tokens_utilises

        except Exception as e:
            logger.error(f"Échec critique inférence Gemini : {e}")
            fallback_decision = Decision(
                thinking=f"Repli d'urgence suite à une erreur : {e}",
                action="final_answer",
                answer=f"⚠️ Incident technique lors de la génération : {e}",
            )
            return fallback_decision, 50

    def run(
        self,
        task: str,
        persona: str = "jarvis",
        contexte_memoire: str = "",
        mode_operationnel: str = "auto",
        confirmer: ConfirmCallback = None,
        max_steps: int = 12,
        tracer: AgentTrace | None = None,
        callback_ui: Optional[Callable[[str, str], None]] = None,
    ) -> tuple[str, int, float, str]:
        t0 = time.time()
        tracer = tracer or AgentTrace(persona)
        state = AgentState(task=task, persona=persona, max_steps=max_steps)
        state.add("user", task)

        # Fast path pour les salutations triviales
        t_clean = task.strip().lower()
        if t_clean in {"salut", "bonjour", "hello", "hi", "coucou"} and len(state.history) <= 1:
            rep = f"Bonjour {config.UTILISATEUR}. Systèmes opérationnels. Quel est votre ordre ?"
            tracer.log("final_answer", rep, status="ok")
            state.sauvegarder_session(task, rep)
            return rep, 20, round(time.time() - t0, 2), self.model_name

        system_prompt = self.compiler_system_prompt(persona, mode_operationnel, contexte_memoire or state.context_summary())
        total_tokens = 0
        actions_reussies: list[dict[str, Any]] = []
        echecs_consecutifs: dict[str, int] = {}

        for step in range(max_steps):
            state.verifier_et_compresser(tracer=tracer)
            user_prompt = f"Demande opérationnelle : {task}\n\nContexte d'état :\n{state.context_summary()}"
            
            decision, tokens_step = self.executer_tour_decision(system_prompt, user_prompt)
            total_tokens += tokens_step

            if decision.thinking:
                tracer.log("thinking", decision.thinking)
                if callback_ui:
                    callback_ui("thinking", decision.thinking)

            if decision.action == "tool_call" and decision.tool_name:
                outil_nom = decision.tool_name
                if echecs_consecutifs.get(outil_nom, 0) >= 2:
                    msg_blocage = f"Arrêt de sécurité : L'outil `{outil_nom}` a échoué 2 fois consécutives."
                    state.sauvegarder_session(task, msg_blocage)
                    return msg_blocage, total_tokens, round(time.time() - t0, 2), self.model_name

                tracer.log("tool_call", f"{outil_nom}({json.dumps(decision.tool_args, ensure_ascii=False)})")
                if callback_ui:
                    callback_ui("tool_call", f"{outil_nom} {json.dumps(decision.tool_args, ensure_ascii=False)}")

                res_outil = executer_outil(outil_nom, decision.tool_args, persona, confirmer)
                state.add("assistant", json.dumps({"action": "tool_call", "tool": outil_nom, "args": decision.tool_args}))

                res_str = str(res_outil)
                if res_str.startswith("ERREUR") or res_str.startswith("⚠️") or res_str.startswith("⛔"):
                    tracer.log("error", res_str, status="warning")
                    echecs_consecutifs[outil_nom] = echecs_consecutifs.get(outil_nom, 0) + 1
                    state.add("tool_result", f"ÉCHEC: {res_str}\nAdapte ta stratégie.")
                else:
                    echecs_consecutifs[outil_nom] = 0
                    tracer.log("result", res_str[:200], status="ok")
                    state.add("tool_result", res_str)
                    actions_reussies.append({"outil": outil_nom, "args": decision.tool_args})

                if callback_ui:
                    callback_ui("result", res_str)
                continue

            if decision.action == "final_answer" or not decision.tool_name:
                reponse_finale = decision.answer
                if decision.doute_exprime:
                    reponse_finale += f"\n\n🔍 **Point de vigilance :** {decision.doute_exprime}"

                if len(actions_reussies) >= 2:
                    skill_registry.distiller_et_apprendre(task, actions_reussies)

                tracer.log("final_answer", reponse_finale, status="ok")
                state.sauvegarder_session(task, reponse_finale)
                return reponse_finale, total_tokens, round(time.time() - t0, 2), self.model_name

        msg_limite = "Limite d'étapes d'exécution atteinte. Opérations interrompues."
        state.sauvegarder_session(task, msg_limite)
        return msg_limite, total_tokens, round(time.time() - t0, 2), self.model_name


hardened_engine: Final[HardenedEngine] = HardenedEngine()
