"""
core/tracing.py — Traçage d'événements et métriques opérationnelles par agent (JSONL).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Final

import config

logger: Final[logging.Logger] = logging.getLogger("jarvis.tracing")


class AgentTrace:
    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name.lower().strip()
        self.path: Path = config.TRACE_DIR / f"{self.agent_name}.jsonl"
        self.step = 0

    def log(self, event: str, detail: str, status: str = "info") -> None:
        """Enregistre un événement chronologique pour l'agent."""
        self.step += 1
        entry = {
            "ts": time.strftime("%H:%M:%S"),
            "ts_epoch": time.time(),
            "agent": self.agent_name,
            "step": self.step,
            "event": event,
            "detail": detail,
            "status": status,
        }
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Erreur d'écriture trace pour {self.agent_name}: {e}")

    def clear(self) -> None:
        if self.path.exists():
            try:
                self.path.unlink()
            except Exception:
                pass
        self.step = 0
