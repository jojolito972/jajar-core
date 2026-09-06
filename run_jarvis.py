from __future__ import annotations

"""
run_jarvis.py — Terminal d'Élite JAJAR SOTA v2.
Commandes : /local, /cloud, /nvidia, /liberer (Purge VRAM), /perso, /pro.
"""

import warnings
import logging
import os

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*automatic function calling.*")
os.environ["PYTHONWARNINGS"] = "ignore"
logging.getLogger("google").setLevel(logging.ERROR)
logging.getLogger("google.genai").setLevel(logging.ERROR)

import asyncio
import datetime
import json
import readline
import re
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from automation.dialogue_vocal_continu import lancer_mode_vocal_continu
from automation.proactive_daemon import proactive_daemon
from core.engine import formuler_5_options, run_agent
from core.llm_router import router
from core.orchestrator_bus import orchestrator_bus
from core.state import AgentState
from core.tracing import AgentTrace
from tools.herdr_bridge import assurer_presence, release_agent, report_state
from tools.local_model_manager import server_manager
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.theme import Theme

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.history import FileHistory
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

HISTORIQUE_CLI: Final[str] = os.path.expanduser("~/.jajar_cli_history")

THEME_PASTEL = Theme({
    "markdown.paragraph": "#cdd6f4",
    "markdown.text": "#cdd6f4",
    "markdown.strong": "bold #fab387",
    "markdown.code": "bold #94e2d5",
    "markdown.h1": "bold #89b4fa",
    "markdown.h2": "bold #cba6f7",
    "markdown.h3": "bold #f9e2af",
    "markdown.em": "italic #f5c2e7",
    "markdown.item": "#cdd6f4",
    "markdown.item.bullet": "bold #fab387",
    "markdown.item.number": "bold #89b4fa",
    "markdown.block_quote": "italic #a6adc8",
    "markdown.hr": "#45475a",
})

console = Console(theme=THEME_PASTEL, highlight=False, soft_wrap=False)
THEME_CODE_LISIBLE: Final[str] = "one-dark"

COULEURS_AGENTS: Final[dict[str, str]] = {
    "jarvis": "#89b4fa",
    "alba": "#a6e3a1",
    "alfred": "#74c7ec",
    "ray": "#cba6f7",
    "cleo": "#f9e2af",
    "leo": "#a6e3a1",
    "franklin": "#94e2d5",
    "tesla": "#f38ba8",
    "ansel": "#b4befe",
    "indiana": "#fab387",
}

AGENT_DESCRIPTIONS: Final[dict[str, str]] = {
    "jarvis": "Superviseur global — Coordination générale, arbitrage et pilotage des missions.",
    "alfred": "Assistant exécutif — Mails, agenda, administration Google Suite.",
    "ray": "Recherche profonde & veille — Web, synthèses SOTA, projets.",
    "cleo": "Stratégie business — Rentabilité, devis, trésorerie et Micro-BNC.",
    "leo": "Direction artistique & UI/UX — Design, médias et typographies.",
    "franklin": "Développement commercial — Clients, prospection et négociation.",
    "tesla": "Ingénierie systèmes — Scripts Python, Docker, réseau et automatisation.",
    "ansel": "Fabrique visuelle — Génération d'images FLUX.1 / Imagen 3.",
    "indiana": "Édition patrimoine — OCR, archives historiques, PDF et NotebookLM.",
    "alba": "Maître Atelier Bespoke — Bottière d'art (Laura Puntillo), peausseries et souliers sur-mesure.",
}


def _extraire_texte_lisible_humain(texte_brut: str) -> str:
    if not texte_brut:
        return "Opération terminée."
    t = texte_brut.strip()
    if t.startswith("{") and ("\"answer\"" in t or "\"thinking\"" in t):
        try:
            data = json.loads(t, strict=False)
            if isinstance(data, dict):
                ans = data.get("answer") or data.get("thinking") or ""
                if ans:
                    return _extraire_texte_lisible_humain(ans)
        except Exception:
            pass
        m = re.search(r"\"answer\"\s*:\s*\"([\s\S]*?)\"\s*,\s*\"faits\"", t)
        if not m:
            m = re.search(r"\"answer\"\s*:\s*\"([\s\S]*?)\"\s*\}\s*$", t)
        if m:
            t = m.group(1)
    return t.replace("\\n", "\n").replace('\\"', '"').strip()


