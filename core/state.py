from __future__ import annotations

"""
core/state.py — Gestionnaire d'état conversationnel multi-tours avec Sérialisation Pydantic Sécurisée.
"""

import datetime
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import config
from core.llm_router import router

logger: Final[logging.Logger] = logging.getLogger("jajar.state")
CARACTERES_PAR_TOKEN_ESTIME: Final[int] = 4

ANSI_ESCAPE_RE: Final[re.Pattern[str]] = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
TERMINAL_BOX_RE: Final[re.Pattern[str]] = re.compile(r"[╭╮╯╰│─═━┌┐└┘├┤┬┴┼^C]+")
CLI_PROMPT_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:👤|🤖)?\s*(?:Den|Denis|JAJAR|ALFRED|TESLA|RAY|CLÉO|LEO|FRANKLIN|ANSEL|INDIANA|ALBA)?\s*(?:\(\d{1,2}:\d{1,2}\))?\s*[❯>]\s*",
    re.IGNORECASE,
)


def _nettoyer_bruit_texte(texte: str) -> str:
    if not texte:
        return ""
    t = ANSI_ESCAPE_RE.sub("", texte)
    t = TERMINAL_BOX_RE.sub(" ", t)
    t = CLI_PROMPT_PREFIX_RE.sub("", t.strip())
    lignes = [l.strip() for l in t.splitlines() if l.strip()]
    return "\n".join(lignes).strip()


def _nettoyer_affichage_memoire(texte_brut: str) -> str:
    if not texte_brut:
        return ""
    t = texte_brut.strip()
    if t.startswith("{") and t.endswith("}"):
        try:
            data = json.loads(t, strict=False)
            if isinstance(data, dict):
                return str(data.get("answer") or data.get("thinking") or "").strip()
        except Exception:
            pass
    return t


