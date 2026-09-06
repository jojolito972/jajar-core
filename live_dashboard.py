"""
live_dashboard.py — Dashboard Textual Pastel Haute Visibilité
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, RichLog, Static, TabbedContent, TabPane

import config

TRACE_DIR = config.TRACE_DIR

# --- Thème Pastel Doux & Confort Visuel ---
BG = "#1A1B26"
PANEL = "#24283B"
TEXT = "#C0CAF5"
TEXT_DIM = "#7AA2F7"

DOT = {
    "idle": ("#565F89", "#565F89"),
    "en_cours": ("#FDE68A", "#F59E0B"),      # Ambre / Or pastel
    "attention": ("#FCA5A5", "#EF4444"),     # Corail pastel
    "termine": ("#A7F3D0", "#10B981"),       # Menthe douce
}

EVENT_STYLE = {
    "thinking": ("💭 ", "#C7D2FE"),          # Lavande douce
    "tool_call": ("⚡ ", "#FDE68A"),          # Jaune pastel
    "result": ("📥 ", "#A7F3D0"),             # Menthe
    "error": ("⛔ ", "#FCA5A5"),              # Corail
    "final_answer": ("✨ ", "#93C5FD"),       # Bleu ciel pastel
    "clarification": ("❓ ", "#FBCFE8"),      # Rose poudré
    "info": ("ℹ️ ", "#7AA2F7"),
}

def formater_ligne(entry: dict, delta_s: float | None) -> str:
    event = entry.get("event", "info")
    detail = str(entry.get("detail", "")).replace("[", "\\[")
    ts = entry.get("ts", "")
    etape = entry.get("step", "")
    icone, couleur = EVENT_STYLE.get(event, ("· ", "#C0CAF5"))
    delta_txt = f"+{delta_s:.1f}s" if delta_s is not None else "     "

    return (
        f"[dim]{ts} #{etape:<2} {delta_txt}[/dim] "
        f"[{couleur} bold]{icone}{event:<12}[/{couleur} bold] "
        f"[bold {TEXT}]{detail}[/bold {TEXT}]"
    )

@dataclass
class AgentState:
    persona: str
    etat: str = "idle"
    etape: int = 0
    moteur: str = "—"
    position_fichier: int = 0
    ts_epoch_precedent: float | None = None

class AgentDashboard(App):
    CSS = f"""
    Screen {{ background: {BG}; }}
    #overview {{ height: 3; background: {PANEL}; padding: 0 1; align: left middle; }}
    TabbedContent {{ height: 1fr; }}
    Tab.-active {{ background: {PANEL}; color: #A7F3D0; text-style: bold; }}
    Tabs Underline > .underline--bar {{ color: #C7D2FE; }}
    RichLog {{ background: {BG}; padding: 1; }}
    """
    BINDINGS = [("q", "quit", "Quitter"), ("p", "pause", "Pause")]

    def compose(self) -> ComposeResult:
        with TabbedContent(id="agent_tabs", initial="tab_jarvis"):
            for persona, infos in config.PERSONAS.items():
                with TabPane(f"{infos['nom']} ({infos['role']})", id=f"tab_{persona}"):
                    yield RichLog(id=f"log_{persona}", wrap=True, highlight=False, markup=True, auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        self.etats = {p: AgentState(persona=p) for p in config.PERSONAS}
        self.set_interval(0.4, self.poll_traces)

    def poll_traces(self) -> None:
        for persona in config.PERSONAS:
            path = TRACE_DIR / f"{persona}.jsonl"
            if not path.exists():
                continue
            etat = self.etats[persona]
            with open(path, "r", encoding="utf-8") as f:
                f.seek(etat.position_fichier)
                lignes = f.readlines()
                etat.position_fichier = f.tell()

            if not lignes:
                continue
            log_widget = self.query_one(f"#log_{persona}", RichLog)
            for l in lignes:
                if not l.strip():
                    continue
                try:
                    entry = json.loads(l)
                    delta = entry.get("ts_epoch", 0) - (etat.ts_epoch_precedent or entry.get("ts_epoch", 0))
                    etat.ts_epoch_precedent = entry.get("ts_epoch")
                    log_widget.write(formater_ligne(entry, delta))
                except Exception:
                    pass

if __name__ == "__main__":
    AgentDashboard().run()
