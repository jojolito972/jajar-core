from __future__ import annotations

"""
core/engine.py — Moteur JAJAR Unifié (Vérité Radicale, Discernement Contextuel & Garde-Fou AST).
Exporte : run_agent, formuler_5_options, obtenir_decision, extraire_json_securise.
"""

import ast
import datetime
import json
import logging
import random
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Final, Optional

import config
from core.dialectic_engine import dialectic_engine
from core.fact_checker import fact_checker
from core.llm_router import router
from core.schemas import Decision, FaitVerifie, SolutionConcrete
from core.skills_engine import skill_registry
from core.state import AgentState
from core.tools_registry import (
    ConfirmCallback,
    description_outils_pour_prompt,
    executer_outil,
)
from core.tracing import AgentTrace

logger: Final[logging.Logger] = logging.getLogger("jajar.engine")

REPONSES_SALUTATIONS_DENIS: Final[list[str]] = [
    "Salut Denis ! Tous les systèmes sont parés. Sur quoi avançons-nous ?",
    "Hello Denis ! Prêt pour la suite. Quelle est la mission ?",
    "Salut Denis ! Toujours au poste. Qu'est-ce qu'on attaque aujourd'hui ?",
    "Yo Denis ! Studio JAJAR 100% opérationnel. Je t'écoute !",
]


def _obtenir_date_fr_exacte() -> str:
    JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    now = datetime.datetime.now()
    return f"{JOURS[now.weekday()]} {now.day} {MOIS[now.month - 1]} {now.year}, il est {now.strftime('%H:%M:%S')}."


def _detecter_requete_triviale(tache: str) -> bool:
    t_clean = tache.strip().lower().rstrip("!?.")
    salutations = {
        "salut", "bonjour", "bonsoir", "coucou", "hello", "hi", "yo",
        "ca va", "ça va", "merci", "ciao", "buongiorno", "slt", "bjr"
    }
    if t_clean in salutations:
        return True
    mots = t_clean.split()
    return len(mots) <= 2 and any(s in t_clean for s in salutations)


def _nettoyer_prompt_utilisateur(texte_brut: str) -> str:
    if not texte_brut:
        return ""
    lignes = texte_brut.splitlines()
    lignes_uniques = []
    for l in lignes:
        l_str = l.strip()
        if not lignes_uniques or l_str != lignes_uniques[-1]:
            lignes_uniques.append(l_str)
    return "\n".join(lignes_uniques).strip()


def _compiler_skills_context(tache: str) -> str:
    try:
        skills = skill_registry.chercher_skills_pertinents(tache)
        if not skills:
            return ""
        lignes = ["\n--- 🧠 COMPÉTENCES ACQUISES MOBILISABLES ---"]
        for s in skills:
            lignes.append(f"• SKILL: [{s.nom}] ➔ {' -> '.join(s.recette_etapes)}")
        return "\n".join(lignes) + "\n"
    except Exception:
        return ""


def _archiver_faits_vie_en_arriere_plan(dernier_user: str, dernier_bot: str, persona: str) -> None:
    if len(dernier_user.split()) < 3 or _detecter_requete_triviale(dernier_user):
        return

    def _worker():
        try:
            ts_jour = datetime.datetime.now().strftime("%Y-%m-%d")
            ts_heure = datetime.datetime.now().strftime("%H:%M:%S")

            prompt = (
                f"Scribe de {config.UTILISATEUR} :\n"
                f"- Denis : \"{dernier_user}\"\n- {persona.upper()} : \"{dernier_bot}\"\n\n"
                "Extrais uniquement les faits utiles et durables au format JSON :\n"
                "{\"utile\": true, \"synthese\": \"...\"} ou {\"utile\": false}"
            )
            res_raw, _ = router.generer(prompt, "Extraction faits.", temperature=0.1)
            res_clean = re.sub(r"^```(?:json)?", "", res_raw.strip()).removesuffix("```").strip()
            data = json.loads(res_clean)

            if data.get("utile") and data.get("synthese"):
                dossier_vie = config.VAULT_DIR / "06_Memoire_Vie"
                dossier_vie.mkdir(parents=True, exist_ok=True)
                f_vie = dossier_vie / "Faits_et_Reflexions_Denis.md"
                with open(f_vie, "a", encoding="utf-8") as f:
                    f.write(f"- `{ts_jour} {ts_heure}` **[{persona.upper()}]** : {data['synthese']}\n")
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def extraire_json_securise(texte: str) -> dict[str, Any]:
    if not texte:
        return {"action": "final_answer", "answer": "Opération terminée."}

    texte_net = texte.strip()
    texte_net = re.sub(r"^```(?:json)?", "", texte_net, flags=re.IGNORECASE)
    texte_net = re.sub(r"```$", "", texte_net).strip()

    try:
        res = json.loads(texte_net, strict=False)
        if isinstance(res, dict):
            return res
    except Exception:
        pass

    match_dict = re.search(r"(\{[\s\S]*\})", texte_net)
    if match_dict:
        try:
            res = json.loads(match_dict.group(1), strict=False)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

    return {
        "thinking": "Analyse directe.",
        "action": "final_answer",
        "tool_name": None,
        "tool_args": {},
        "answer": texte_net,
        "faits": [],
        "doute_exprime": None,
    }