def afficher_banniere(persona: str, mode_actuel: str) -> None:
    expert = config.PERSONAS.get(persona.lower(), config.PERSONAS["jarvis"])
    couleur = COULEURS_AGENTS.get(persona.lower(), "#89b4fa")
    now_str = datetime.datetime.now().strftime("%H:%M:%S")

    if router.mode_actif == "local":
        badge_moteur = "[bold #a6e3a1]🔒 LOCAL METAL (Gemma 4)[/bold #a6e3a1]"
    elif router.mode_actif == "nvidia":
        badge_moteur = "[bold #a6e3a1]🟢 NVIDIA NIM H100 (120B)[/bold #a6e3a1]"
    else:
        badge_moteur = "[bold #89b4fa]⚡ CLOUD GEMINI 3.6[/bold #89b4fa]"

    badge_mode = "[bold #fab387]PRO (Ops)[/bold #fab387]" if mode_actuel == "auto" else "[bold #a6e3a1]PERSO (Chat)[/bold #a6e3a1]"

    console.print()
    console.print(Panel(
        f"[bold {couleur}]STUDIO JAJAR v2 · AGENT {expert['nom']}[/bold {couleur}]  │  {badge_moteur}  │  {badge_mode}\n"
        f"[#cdd6f4]• Rôle : {escape(expert['domaine'])}[/#cdd6f4]\n"
        f"[dim #6c7086 italic]⏰ Connecté à {now_str} · Mac de {config.UTILISATEUR} (/Users/denmac)[/dim #6c7086 italic]\n"
        f"[dim #89b4fa]• Commandes : [bold #a6e3a1]/local[/bold #a6e3a1]  [bold #89b4fa]/cloud[/bold #89b4fa]  [bold #a6e3a1]/nvidia[/bold #a6e3a1]  [bold #f38ba8]/liberer[/bold #f38ba8] (Stop VRAM)  [bold #f9e2af]/perso[/bold #f9e2af]  [bold #fab387]/pro[/bold #fab387][/dim #89b4fa]",
        title=f"[bold {couleur}]⚡ COCKPIT UNIFIÉ SOTA[/bold {couleur}]",
        border_style=couleur,
        box=box.ROUNDED,
        padding=(1, 2),
    ))
    console.print()