def _scanner_taches_et_projets() -> tuple[list[str], list[str], list[str]]:
    projets_dir = config.VAULT_DIR / "01_Projets"
    projets_actifs = []
    taches_a_faire = []
    taches_faites = []

    if projets_dir.exists():
        for f in sorted(projets_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            if not f.name.startswith("."):
                projets_actifs.append(f.stem)
                try:
                    contenu = f.read_text(encoding="utf-8", errors="ignore")
                    for ligne in contenu.splitlines():
                        l_str = ligne.strip()
                        if l_str.startswith("- [ ]") and len(l_str) > 6:
                            taches_a_faire.append(f"{l_str[5:].strip()} `[[{f.stem}]]`")
                        elif l_str.startswith("- [x]") and len(l_str) > 6:
                            taches_faites.append(f"{l_str[5:].strip()} `[[{f.stem}]]`")
                except Exception:
                    pass

    return projets_actifs[:6], taches_faites[:4], taches_a_faire[:6]


@dataclass
class AgentState:
    task: str
    persona: str = "jarvis"
    history: list[dict[str, str]] = field(default_factory=list)
    plan: list[dict[str, Any]] = field(default_factory=list)
    max_steps: int = 20
    mission_active: str = ""
    cible_distante_active: str = ""
    chemins_connus: dict[str, str] = field(default_factory=dict)
    options_actives: list[dict[str, Any]] = field(default_factory=list)
    consecutive_tool_failures: int = 0

    def __post_init__(self) -> None:
        if not self.history:
            self._charger_historique_recent()

    def add(self, role: str, content: str) -> None:
        texte_propre = _nettoyer_bruit_texte(str(content))
        if role == "tool_result" and len(texte_propre) > 3500:
            lignes = texte_propre.splitlines()
            if len(lignes) > 40:
                texte_propre = "\n".join(lignes[:30]) + f"\n... [{len(lignes) - 30} lignes filtrées] ..."

        self.history.append({"role": role, "content": texte_propre})

        if "/Users/denmac" in texte_propre:
            for match in re.findall(r"(/Users/denmac/[\w\.-]+(?:/[\w\.-]+)*)", texte_propre):
                p = Path(match)
                if p.exists():
                    self.chemins_connus[p.name] = str(p)

        if role == "user" and len(texte_propre.split()) > 2 and not self.mission_active:
            self.mission_active = texte_propre[:140]

    def estimer_tokens(self) -> int:
        total_chars = sum(len(str(h.get("content", ""))) for h in self.history if isinstance(h, dict))
        return max(1, total_chars // CARACTERES_PAR_TOKEN_ESTIME)

    def _charger_historique_recent(self) -> None:
        f_etat = config.BASE_DIR / f"session_active_{self.persona}.json"
        if not f_etat.exists():
            return
        try:
            data = json.loads(f_etat.read_text(encoding="utf-8"))
            tours_recents = data.get("derniers_tours", [])
            if isinstance(tours_recents, list):
                self.history.extend(tours_recents[-8:])
            self.mission_active = data.get("mission_active", "")
            self.cible_distante_active = data.get("cible_distante", "")
            self.chemins_connus = data.get("chemins_connus", {})
            self.options_actives = data.get("options_actives", [])
        except Exception as e:
            logger.warning(f"Erreur chargement session : {e}")

    def charger_grand_briefing_demarrage(self) -> str:
        projets, faits, a_faire = _scanner_taches_et_projets()
        f_etat = config.BASE_DIR / f"session_active_{self.persona}.json"

        lignes: list[str] = []
        lignes.append(f"# 🧭 GRAND BRIEFING STRATÉGIQUE — {config.UTILISATEUR.upper()}\n")

        lignes.append("### 🏁 Ce que nous avons accompli récemment :")
        echanges_utiles = []
        if f_etat.exists():
            try:
                data = json.loads(f_etat.read_text(encoding="utf-8"))
                for t in data.get("derniers_tours", []):
                    if t.get("role") == "assistant" and not t.get("content", "").startswith("🛑"):
                        contenu = _nettoyer_affichage_memoire(t.get("content", ""))
                        if contenu and len(contenu) > 15:
                            resume = contenu.splitlines()[0][:130]
                            echanges_utiles.append(f"• **Session précédente :** {resume}")
            except Exception:
                pass

        if faits:
            for f in faits:
                lignes.append(f"• ✅ {f}")
        elif echanges_utiles:
            for eu in echanges_utiles[-2:]:
                lignes.append(eu)
        else:
            lignes.append("• Consolidation et sécurisation du noyau d'inférence JAJAR v2.")

        lignes.append("\n### 🎯 Ce que nous devons faire / Priorités en attente :")
        if a_faire:
            for af in a_faire:
                lignes.append(f"• ⏳ **{af}**")
        else:
            lignes.append("• ⏳ **Audit et finalisation des projets actifs dans 01_Projets**")
            lignes.append("• ⏳ **Tri et traitement des archives d'emails 2026**")

        lignes.append("\n### 📁 Projets & Contexte Actif :")
        projets_txt = " · ".join(f"`[[{p}]]`" for p in projets) if projets else "`[[Second-Cerveau]]`"
        lignes.append(f"• **Projets Détectés :** {projets_txt}")
        if self.chemins_connus:
            dossiers_txt = " · ".join(f"`{k}`" for k in list(self.chemins_connus.keys())[:4])
            lignes.append(f"• **Dossiers Clés :** {dossiers_txt}")

        lignes.append("\n> 💡 *Prêt pour tes instructions. Pose-moi une question technique ou valide une étape pour avancer.*")
        return "\n".join(lignes)

    def sauvegarder_session(
        self,
        dernier_user: str = "",
        dernier_bot: str = "",
        options: list[Any] | None = None,
    ) -> None:
        """Sauvegarde atomique avec conversion propre des objets Pydantic SolutionConcrete."""
        f_etat = config.BASE_DIR / f"session_active_{self.persona}.json"
        user_clean = _nettoyer_bruit_texte(dernier_user)
        bot_clean = _nettoyer_bruit_texte(dernier_bot)

        if bot_clean.startswith("🛑") and self.history and self.history[-1].get("content", "").startswith("🛑"):
            return

        tours_a_sauver = [h for h in self.history if h.get("role") in ("user", "assistant")][-12:]

        # Conversion robuste de n'importe quel objet Pydantic en dict JSON natif
        options_clean: list[dict[str, Any]] = []
        candidats_options = options if options is not None else self.options_actives
        if isinstance(candidats_options, list):
            for opt in candidats_options:
                if hasattr(opt, "model_dump"):
                    options_clean.append(opt.model_dump())
                elif hasattr(opt, "dict"):
                    options_clean.append(opt.dict())
                elif isinstance(opt, dict):
                    options_clean.append(opt)
                else:
                    options_clean.append({"description": str(opt)})

        self.options_actives = options_clean

        data = {
            "agent": self.persona,
            "date_maj": datetime.datetime.now().isoformat(),
            "mission_active": self.mission_active or user_clean[:140],
            "cible_distante": self.cible_distante_active,
            "chemins_connus": self.chemins_connus,
            "derniers_tours": tours_a_sauver,
            "options_actives": options_clean,
        }

        try:
            tmp_file = f_etat.parent / f".tmp_{f_etat.name}_{uuid.uuid4().hex[:6]}"
            tmp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_file.replace(f_etat)
        except Exception as e:
            logger.warning(f"Erreur persistance session : {e}")

    def verifier_et_compresser(self, tracer: Any = None) -> None:
        tokens = self.estimer_tokens()
        if tokens >= config.SEUIL_TOKENS_COMPRESSION and len(self.history) > 6:
            if tracer:
                tracer.log("info", f"🧠 Compression du contexte ({tokens} tokens)...")
            derniers = self.history[-4:]
            self.history = [
                {"role": "system", "content": f"=== SÈVE CONVERSATIONNELLE RÉCENTE ==="},
                *derniers,
            ]

    def context_summary(self) -> str:
        ctx: dict[str, Any] = {
            "historique_recent": self.history[-6:],
        }
        if self.mission_active:
            ctx["🎯_MISSION_EN_COURS"] = self.mission_active
        if self.options_actives:
            ctx["📋_OPTIONS_PROPOSEES"] = self.options_actives
        projets, _, _ = _scanner_taches_et_projets()
        if projets:
            ctx["📁_PROJETS_OBSIDIAN"] = projets
        return json.dumps(ctx, ensure_ascii=False)