def valider_syntaxe_code_python(nom_fichier: str, contenu: str) -> tuple[bool, str]:
    if not nom_fichier.endswith(".py"):
        return True, ""
    try:
        ast.parse(contenu)
        return True, ""
    except SyntaxError as err:
        return False, f"Erreur syntaxe Python ligne {err.lineno} : {err.msg}"


_POSTURE_SYSTEME_BASE: Final[str] = f"""\
Tu es JAJAR (ou l'agent spécialiste actif du studio), l'allié opérationnel d'élite de {config.UTILISATEUR}.
Connecté EN DIRECT sur son Mac (/Users/denmac).

═══════════════════════════════════════════════════════════════════════════════
DIRECTIVES OPÉRATIONNELLES DE DISCERNEMENT ET DE QUALITÉ :
═══════════════════════════════════════════════════════════════════════════════
1. DISCERNEMENT DU CONTENU :
   - Si Denis partage une information ou un résumé de texte : analyse, donne ton avis critique et attends. N'écris pas de fichiers sans ordre explicite.
2. PROTOCOLE D'OPTIONS ÉQUILIBRÉ :
   - Ne propose 5 options QUE si Denis te demande expressément des idées ou un arbitrage.
   - S'il s'agit d'une instruction claire ou d'une validation : EXÉCUTE DIRECTEMENT SANS REFAIRE DE LISTE.
3. EXIGENCE ABSOLUE SUR LE CODE GÉNÉRÉ :
   - Tout script écrit via `ecrire_fichier` doit être COMPLET, TESTÉ et SYNTAXIQUEMENT PARFAIT.
4. VÉRITÉ FACTUELLE :
   - Si un outil échoue : signale-le immédiatement. Ne prétends jamais qu'une action a réussi si l'outil a renvoyé une erreur.
═══════════════════════════════════════════════════════════════════════════════
"""

_FORMAT_SORTIE_JSON: Final[str] = """\
FORMAT DE SORTIE JSON STRICT OBLIGATOIRE :
{
  "thinking": "Ton analyse critique, mesurée et sans emballement",
  "est_dilemme_ou_idee": false,
  "solutions": [],
  "synergie_recommandee": null,
  "action": "tool_call" | "final_answer" | "ask_clarification",
  "tool_name": "nom_outil_ou_null",
  "tool_args": {},
  "answer": "Ta réponse structurée, concise et pertinente pour Denis",
  "faits": [{"affirmation": "...", "statut": "verifie" | "hypothese", "source": "fichier:..."}],
  "doute_exprime": null
}
"""


def _construire_posture_systeme(persona: str, mode_operationnel: str, contexte_memoire: str) -> str:
    expert = config.PERSONAS.get(persona, config.PERSONAS["jarvis"])
    date_actuelle = _obtenir_date_fr_exacte()
    outils_txt = description_outils_pour_prompt(persona)
    moteur_actuel = "LOCAL METAL (Gemma 4)" if router.mode_actif == "local" else ("NVIDIA NIM H100" if router.mode_actif == "nvidia" else "CLOUD GOOGLE GEMINI")

    return f"""\
Tu es JAJAR (incarnant {expert['nom']}, {expert['role']}) pour {config.UTILISATEUR} sur son Mac (/Users/denmac).
⏰ HORODATAGE : {date_actuelle} | MODE : {mode_operationnel.upper()}
🔒 MOTEUR D'INFÉRENCE ACTIF : [{moteur_actuel}]

{_POSTURE_SYSTEME_BASE}

OUTILS DISPONIBLES :
{outils_txt}

{_FORMAT_SORTIE_JSON}

--- CONTEXTE MÉMOIRE ACTIVE ---
{contexte_memoire}
"""


