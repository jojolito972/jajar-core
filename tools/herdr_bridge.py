from __future__ import annotations

"""
tools/herdr_bridge.py — Intégration Officielle du Cycle de Vie des Agents pour Herdr.
Communique directement avec l'API CLI Herdr (pane report-agent / release-agent)
pour enregistrer et actualiser l'état des agents dans le panneau latéral (agents/grouped).
"""

import atexit
import datetime
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final, Optional

import config

logger: Final[logging.Logger] = logging.getLogger("jajar.herdr_bridge")


def _trouver_herdr_bin() -> str:
    """Localise le binaire Herdr avec recherche multi-chemins sur macOS."""
    bin_env = os.environ.get("HERDR_BIN_PATH")
    if bin_env and Path(bin_env).is_file() and os.access(bin_env, os.X_OK):
        return bin_env

    candidats = [
        shutil.which("herdr"),
        "/opt/homebrew/bin/herdr",
        "/usr/local/bin/herdr",
        str(Path.home() / ".cargo/bin/herdr"),
        str(Path.home() / ".local/bin/herdr"),
    ]
    for c in candidats:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return c
    return "herdr"


def report_state(agent_name: str, state: str = "idle", message: Optional[str] = None) -> None:
    """Enregistre l'état sémantique de l'agent auprès de Herdr (idle | working | blocked)."""
    if os.environ.get("HERDR_ENV") != "1":
        return

    pane_id = os.environ.get("HERDR_PANE_ID")
    if not pane_id:
        return

    p_clean = agent_name.lower().strip()
    expert = config.PERSONAS.get(p_clean, config.PERSONAS["jarvis"])
    nom_agent = expert["nom"]
    herdr_bin = _trouver_herdr_bin()

    # 1. Émission du titre OSC 0/2
    try:
        sys.stdout.write(f"\x1b]0;{nom_agent}\x07")
        sys.stdout.write(f"\x1b]2;{nom_agent}\x07")
        sys.stdout.flush()
    except Exception:
        pass

    # 2. Enregistrement officiel via la CLI Herdr
    cmd = [
        herdr_bin, "pane", "report-agent", str(pane_id),
        "--source", f"custom:{p_clean}",
        "--agent", nom_agent,
        "--state", state,
    ]
    if message:
        cmd.extend(["--message", str(message)])

    try:
        subprocess.run(cmd, capture_output=True, timeout=3)
    except Exception as e:
        logger.debug(f"Notice report-agent Herdr : {e}")


def release_agent(agent_name: str) -> None:
    """Libère l'autorité de l'agent dans Herdr lors de la fermeture."""
    if os.environ.get("HERDR_ENV") != "1":
        return

    pane_id = os.environ.get("HERDR_PANE_ID")
    if not pane_id:
        return

    p_clean = agent_name.lower().strip()
    expert = config.PERSONAS.get(p_clean, config.PERSONAS["jarvis"])
    nom_agent = expert["nom"]
    herdr_bin = _trouver_herdr_bin()

    cmd = [
        herdr_bin, "pane", "release-agent", str(pane_id),
        "--source", f"custom:{p_clean}",
        "--agent", nom_agent,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=2)
    except Exception:
        pass


def assurer_presence(persona: str) -> None:
    """Initialise l'agent dans Herdr et arme le hook de déconnexion automatique."""
    report_state(persona, state="idle")
    atexit.register(lambda: release_agent(persona))
