from __future__ import annotations

"""
core/tools_registry.py — Registre d'Outils Centralisé avec Auto-Découverte et Protection Anti-Boucle.
"""

import importlib
import inspect
import json
import logging
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Final, Optional

from config import SecurityTier

logger: Final[logging.Logger] = logging.getLogger("jajar.tools_registry")

ConfirmCallback = Optional[Callable[[str, dict[str, Any]], bool]]


@dataclass
class OutilSpec:
    nom: str
    fonction: Callable[..., Any]
    description: str
    parametres: dict[str, Any]
    tier: SecurityTier = SecurityTier.AUTO
    personas: list[str] = field(default_factory=list)


REGISTRE_OUTILS: dict[str, OutilSpec] = {}


def outil(
    tier: SecurityTier = SecurityTier.AUTO,
    personas: Optional[list[str]] = None,
    nom: Optional[str] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        nom_outil = nom or fn.__name__
        doc = (fn.__doc__ or "").strip()
        sig = inspect.signature(fn)

        params_spec: dict[str, Any] = {}
        for p_name, param in sig.parameters.items():
            if p_name in ("self", "cls"):
                continue
            type_str = param.annotation.__name__ if hasattr(param.annotation, "__name__") else str(param.annotation)
            defaut = param.default if param.default is not inspect.Parameter.empty else None
            params_spec[p_name] = {
                "type": type_str if type_str != "_empty" else "str",
                "default": defaut,
                "required": param.default is inspect.Parameter.empty,
            }

        REGISTRE_OUTILS[nom_outil] = OutilSpec(
            nom=nom_outil,
            fonction=fn,
            description=doc,
            parametres=params_spec,
            tier=tier,
            personas=[p.lower() for p in (personas or [])],
        )
        return fn
    return decorator


def charger_tous_les_outils() -> None:
    tools_dir = Path(__file__).resolve().parent.parent / "tools"
    if not tools_dir.exists():
        return

    # Fichiers à exclure impérativement pour éviter les imports circulaires avec engine.py
    MODULES_EXCLUS = {"jarvis_telegram_hub", "herdr_bridge"}

    modules_connus = [
        "tools.system_tools",
        "tools.delegation_tools",
        "tools.second_cerveau",
        "tools.web_tool",
        "tools.deep_research",
        "tools.graph_memory",
        "tools.notebooklm_tool",
        "tools.gui_control",
        "tools.alba_artisan_tools",
        "tools.local_model_manager",
        "tools.governor_tools",
    ]

    for mod_nom in modules_connus:
        try:
            importlib.import_module(mod_nom)
        except Exception as e:
            logger.debug(f"Notice import [{mod_nom}]: {e}")

    for _, module_name, _ in pkgutil.iter_modules([str(tools_dir)]):
        if module_name in MODULES_EXCLUS or module_name.startswith("_"):
            continue
        full_name = f"tools.{module_name}"
        if full_name not in modules_connus:
            try:
                importlib.import_module(full_name)
            except Exception as e:
                logger.debug(f"Notice auto-import [{full_name}] : {e}")

    logger.info(f"🛠️ Registre d'outils initialisé : {len(REGISTRE_OUTILS)} outils enregistrés.")


def description_outils_pour_prompt(persona: str = "jarvis") -> str:
    if not REGISTRE_OUTILS:
        charger_tous_les_outils()

    persona_clean = persona.lower().strip()
    lignes: list[str] = []

    for nom_o, spec in REGISTRE_OUTILS.items():
        if spec.personas and persona_clean != "jarvis" and persona_clean not in spec.personas:
            continue

        params_txt = ", ".join(
            f"{k}: {v['type']}" + ("" if v['required'] else f" = {repr(v['default'])}")
            for k, v in spec.parametres.items()
        )
        lignes.append(f"• `{nom_o}({params_txt})` ➔ {spec.description}")

    return "\n".join(lignes) or "Aucun outil requis pour ce mode."


def executer_outil(
    nom_outil: str,
    args: dict[str, Any],
    persona: str = "jarvis",
    confirmer: ConfirmCallback = None,
) -> Any:
    if not REGISTRE_OUTILS:
        charger_tous_les_outils()

    nom_clean = nom_outil.strip()
    if nom_clean not in REGISTRE_OUTILS:
        return f"ERREUR: Outil '{nom_clean}' non répertorié."

    spec = REGISTRE_OUTILS[nom_clean]

    if spec.tier == SecurityTier.CONFIRM and confirmer:
        autorise = confirmer(nom_clean, args)
        if not autorise:
            return f"⛔ Action '{nom_clean}' refusée par l'utilisateur."

    try:
        sig = inspect.signature(spec.fonction)
        args_filtres = {}
        for p_name, param in sig.parameters.items():
            if p_name in args:
                args_filtres[p_name] = args[p_name]
            elif param.default is not inspect.Parameter.empty:
                args_filtres[p_name] = param.default

        return spec.fonction(**args_filtres)
    except Exception as e:
        logger.error(f"Erreur exécution outil [{nom_clean}] : {e}")
        return f"ERREUR lors de l'exécution de '{nom_clean}' : {e}"


charger_tous_les_outils()