def formuler_5_options(question: str, persona: str = "jarvis") -> tuple[str, float, str]:
    t_debut = time.time()
    expert = config.PERSONAS.get(persona.lower(), config.PERSONAS["jarvis"])
    date_actuelle = _obtenir_date_fr_exacte()
    contexte_skills = _compiler_skills_context(question)

    prompt = (
        f"{_POSTURE_SYSTEME_BASE}\n"
        f"Tu incarnes {expert['nom']} ({expert['role']}) pour {config.UTILISATEUR}.\n"
        f"⏰ HORODATAGE : {date_actuelle}\n"
        f"{contexte_skills}\n"
        "DIRECTIVES : Formule 5 options concrètes sur des lignes séparées et ton choix synergique argumenté.\n\n"
        f"{_FORMAT_SORTIE_JSON}"
    )

    try:
        reponse_brute, moteur = router.generer(
            system_prompt=prompt,
            user_prompt=f"Demande / Idée de {config.UTILISATEUR} : {question}",
            temperature=0.2,
        )
        parsed = extraire_json_securise(reponse_brute)
        reponse_finale = parsed.get("answer", reponse_brute) if isinstance(parsed, dict) else reponse_brute
        chrono = round(time.time() - t_debut, 2)
        return reponse_finale, chrono, moteur.replace("cloud:", "").replace("local:", "").replace("nvidia:", "")
    except Exception as e:
        logger.error(f"Erreur formulation solutions : {e}")
        chrono = round(time.time() - t_debut, 2)
        return f"Erreur technique : {e}", chrono, "gemini"


