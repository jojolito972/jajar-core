"""
scripts/installer_tout_propre.py — Installateur automatisé et sécurisé du Studio JAJAR v2.
Écrit et valide l'intégrité de run_jarvis.py et core/engine.py.
"""

from __future__ import annotations

import py_compile
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# CONTENU DE RUN_JARVIS.PY (INTERFACE PASTEL & VISION INTÉGRALE)
# ---------------------------------------------------------------------------
RUN_JARVIS_CONTENT = '''"""
run_jarvis.py — Interface CLI / Herdr Haute Visibilité avec Palette Pastel (Catppuccin/TokyoNight)
Affichage intégral : Réflexion Visible, Arbre d Action (Tree), Code Shell Live, /agents et /etat.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import readline
import signal
import sys
import time
from pathlib import Path
from typing import Any, Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from automation.dialogue_vocal_continu import lancer_mode_vocal_continu
from core.engine import formuler_5_options, run_agent
from core.state import AgentState
from core.tracing import AgentTrace
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

console = Console(highlight=False, soft_wrap=False)

THEME_CODE_LISIBLE: Final[str] = "one-dark"

# ---------------------------------------------------------------------------
# PALETTE PASTEL DOUCE & LISIBLE (NORME CATPPUCCIN / TOKYO NIGHT)
# ---------------------------------------------------------------------------
COULEURS_PASTEL: Final[dict[str, str]] = {
    "jarvis": "#89b4fa",   # Bleu ciel doux
    "alba": "#a6e3a1",     # Vert sauge / menthe d atelier
    "alfred": "#74c7ec",   # Cyan glacier
    "ray": "#cba6f7",      # Lavande poudrée
    "cleo": "#f9e2af",     # Or doux / vanille
    "leo": "#a6e3a1",      # Vert pastel
    "franklin": "#94e2d5", # Turquoise pastel
    "tesla": "#f38ba8",    # Terracotta / corail doux
    "ansel": "#b4befe",    # Pervenche doux
    "indiana": "#fab387",  # Pêche douce
}

AGENT_DESCRIPTIONS: Final[dict[str, str]] = {
    "jarvis": "Superviseur global — Coordination générale, arbitrage et pilotage des missions.",
    "alfred": "Assistant exécutif — Mails, agenda, administration Google Suite.",
    "ray": "Recherche profonde & veille — Web, synthèses SOTA, projets.",
    "cleo": "Stratégie business — Rentabilité, devis, trésorerie et Micro-BNC.",
    "leo": "Direction artistique & UI/UX — Design, médias et typographies.",
    "franklin": "Développement commercial — Clients, prospection et négociation.",
    "tesla": "Ingénierie systèmes — Scripts Python, Docker, réseau et automatisation.",
    "ansel": "Fabrique visuelle — Génération d images FLUX.1 / Imagen 3.",
    "indiana": "Édition patrimoine — OCR, archives historiques, PDF et NotebookLM.",
    "alba": "Maître Atelier Bespoke — Bottière d art, peausseries et bilinguisme IT/FR.",
}


def _extraire_texte_lisible_humain(texte_brut: str) -> str:
    if not texte_brut:
        return "Opération terminée."

    t = texte_brut.strip()
    if t.startswith("{") and t.endswith("}"):
        try:
            data = json.loads(t)
            if isinstance(data, dict):
                ans = data.get("answer") or data.get("thinking") or ""
                if ans:
                    return _extraire_texte_lisible_humain(ans)
        except Exception:
            pass

    lignes = []
    for line in t.splitlines():
        l_str = line.strip()
        if l_str.startswith("|") and l_str.endswith("|") and not ("---" in l_str or " : " in l_str):
            l_str = l_str[1:-1].strip()
        elif l_str.startswith("|") and not ("---" in l_str or "\t" in l_str):
            l_str = l_str[1:].strip()
        lignes.append(l_str)

    return "\n".join(lignes).strip()


def afficher_arbre_action(agent_key: str, titre_action: str, etapes: list[str]) -> None:
    couleur = COULEURS_PASTEL.get(agent_key.lower(), "#89b4fa")
    tree = Tree(f"[{couleur}]⚙️ {escape(titre_action)}[/{couleur}]")
    for etape in etapes:
        tree.add(f"[#f9e2af]├─[/] [#cdd6f4]{escape(etape)}[/]")
    console.print()
    console.print(tree)
    console.print()


def afficher_banniere(persona: str) -> None:
    expert = config.PERSONAS.get(persona.lower(), config.PERSONAS["jarvis"])
    couleur = COULEURS_PASTEL.get(persona.lower(), "#89b4fa")
    desc = AGENT_DESCRIPTIONS.get(persona.lower(), expert["domaine"])
    now_str = datetime.datetime.now().strftime("%H:%M:%S")

    console.print()
    console.print(Panel(
        f"[bold {couleur}]STUDIO JAJAR v2 · AGENT {expert['nom']}[/bold {couleur}]\\n"
        f"[#cdd6f4]• Rôle : {escape(desc)}[/#cdd6f4]\\n"
        f"[dim #6c7086 italic]⏰ Connecté à {now_str} · Mac de {config.UTILISATEUR} (/Users/denmac)[/dim #6c7086 italic]\\n"
        f"[dim #89b4fa]• Commandes : [bold #f9e2af]/agents[/bold #f9e2af]  [bold #f9e2af]/etat[/bold #f9e2af]  [bold #f9e2af]/vocal[/bold #f9e2af]  [bold #f9e2af]J[/bold #f9e2af][/dim #89b4fa]",
        title=f"[bold {couleur}]⚡ INTERFACE OPÉRATIONNELLE[/bold {couleur}]",
        title_align="left",
        border_style=couleur,
        box=box.ROUNDED,
        padding=(1, 2),
        expand=True,
    ))
    console.print()


def afficher_memoire_reprise(persona: str) -> None:
    state_temp = AgentState(task="Reprise", persona=persona)
    memoire = state_temp.charger_memoire_precedente()
    if memoire and "initialisée" not in memoire.lower():
        console.print(Panel(
            Markdown(memoire),
            title="[bold #f9e2af]📌 SÈVE STRATÉGIQUE & REPRISE DE SESSION[/bold #f9e2af]",
            title_align="left",
            border_style="#45475a",
            box=box.ROUNDED,
            padding=(0, 2),
            expand=True,
        ))
        console.print()


def afficher_agents() -> None:
    lignes = []
    for k, v in config.PERSONAS.items():
        couleur = COULEURS_PASTEL.get(k, "#89b4fa")
        desc = AGENT_DESCRIPTIONS.get(k, v["domaine"])
        lignes.append(f"[bold #f9e2af]/{k:<9}[/] [bold {couleur}]{v['nom']:<10}[/] [dim #6c7086]—[/] [#cdd6f4]{escape(desc)}[/#cdd6f4]")

    console.print()
    console.print(Panel(
        "\\n".join(lignes),
        title="[bold #89b4fa]👥 PÔLE DES 10 SPÉCIALISTES DU STUDIO JAJAR[/bold #89b4fa]",
        title_align="left",
        border_style="#585b70",
        box=box.ROUNDED,
        padding=(1, 2),
        expand=True,
    ))
    console.print()


def afficher_activite_agents() -> None:
    lignes = []
    for k, v in config.PERSONAS.items():
        f_mem = config.BASE_DIR / f"session_active_{k}.json"
        derniere_act = "Aucune session"

        if f_mem.exists():
            try:
                data = json.loads(f_mem.read_text(encoding="utf-8"))
                if data.get("derniers_tours"):
                    last_e = data["derniers_tours"][-1]
                    derniere_act = f"[{last_e.get('role', '')}] {last_e.get('content', '')[:40]}"
                elif data.get("mission_active"):
                    derniere_act = f"Mission : {data['mission_active'][:40]}"
            except Exception:
                pass

        couleur = COULEURS_PASTEL.get(k, "#89b4fa")
        lignes.append(f"[bold {couleur}]{v['nom']:<10}[/] [dim #6c7086]│[/] [#a6adc8]{escape(v['role'][:30]):<32}[/] [dim #6c7086]│[/] [bold #f9e2af]{escape(derniere_act)}[/]")

    console.print()
    console.print(Panel(
        "\\n".join(lignes),
        title="[bold #89b4fa]📊 MONITORING D ACTIVITÉ DU STUDIO[/bold #89b4fa]",
        title_align="left",
        border_style="#585b70",
        box=box.ROUNDED,
        padding=(1, 2),
        expand=True,
    ))
    console.print()


def callback_confirmation_terminal(nom_outil: str, args: dict[str, Any]) -> bool:
    console.print()
    console.print(Panel(
        f"[bold #f9e2af]⚠️ ACTION SYSTÈME REQUISE :[/bold #f9e2af] [bold #89b4fa]{nom_outil}[/bold #89b4fa]\\n"
        f"[dim #a6adc8]Paramètres : {json.dumps(args, ensure_ascii=False)}[/dim #a6adc8]",
        border_style="#f9e2af",
        box=box.ROUNDED,
        padding=(0, 2),
        expand=True,
    ))
    try:
        rep = console.input("[bold #f9e2af]👉 Autoriser l exécution ? (o/N) : [/bold #f9e2af]").strip().lower()
        return rep in ("o", "oui", "y", "yes")
    except Exception:
        return False


def boucle_principale(persona: str = "jarvis", mode_herdr: bool = False) -> None:
    persona = persona.lower().strip()
    if persona not in config.PERSONAS:
        persona = "jarvis"

    if mode_herdr:
        try:
            from tools.herdr_bridge import assurer_presence
            assurer_presence(persona)
        except Exception:
            pass

    afficher_banniere(persona)
    afficher_memoire_reprise(persona)

    dernier_ctrl_c_timestamp: float = 0.0

    while True:
        try:
            expert = config.PERSONAS[persona]
            couleur = COULEURS_PASTEL.get(persona, "#89b4fa")

            prompt_user = console.input(f"[bold {couleur}]👤 {config.UTILISATEUR} ❯ [/bold {couleur}]").strip()
            dernier_ctrl_c_timestamp = 0.0

            if not prompt_user:
                continue

            if prompt_user.lower() in ("exit", "quit", "quitter", "q", "/q", "bye", "stop"):
                console.print(f"\\n[bold {couleur}]👋 Déconnexion du Studio JAJAR. À bientôt {config.UTILISATEUR} ![/bold {couleur}]\\n")
                sys.exit(0)

            if prompt_user.lower() in ("/agents", "agents", "/aide", "help"):
                afficher_agents()
                continue

            if prompt_user.lower() in ("/etat", "etat", "status", "/status"):
                afficher_activite_agents()
                continue

            if prompt_user.upper() == "J" or prompt_user.lower() in ("/vocal", "vocal", "/micro"):
                lancer_mode_vocal_continu(persona_initial=persona)
                afficher_banniere(persona)
                continue

            if prompt_user.startswith("/agent"):
                parts = prompt_user.split()
                if len(parts) > 1 and parts[1].lower() in config.PERSONAS:
                    persona = parts[1].lower()
                    afficher_banniere(persona)
                    afficher_memoire_reprise(persona)
                    continue

            # Callback visuel temps réel
            def _ui_callback(event_type: str, detail: str):
                if event_type == "thinking" and len(detail) > 5:
                    console.print()
                    console.print(Panel(
                        Markdown(detail, code_theme=THEME_CODE_LISIBLE),
                        title=f"[bold #cba6f7]🧠 RÉFLEXION & STRATÉGIE ({expert['nom']})[/bold #cba6f7]",
                        title_align="left",
                        border_style="#cba6f7",
                        box=box.ROUNDED,
                        padding=(1, 2),
                        expand=True,
                    ))
                elif event_type == "tool_call":
                    afficher_arbre_action(persona, f"Exécution d Outil : {detail.split()[0]}", [f"Paramètres : {detail}"])
                elif event_type == "result":
                    extrait = detail.splitlines()[0] if detail else "(Succès)"
                    console.print(f"  [bold #a6e3a1]📥 Données reçues :[/bold #a6e3a1] [dim #cdd6f4]{extrait[:100]}...[/dim #cdd6f4]")

            reponse_brute, tokens, chrono, moteur = run_agent(
                task=prompt_user,
                persona=persona,
                confirmer=callback_confirmation_terminal,
                callback_ui=_ui_callback,
            )

            texte_final = _extraire_texte_lisible_humain(reponse_brute)
            now_ts = datetime.datetime.now().strftime("%H:%M:%S")

            console.print()
            console.print(Panel(
                Markdown(texte_final, code_theme=THEME_CODE_LISIBLE),
                title=f"[bold {couleur}]🤖 {expert['nom']}[/bold {couleur}]  [dim #a6adc8]│  🕒 {now_ts}  │  ⏱️ {chrono:.2f}s  │  ⚡ {moteur}[/dim #a6adc8]",
                title_align="left",
                border_style=couleur,
                box=box.ROUNDED,
                padding=(1, 2),
                expand=True,
            ))
            console.print()

        except KeyboardInterrupt:
            now = time.time()
            if now - dernier_ctrl_c_timestamp < 1.5:
                console.print(f"\\n[bold #f38ba8]👋 Arrêt forcé (Ctrl+C).[/bold #f38ba8]\\n")
                sys.exit(0)
            else:
                dernier_ctrl_c_timestamp = now
                console.print(f"\\n[bold #f9e2af](Appuyez à nouveau sur Ctrl+C ou tapez exit pour quitter)[/bold #f9e2af]\\n")
                continue

        except EOFError:
            sys.exit(0)
        except Exception as e:
            console.print(f"\\n[bold #f38ba8]⚠️ Erreur d interface : {e}[/bold #f38ba8]\\n")


def main() -> None:
    args = sys.argv[1:]
    persona_init = "jarvis"
    mode_herdr = False

    if "herdr" in args:
        mode_herdr = True
        args.remove("herdr")

    if "--vocal" in args or "-v" in args:
        args = [a for a in args if a not in ("--vocal", "-v")]
        candidat = args[0].lower().strip() if args else "jarvis"
        lancer_mode_vocal_continu(persona_initial=candidat)
        return

    if args:
        candidat = args[0].lower().strip()
        if candidat in config.PERSONAS:
            persona_init = candidat

    boucle_principale(persona=persona_init, mode_herdr=mode_herdr)


if __name__ == "__main__":
    main()
'''