def boucle_principale(persona: str = "jarvis", mode_initial: str = "auto") -> None:
    persona = persona.lower().strip()
    if persona not in config.PERSONAS:
        persona = "jarvis"

    assurer_presence(persona)

    global_bg_loop = asyncio.new_event_loop()
    def _demarrer_services_arriere_plan(loop: asyncio.AbstractEventLoop):
        asyncio.set_event_loop(loop)
        loop.run_until_complete(orchestrator_bus.start())
        loop.run_until_complete(proactive_daemon.start())
        loop.run_forever()

    t_services = threading.Thread(target=_demarrer_services_arriere_plan, args=(global_bg_loop,), daemon=True, name="jajar_services_daemon")
    t_services.start()

    mode_courant = mode_initial
    afficher_banniere(persona, mode_courant)

    session_prompt = None
    if HAS_PROMPT_TOOLKIT:
        try:
            session_prompt = PromptSession(history=FileHistory(HISTORIQUE_CLI), enable_history_search=True)
        except Exception:
            pass

    while True:
        try:
            report_state(persona, "idle")

            expert = config.PERSONAS[persona]
            couleur_hex = COULEURS_AGENTS.get(persona, "#89b4fa")
            
            if router.mode_actif == "local":
                symbole_moteur = "🔒"
            elif router.mode_actif == "nvidia":
                symbole_moteur = "🟢"
            else:
                symbole_moteur = "⚡"

            if session_prompt:
                prompt_str = f"\033[1;36m👤 {config.UTILISATEUR} [{symbole_moteur}] ❯\033[0m "
                prompt_user = session_prompt.prompt(ANSI(prompt_str)).strip()
            else:
                prompt_user = console.input(f"[bold {couleur_hex}]👤 {config.UTILISATEUR} [{symbole_moteur}] ❯ [/bold {couleur_hex}]").strip()

            if not prompt_user:
                continue

            if prompt_user.lower() in ("exit", "quit", "quitter", "q", "/q", "bye", "stop"):
                release_agent(persona)
                sys.exit(0)

            # Bascules déterministes de moteur
            if prompt_user.lower() in ("/local", "/offline", "/gemma"):
                msg = router.basculer_mode("local")
                console.print(f"\n{msg}\n")
                afficher_banniere(persona, mode_courant)
                continue

            if prompt_user.lower() in ("/cloud", "/gemini", "/online"):
                msg = router.basculer_mode("cloud")
                console.print(f"\n{msg}\n")
                afficher_banniere(persona, mode_courant)
                continue

            if prompt_user.lower() in ("/nvidia", "/nim", "/h100", "nvidia"):
                msg = router.basculer_mode("nvidia")
                console.print(f"\n{msg}\n")
                afficher_banniere(persona, mode_courant)
                continue

            # Commande explicite pour purger la VRAM
            if prompt_user.lower() in ("/liberer", "/stop-local", "/kill-local", "/purge"):
                msg_purge = server_manager.arreter_serveur()
                if router.mode_actif == "local":
                    router.mode_actif = "cloud"
                console.print(f"\n[bold #a6e3a1]{msg_purge}[/bold #a6e3a1]\n")
                afficher_banniere(persona, mode_courant)
                continue

            if prompt_user.lower() in ("/perso", "/chat"):
                mode_courant = "discussion"
                console.print("\n[bold #a6e3a1]💬 Mode Discussion Perso activé (<0.4s).[/bold #a6e3a1]\n")
                continue

            if prompt_user.lower() in ("/pro", "/studio", "/ops"):
                mode_courant = "auto"
                console.print("\n[bold #fab387]⚡ Mode Studio Pro activé.[/bold #fab387]\n")
                continue

            if prompt_user.upper() == "J" or prompt_user.lower() in ("/vocal", "vocal"):
                lancer_mode_vocal_continu(persona_initial=persona)
                afficher_banniere(persona, mode_courant)
                continue

            if prompt_user.startswith("/agent"):
                parts = prompt_user.split()
                if len(parts) > 1 and parts[1].lower() in config.PERSONAS:
                    release_agent(persona)
                    persona = parts[1].lower()
                    assurer_presence(persona)
                    afficher_banniere(persona, mode_courant)
                    continue

            def _ui_callback(event_type: str, detail: str):
                if event_type == "thinking" and len(detail) > 5 and mode_courant != "discussion":
                    console.print()
                    console.print(Panel(
                        Markdown(detail.strip(), code_theme=THEME_CODE_LISIBLE),
                        title=f"[bold #cba6f7]🧠 RÉFLEXION & STRATÉGIE ({expert['nom']})[/bold #cba6f7]",
                        border_style="#cba6f7",
                        box=box.ROUNDED,
                        padding=(1, 2),
                    ))
                elif event_type == "tool_call":
                    console.print(f"  [bold #89b4fa]⚙️ Action :[/bold #89b4fa] [bold #94e2d5]{detail}[/bold #94e2d5]")
                elif event_type == "result":
                    extrait = detail.splitlines()[0] if detail else "(Succès)"
                    console.print(f"  [bold #a6e3a1]📥 Données :[/bold #a6e3a1] [dim #a6adc8]{extrait[:110]}...[/dim #a6adc8]")

            report_state(persona, "working")

            reponse_brute, tokens, chrono, moteur = run_agent(
                task=prompt_user,
                persona=persona,
                mode_operationnel=mode_courant,
                callback_ui=_ui_callback,
            )

            report_state(persona, "idle")

            texte_final = _extraire_texte_lisible_humain(reponse_brute)
            now_ts = datetime.datetime.now().strftime("%H:%M:%S")

            console.print()
            console.print(Panel(
                Markdown(texte_final, code_theme=THEME_CODE_LISIBLE),
                title=f"[bold {couleur_hex}]🤖 {expert['nom']}[/bold {couleur_hex}]  [dim #a6adc8]│  🕒 {now_ts}  │  ⏱️ {chrono:.2f}s  │  ⚡ {moteur}[/dim #a6adc8]",
                border_style=couleur_hex,
                box=box.ROUNDED,
                padding=(1, 2),
            ))
            console.print()

        except KeyboardInterrupt:
            release_agent(persona)
            console.print(f"\n[bold #f38ba8]👋 Arrêt forcé (Ctrl+C).[/bold #f38ba8]\n")
            sys.exit(0)
        except Exception as e:
            report_state(persona, "idle", message=f"Erreur: {e}")
            console.print(f"\n[bold #f38ba8]⚠️ Erreur d'interface : {e}[/bold #f38ba8]\n")
            time.sleep(0.5)


def main() -> None:
    args = sys.argv[1:]
    persona_init = "jarvis"
    mode_init = "auto"
    if args and args[0].lower().strip() in config.PERSONAS:
        persona_init = args[0].lower().strip()
    boucle_principale(persona=persona_init, mode_initial=mode_init)


if __name__ == "__main__":
    main()