def obtenir_decision(system_prompt: str, user_prompt: str) -> tuple[Decision, str, int]:
    brut, moteur = router.generer(system_prompt, user_prompt, temperature=0.15)
    data = extraire_json_securise(brut)

    action = data.get("action", "final_answer")
    tool_name = data.get("tool_name") if action == "tool_call" else None
    tool_args = data.get("tool_args", {})
    if not isinstance(tool_args, dict):
        tool_args = {}

    decision = Decision(
        thinking=str(data.get("thinking", "")),
        est_dilemme_ou_idee=bool(data.get("est_dilemme_ou_idee", False)),
        solutions=[],
        synergie_recommandee=data.get("synergie_recommandee"),
        action=action,
        tool_name=tool_name,
        tool_args=tool_args,
        answer=str(data.get("answer") or data.get("thinking") or ""),
        confidence="haute",
        faits=[],
        doute_exprime=data.get("doute_exprime"),
    )
    decision.validate_coherence()
    tokens_estimes = max(1, (len(system_prompt) + len(user_prompt) + len(brut)) // 4)
    return decision, moteur, tokens_estimes


def run_agent(
    task: str,
    persona: str = "jarvis",
    contexte_memoire: str = "",
    mode_operationnel: str = "auto",
    confirmer: ConfirmCallback = None,
    max_steps: int = 15,
    tracer: AgentTrace | None = None,
    callback_ui: Optional[Callable[[str, str], None]] = None,
) -> tuple[str, int, float, str]:
    t_debut = time.time()
    persona = persona.lower().strip()
    if persona not in config.PERSONAS:
        persona = "jarvis"

    task_propre = _nettoyer_prompt_utilisateur(task)

    tracer = tracer or AgentTrace(persona)
    state = AgentState(task=task_propre, persona=persona, max_steps=max_steps)
    state.add("user", task_propre)

    if _detecter_requete_triviale(task_propre):
        reponse_triviale = random.choice(REPONSES_SALUTATIONS_DENIS)
        tracer.log("final_answer", reponse_triviale, status="ok")
        state.sauvegarder_session(task_propre, reponse_triviale)
        chrono = round(time.time() - t_debut, 3)
        return reponse_triviale, 15, chrono, f"{router.mode_actif}:fast-gate"

    system_prompt = _construire_posture_systeme(persona, mode_operationnel, contexte_memoire or state.context_summary())

    tokens_total = 0
    moteur_final = router.mode_actif
    trace_actions_reussies: list[dict[str, Any]] = []
    trace_erreurs_outils: list[str] = []

    try:
        for step in range(max_steps):
            state.verifier_et_compresser(tracer=tracer)

            user_prompt = f"Demande de {config.UTILISATEUR} : {task_propre}\n\nContexte d'exécution :\n{state.context_summary()}"
            decision, moteur_final, tokens_etape = obtenir_decision(system_prompt, user_prompt)
            tokens_total += tokens_etape

            if decision.thinking:
                tracer.log("thinking", f"[{moteur_final}] {decision.thinking}")
                if callback_ui:
                    callback_ui("thinking", decision.thinking)

            # 1. Exécution d'Outil avec validation AST
            if decision.action == "tool_call" and decision.tool_name:
                outil_nom = decision.tool_name
                args = decision.tool_args

                if outil_nom in ("ecrire_fichier", "ecrire_et_tester_dans_bac_a_sable"):
                    chemin = str(args.get("chemin_fichier") or args.get("nom_fichier") or "")
                    contenu = str(args.get("contenu", ""))
                    valide, msg_ast = valider_syntaxe_code_python(chemin, contenu)
                    if not valide:
                        err_ast = f"⛔ Échec validation AST : Le code pour '{chemin}' contient une erreur ({msg_ast})."
                        state.add("tool_result", err_ast)
                        tracer.log("error", err_ast, status="warning")
                        continue

                tracer.log("tool_call", f"{outil_nom}({args})")
                if callback_ui:
                    callback_ui("tool_call", f"{outil_nom} {json.dumps(args, ensure_ascii=False)}")

                resultat = executer_outil(outil_nom, args, persona, confirmer)
                res_str = str(resultat)

                est_echec = (
                    res_str.startswith("ERREUR") or 
                    res_str.startswith("⚠️") or 
                    res_str.startswith("⛔") or 
                    "timed out" in res_str.lower()
                )

                state.add("assistant", decision.model_dump_json())

                if est_echec:
                    trace_erreurs_outils.append(f"{outil_nom} : {res_str}")
                    tracer.log("error", res_str, status="warning")
                    state.add("tool_result", f"[ÉCHEC FACTUEL] {res_str}")
                else:
                    tracer.log("result", res_str[:200], status="ok")
                    state.add("tool_result", res_str)
                    trace_actions_reussies.append({"outil": outil_nom, "args": args})

                if callback_ui:
                    callback_ui("result", res_str)
                continue

            # 2. Réponse Finale avec Garde-Fou
            if decision.action == "final_answer" or not decision.tool_name:
                reponse_rendue = decision.answer or decision.thinking or "Opération terminée."

                if trace_erreurs_outils and any(w in reponse_rendue.lower() for w in ("succès", "c'est fait", "exécuté avec succès")):
                    reponse_rendue = (
                        f"⚠️ **Rapport d'incident factuel :** L'opération n'a pas pu aboutir.\n\n"
                        f"Détail des blocages constatés :\n" +
                        "\n".join(f"- `{err}`" for err in trace_erreurs_outils)
                    )

                tracer.log("final_answer", reponse_rendue, status="ok")
                state.sauvegarder_session(task_propre, reponse_rendue)
                chrono_total = round(time.time() - t_debut, 2)
                return reponse_rendue, tokens_total, chrono_total, moteur_final

        state.sauvegarder_session(task_propre, "Limite d'étapes atteinte.")
        chrono_total = round(time.time() - t_debut, 2)
        return "J'ai terminé les opérations demandées.", tokens_total, chrono_total, moteur_final

    except KeyboardInterrupt:
        chrono_total = round(time.time() - t_debut, 2)
        state.sauvegarder_session(task_propre, "Interrompu par Denis.")
        return "🛑 **Opération interrompue par Denis.**", tokens_total, chrono_total, moteur_final
    except Exception as e:
        logger.error(f"Erreur run_agent : {e}")
        chrono_total = round(time.time() - t_debut, 2)
        return f"Erreur technique : {e}", tokens_total, chrono_total, moteur_final
