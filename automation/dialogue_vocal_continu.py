"""
automation/dialogue_vocal_continu.py — Mode Vocal Continu Apaisé (Pause VAD 1.4s)
Donne le temps de respirer et de réfléchir sans jamais couper la parole prématurément.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from core.engine import run_agent
from rich import box
from rich.console import Console
from rich.panel import Panel

console = Console()
logger: Final[logging.Logger] = logging.getLogger("jajar.vocal_ui")

try:
    import speech_recognition as sr
except ImportError:
    sr = None

MOTS_ARRET: Final[set[str]] = {
    "stop", "au revoir", "quitter", "pause", "fin", "ciao", "basta", "arrête", "arrete"
}


def _jouer_son_audio_rapide(texte: str, persona: str = "jarvis", langue: str = "fr") -> None:
    if not texte or len(texte.strip()) < 2:
        return

    import edge_tts

    if persona == "alba" and langue == "it":
        voice_id = "it-IT-ElsaNeural"
    elif persona == "alba":
        voice_id = "fr-FR-VivienneNeural"
    elif persona in ("tesla", "franklin"):
        voice_id = "fr-FR-HenriNeural"
    else:
        voice_id = "fr-FR-VivienneNeural"

    tmp_mp3 = config.AUDIO_DIR / f"vocal_{int(time.time() * 1000)}.mp3"
    clean_txt = re.sub(r"[*#`_\[\]>]", "", texte)[:400]

    async def _tts_exec():
        comm = edge_tts.Communicate(clean_txt, voice_id)
        await comm.save(str(tmp_mp3))

    try:
        asyncio.run(_tts_exec())
        if tmp_mp3.exists():
            subprocess.run(["afplay", str(tmp_mp3)], timeout=30)
    except Exception:
        pass
    finally:
        if tmp_mp3.exists():
            try:
                tmp_mp3.unlink()
            except Exception:
                pass


def lancer_mode_vocal_continu(persona_initial: str = "jarvis") -> None:
    persona_actuel = persona_initial.lower().strip()
    if persona_actuel not in config.PERSONAS:
        persona_actuel = "jarvis"

    if not sr:
        console.print("[bold red]❌ SpeechRecognition manquant : pip install SpeechRecognition pyaudio[/bold red]")
        return

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    # ⏳ Seuil de silence rehaussé à 1.4 seconde : vous avez tout le temps de réfléchir et de parler
    recognizer.pause_threshold = 1.4
    recognizer.phrase_threshold = 0.3

    try:
        micro = sr.Microphone()
    except Exception as e:
        console.print(f"[bold red]❌ Micro inaccessible : {e}[/bold red]")
        return

    expert = config.PERSONAS[persona_actuel]
    couleur = expert.get("couleur", "bright_cyan")

    console.clear()
    console.print(Panel(
        f"[bold {couleur}]🎙️ MODE VOCAL APAISÉ (Pause 1.4s) — AGENT {expert['nom']}[/bold {couleur}]\n"
        f"[#c0caf5]• Parle tranquillement à ton rythme, le micro ne te coupe plus.\n"
        f"• L'agent te répond puis attend TOUJOURS ton accord avant d'agir.[/]",
        border_style=couleur,
        box=box.ROUNDED,
        padding=(1, 2),
    ))

    with micro as source:
        console.print("[dim]⏳ Calibrage du micro sur la pièce...[/dim]")
        recognizer.adjust_for_ambient_noise(source, duration=0.8)

    while True:
        try:
            console.print(f"\n[bold {couleur}]🟢 [EN ÉCOUTE... Prends ton temps pour parler][/bold {couleur}]")

            with micro as source:
                audio = recognizer.listen(source, timeout=None, phrase_time_limit=20)

            texte_reconnu = ""
            langue = "fr"
            try:
                texte_reconnu = recognizer.recognize_google(audio, language="fr-FR").strip()
            except Exception:
                try:
                    texte_reconnu = recognizer.recognize_google(audio, language="it-IT").strip()
                    langue = "it"
                except Exception:
                    continue

            if not texte_reconnu:
                continue

            console.print(Panel(
                f"[bold white]{texte_reconnu}[/bold white]",
                title=f"[bold #7aa2f7]👤 {config.UTILISATEUR} (Texte Capté)[/bold #7aa2f7]",
                title_align="left",
                border_style="#7aa2f7",
                padding=(0, 2),
            ))

            if any(m in texte_reconnu.lower().split() for m in MOTS_ARRET):
                console.print("[bold #e0af68]👋 Fin du mode vocal.[/bold #e0af68]")
                _jouer_son_audio_rapide("À tout de suite Denis.", persona=persona_actuel)
                break

            # Inférence contrôlée
            reponse, tokens, chrono, moteur = run_agent(
                task=texte_reconnu,
                persona=persona_actuel,
                mode_operationnel="auto",
            )

            console.print(Panel(
                f"[bold white]{reponse}[/bold white]",
                title=f"[bold {couleur}]🤖 {expert['nom']}[/bold {couleur}]  [dim]│ ⏱️ {chrono:.2f}s[/dim]",
                title_align="left",
                border_style=couleur,
                padding=(0, 2),
            ))

            _jouer_son_audio_rapide(reponse, persona=persona_actuel, langue=langue)

        except KeyboardInterrupt:
            break
        except Exception:
            continue