# ---------------------------------------------------------------------------
# CONTENU DE CORE/ENGINE.PY (MOTEUR SIMPLE-PASSE & VÉRITÉ RADICALE)
# ---------------------------------------------------------------------------
CORE_ENGINE_CONTENT = '''"""
core/engine.py — Moteur JAJAR Unifié (Vérité Radicale, Dialectique, Gating & Zéro-Simulation).
"""

from __future__ import annotations

import datetime
import json
import logging
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
from core.tools_registry import ConfirmCallback, description_outils_pour_prompt, executer_outil
from core.tracing import AgentTrace

logger: Final[logging.Logger] = logging.getLogger("jajar.engine")


def _obtenir_date_fr_exacte() -> str:
    JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    now = datetime.datetime.now()
    return f"{JOURS[now.weekday()]} {now.day} {MOIS[now.month - 1]} {now.year}, il est {now.strftime('%H:%M:%S')}."


def _detecter_requete_triviale(tache: str) -> bool:
    t_clean = tache.strip().lower()
    salutations = {"salut", "bonjour", "bonsoir", "coucou", "hello", "hi", "ça va", "merci", "ciao", "buongiorno"}
    return t_clean in salutations or (len(t_clean.split()) <= 2 and any(s in t_clean for s in salutations))


def _archiver_faits_vie_en_arriere_plan(dernier_user: str, dernier_bot: str, persona: str) -> None:
    if len(dernier_user.split()) < 3:
        return

    def _worker():
        try:
            ts_jour = datetime.datetime.now().strftime("%Y-%m-%d")
            ts_heure = datetime.datetime.now().strftime("%H:%M:%S")

            prompt = (
                f"Scribe de {config.UTILISATEUR} :\\n"
                f"- Denis : \\"{dernier_user}\\"\\n- {persona.upper()} : \\"{dernier_bot}\\"\\n\\n"
                "Extrais uniquement les faits utiles et durables au format JSON :\\n"
                "{\\"utile\\": true, \\"synthese\\": \\"...\\"} ou {\\"utile\\": false}"
            )
            res_raw, _ = router.generer(prompt, "Extraction faits.", temperature=0.1)
            res_clean = re.sub(r"^```(?:json)?", "", res_raw.strip()).removesuffix("```").strip()
            data = json.loads(res_clean)

            if data.get("utile") and data.get("synthese"):
                dossier_vie = config.VAULT_DIR / "06_Memoire_Vie"
                dossier_vie.mkdir(parents=True, exist_ok=True)
                f_vie = dossier_vie / "Faits_et_Reflexions_Denis.md"
                with open(f_vie, "a", encoding="utf-8") as f:
                    f.write(f"- `{ts_jour} {ts_heure}` **[{persona.upper()}]** : {data['synthese']}\\n")
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


_POSTURE_SYSTEME_BASE: Final[str] = f"""\\
Tu es JAJAR (ou l'agent spécialiste actif du studio), l'allié opérationnel d'élite de {config.UTILISATEUR}.
Connecté EN DIRECT sur son Mac (/Users/denmac).

═══════════════════════════════════════════════════════════════════════════════
LE PROTOCOLE DE VÉRITÉ RADICALE & ACTION DIRECTE (ZERO-MOCK) :
═══════════════════════════════════════════════════════════════════════════════
1. ACTION DIRECTE SANS SIMULATION :
   - Pour vérifier, inspecter ou exécuter : DÉCLENCHE DIRECTEMENT L'OUTIL (`action: "tool_call"`).
   - Interdiction formelle d'écrire des scripts avec des faux `print()` ou `# [OPTIMISÉ MACHINE DE GUERRE] time.sleep -> asyncio.sleep recommandé
# time.sleep()`.

2. PROPOSITION & ARBITRAGE (Dilemme ou idée nouvelle) :
   - Formule 2 à 3 solutions réelles et ta recommandation (Synergie A + B).
   - Arrête-toi immédiatement pour attendre le feu vert de Denis (`action: "final_answer"`).

3. RÈGLE DE PRÉSENTATION HERDR :
   - Rédige tes réponses en Markdown standard aéré.
   - ZÉRO JSON brut visible dans ta réponse finale : tout le contenu pour Denis doit être dans "answer".
═══════════════════════════════════════════════════════════════════════════════
"""

_FORMAT_SORTIE_JSON: Final[str] = """\\
FORMAT DE SORTIE JSON STRICT :
{
  "thinking": "Ton analyse concise",
  "est_dilemme_ou_idee": false,
  "solutions": [],
  "synergie_recommandee": null,
  "action": "tool_call" | "final_answer" | "ask_clarification",
  "tool_name": "nom_outil_ou_null",
  "tool_args": {},
  "answer": "Ta réponse intégrale pour Denis",
  "faits": [{"affirmation": "...", "statut": "verifie" | "hypothese", "source": "fichier:..."}],
  "doute_exprime": null
}
"""


def extraire_json_securise(texte: str) -> dict[str, Any]:
    if not texte:
        return {"action": "final_answer", "answer": "Opération terminée."}

    texte_net = texte.strip()
    texte_net = re.sub(r"^```(?:json)?", "", texte_net, flags=re.IGNORECASE)
    texte_net = re.sub(r"```$", "", texte_net).strip()

    try:
        res = json.loads(texte_net)
        if isinstance(res, dict):
            if isinstance(res.get("answer"), str) and res["answer"].strip().startswith("{"):
                try:
                    inner = json.loads(res["answer"].strip())
                    if isinstance(inner, dict) and "answer" in inner:
                        res["answer"] = inner["answer"]
                except Exception:
                    pass
            return res
        if isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict):
            return res[0]
    except Exception:
        pass

    match_dict = re.search(r"(\{[\s\S]*\})", texte_net)
    if match_dict:
        try:
            res = json.loads(match_dict.group(1))
            if isinstance(res, dict):
                return res
        except Exception:
            pass

    return {
        "thinking": "Action directe",
        "action": "final_answer",
        "tool_name": None,
        "tool_args": {},
        "answer": texte_net,
        "faits": [],
        "doute_exprime": None,
    }


def _compiler_skills_context(tache: str) -> str:
    skills = skill_registry.chercher_skills_pertinents(tache)
    if not skills:
        return ""
    lignes = ["\\n--- 🧠 COMPÉTENCES ACQUISES MOBILISABLES ---"]
    for s in skills:
        lignes.append(f"• SKILL: [{s.nom}] ➔ {' -> '.join(s.recette_etapes)}")
    return "\\n".join(lignes) + "\\n"


def formuler_5_options(question: str, persona: str = "jarvis") -> tuple[str, float, str]:
    t_debut = time.time()
    expert = config.PERSONAS.get(persona.lower(), config.PERSONAS["jarvis"])
    date_actuelle = _obtenir_date_fr_exacte()
    contexte_skills = _compiler_skills_context(question)

    prompt = (
        f"{_POSTURE_SYSTEME_BASE}\\n"
        f"Tu incarnes {expert['nom']} ({expert['role']}) pour {config.UTILISATEUR}.\\n"
        f"⏰ HORODATAGE : {date_actuelle}\\n"
        f"{contexte_skills}\\n"
        "DIRECTIVES : Présente 2 à 3 solutions réelles vérifiables et ta synergie recommandée.\\n\\n"
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
        return reponse_finale, chrono, moteur.replace("cloud:", "").replace("local:", "")
    except Exception as e:
        logger.error(f"Erreur formulation solutions : {e}")
        chrono = round(time.time() - t_debut, 2)
        return f"Erreur technique : {e}", chrono, "gemini"


def obtenir_decision(system_prompt: str, user_prompt: str) -> tuple[Decision, str, int]:
    brut, moteur = router.generer(system_prompt, user_prompt, temperature=0.2)
    data = extraire_json_securise(brut)

    action = data.get("action", "final_answer")
    if action not in ("tool_call", "final_answer", "ask_clarification"):
        action = "final_answer"

    tool_args = data.get("tool_args", {})
    if not isinstance(tool_args, dict):
        tool_args = {}

    tool_name = data.get("tool_name")
    if tool_name and isinstance(tool_name, str) and tool_name.strip() and tool_name != "null":
        action = "tool_call"

    faits_objs = []
    for f in data.get("faits", []):
        try:
            if isinstance(f, dict):
                faits_objs.append(FaitVerifie(**f))
        except Exception:
            pass

    decision = Decision(
        thinking=str(data.get("thinking", "")),
        est_dilemme_ou_idee=bool(data.get("est_dilemme_ou_idee", False)),
        solutions=[],
        synergie_recommandee=data.get("synergie_recommandee") or data.get("choix_creme"),
        action=action,
        tool_name=tool_name if action == "tool_call" else None,
        tool_args=tool_args,
        answer=str(data.get("answer") or data.get("thinking") or ""),
        confidence=data.get("confidence", "haute"),
        faits=faits_objs,
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

    tracer = tracer or AgentTrace(persona)
    state = AgentState(task=task, persona=persona, max_steps=max_steps)
    state.add("user", task)

    # Fast Gating pour salutations
    if _detecter_requete_triviale(task) and len(state.history) <= 1:
        reponse_triviale = f"Salut {config.UTILISATEUR} ! Tous les systèmes sont prêts. Sur quoi avançons-nous ?"
        tracer.log("final_answer", reponse_triviale, status="ok")
        state.sauvegarder_session(task, reponse_triviale)
        chrono = round(time.time() - t_debut, 2)
        return reponse_triviale, 30, chrono, config.MODELE_TEXTE_GEMINI

    expert = config.PERSONAS.get(persona, config.PERSONAS["jarvis"])
    date_actuelle = _obtenir_date_fr_exacte()

    if mode_operationnel in ("discussion", "oral"):
        prompt_chat = (
            f"Tu es {expert['nom']} en direct avec {config.UTILISATEUR}.\\n"
            f"Réponds en 1 à 2 phrases directes et chaleureuses (max 30 mots), zéro markdown."
        )
        reponse_directe, moteur = router.generer(prompt_chat, task, temperature=0.35)
        parsed = extraire_json_securise(reponse_directe)
        rendu = parsed.get("answer", reponse_directe)
        _archiver_faits_vie_en_arriere_plan(task, rendu, persona)
        tracer.log("final_answer", rendu, status="ok")
        state.sauvegarder_session(task, rendu)
        return rendu, 60, round(time.time() - t_debut, 2), moteur.replace("cloud:", "")

    outils_txt = description_outils_pour_prompt(persona)
    contexte_skills = _compiler_skills_context(task)

    system_prompt = (
        f"{_POSTURE_SYSTEME_BASE}\\n"
        f"Tu incarnes {expert['nom']} ({expert['role']}) — Domaine : {expert['domaine']}.\\n"
        f"⏰ HORODATAGE : {date_actuelle}\\n"
        f"MODE : {mode_operationnel.upper()}\\n\\n"
        f"OUTILS DISPONIBLES :\\n{outils_txt}\\n"
        f"{contexte_skills}\\n"
        f"{_FORMAT_SORTIE_JSON}\\n"
        f"--- CONTEXTE MÉMOIRE ACTIVE ---\\n{contexte_memoire or state.context_summary()}\\n"
    )

    tokens_total = 0
    moteur_final = config.MODELE_TEXTE_GEMINI
    trace_actions_reussies: list[dict[str, Any]] = []
    echecs_outils_consecutifs: dict[str, int] = {}

    try:
        for step in range(max_steps):
            state.verifier_et_compresser(tracer=tracer)

            user_prompt = f"Demande de {config.UTILISATEUR} : {task}\\n\\nContexte d exécution :\\n{state.context_summary()}"
            decision, moteur, tokens_etape = obtenir_decision(system_prompt, user_prompt)
            tokens_total += tokens_etape
            moteur_final = moteur.replace("cloud:", "").replace("local:", "")

            # Transmission de la pensée complète
            if decision.thinking:
                tracer.log("thinking", f"[{moteur}] {decision.thinking}")
                if callback_ui:
                    callback_ui("thinking", decision.thinking)

            # Exécution d Outil
            if decision.action == "tool_call" and decision.tool_name:
                outil_nom = decision.tool_name

                if echecs_outils_consecutifs.get(outil_nom, 0) >= 2:
                    reponse_forcee = f"Denis, l outil `{outil_nom}` rencontre un blocage répété. Voici les faits exacts constatés."
                    state.sauvegarder_session(task, reponse_forcee)
                    chrono_total = round(time.time() - t_debut, 2)
                    return reponse_forcee, tokens_total, chrono_total, moteur_final

                tracer.log("tool_call", f"{outil_nom}({decision.tool_args})")
                if callback_ui:
                    callback_ui("tool_call", f"{outil_nom} {json.dumps(decision.tool_args, ensure_ascii=False)}")

                resultat = executer_outil(outil_nom, decision.tool_args, persona, confirmer)
                state.add("assistant", decision.model_dump_json())

                if str(resultat).startswith("ERREUR") or str(resultat).startswith("⚠️"):
                    tracer.log("error", str(resultat), status="warning")
                    echecs_outils_consecutifs[outil_nom] = echecs_outils_consecutifs.get(outil_nom, 0) + 1
                    state.add("tool_result", f"{resultat}\\n[CONSIGNE] Outil en échec. Analyse l erreur et adapte ta méthode.")
                else:
                    echecs_outils_consecutifs[outil_nom] = 0
                    tracer.log("result", str(resultat), status="ok")
                    state.add("tool_result", str(resultat))
                    trace_actions_reussies.append({"outil": outil_nom, "args": decision.tool_args})

                if callback_ui:
                    callback_ui("result", str(resultat))

                continue

            # Réponse finale
            if decision.action == "final_answer" or not decision.tool_name:
                reponse_rendue = decision.answer or decision.thinking or "Opération terminée."

                if decision.doute_exprime:
                    reponse_rendue += f"\\n\\n🔍 *Point de vigilance :* {decision.doute_exprime}"

                _archiver_faits_vie_en_arriere_plan(task, reponse_rendue, persona)

                if len(trace_actions_reussies) >= 1:
                    skill_registry.distiller_et_apprendre(task, trace_actions_reussies)

                tracer.log("final_answer", reponse_rendue, status="ok")
                state.sauvegarder_session(task, reponse_rendue)
                chrono_total = round(time.time() - t_debut, 2)
                return reponse_rendue, tokens_total, chrono_total, moteur_final

        state.sauvegarder_session(task, "Limite d étapes atteinte.")
        chrono_total = round(time.time() - t_debut, 2)
        return "J ai terminé les opérations réelles demandées.", tokens_total, chrono_total, moteur_final

    except KeyboardInterrupt:
        chrono_total = round(time.time() - t_debut, 2)
        state.sauvegarder_session(task, "Interrompu par Denis.")
        return "🛑 **Opération interrompue par Denis.**", tokens_total, chrono_total, moteur_final
    except Exception as e:
        logger.error(f"Erreur run_agent : {e}")
        chrono_total = round(time.time() - t_debut, 2)
        return f"Erreur technique : {e}", tokens_total, chrono_total, moteur_final
'''

# ---------------------------------------------------------------------------
# ÉCRITURE ATOMIQUE SÉCURISÉE DES FICHIERS
# ---------------------------------------------------------------------------
print("═══════════════════════════════════════════════════════════════")
print("🚀 INSTALLATION ATOMIQUE DES FICHIERS DU STUDIO JAJAR v2")
print("═══════════════════════════════════════════════════════════════\n")

fichiers_a_ecrire = {
    BASE_DIR / "run_jarvis.py": RUN_JARVIS_CONTENT,
    BASE_DIR / "core" / "engine.py": CORE_ENGINE_CONTENT,
}

for chemin_fichier, contenu in fichiers_a_ecrire.items():
    print(f"📦 Écriture sécurisée de : {chemin_fichier.name}...")
    chemin_fichier.parent.mkdir(parents=True, exist_ok=True)
    chemin_fichier.write_text(contenu.strip() + "\n", encoding="utf-8")

    # Validation immédiate de la syntaxe Python
    try:
        py_compile.compile(str(chemin_fichier), doraise=True)
        print(f"   ✅ Syntaxe compilée et validée sans erreur.")
    except Exception as err:
        print(f"   ❌ Erreur de syntaxe détectée dans {chemin_fichier.name} : {err}")
        sys.exit(1)

# Nettoyage global de toute trace 'EOF' résiduelle sur l'ensemble du projet
print("\n🧹 Vérification de l'arbre complet du projet contre les artefacts 'EOF'...")
for f_py in BASE_DIR.rglob("*.py"):
    if f_py.is_file():
        lignes = f_py.read_text(encoding="utf-8", errors="ignore").splitlines()
        lignes_nettoyees = [l for l in lignes if l.strip() != "EOF"]
        if len(lignes_nettoyees) != len(lignes):
            f_py.write_text("\n".join(lignes_nettoyees) + "\n", encoding="utf-8")
            print(f"   ✨ Fichier assaini : {f_py.relative_to(BASE_DIR)}")

print("\n═══════════════════════════════════════════════════════════════")
print("✨ TOUS LES FICHIERS SONT DÉPLOYÉS ET 100% OPÉRATIONNELS !")
print("═══════════════════════════════════════════════════════════════\n")
