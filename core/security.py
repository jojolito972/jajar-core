from __future__ import annotations

"""
core/security.py — Moteur central de sécurité, classification de commandes et confinement I/O.
Intègre la validation SSH, la détection lecture seule et le blindage anti-destruction absolu.
"""

import ipaddress
import os
import re
import shlex
from pathlib import Path
from typing import Final

import config

HOSTNAME_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63}(?<!-))*$"
)
USERNAME_REGEX: Final[re.Pattern[str]] = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")

BINAIRES_LECTURE_SEULE: Final[frozenset[str]] = frozenset({
    "df", "du", "ls", "pwd", "find", "grep", "egrep", "fgrep", "cat", "head", "tail",
    "less", "more", "stat", "file", "which", "whereis", "whoami", "id", "uname",
    "sw_vers", "system_profiler", "top", "ps", "lsof", "uptime", "date", "mdfind",
    "mdls", "sort", "uniq", "wc", "awk", "cut", "tr", "sed", "echo", "printf",
    "netstat", "arp", "ifconfig", "ping", "traceroute", "otool", "nm"
})

OPERATEURS_PIPE_DANGEREUX: Final[re.Pattern[str]] = re.compile(
    r"\|\s*(?:bash|sh|zsh|python[23]?|perl|ruby|php|node|dash|ksh|eval|exec|sudo)\b",
    re.IGNORECASE
)

COMMANDES_CRITIQUES_INTERDITES: Final[list[str]] = [
    r"\brm\s+-[a-zA-Z]*[rf][a-zA-Z0-9_-]*\s+.*?(?:/|/\*|/System(?:/|\s|$)|/Users(?:/|\s|$)|/Library(?:/|\s|$)|/Applications(?:/|\s|$)|/Volumes(?:/|\s|$)|~|~/)",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r">\s*/dev/disk",
    r"\bchmod\s+-[a-zA-Z]*R[a-zA-Z]*\s+777\s+/\s*$",
    r":\(\)\s*\{\s*:\|:&\s*\};",
    r"\bdiskutil\s+(?:eraseDisk|eraseVolume|unmountDisk)\b",
]


class SecurityViolation(Exception):
    pass


def valider_confinement_chemin(chemin_demande: str | Path, base_autorisee: Path | None = None) -> Path:
    base = (base_autorisee or config.BASE_DIR).resolve()
    cible = Path(chemin_demande).expanduser().resolve()
    try:
        cible.relative_to(base)
    except ValueError:
        if base_autorisee is None and cible.is_relative_to(Path.home()):
            return cible
        raise SecurityViolation(f"Accès refusé : Le chemin '{cible}' est hors de la zone confinée '{base}'.")
    return cible


def assainir_nom_fichier(nom_fichier: str) -> str:
    base_name = Path(nom_fichier).name
    propre = re.sub(r"[^a-zA-Z0-9_.\-]", "_", base_name)
    if not propre or propre in (".", ".."):
        return f"fichier_securise_{os.urandom(4).hex()}"
    return propre


def valider_hote_ssh(nom_hote: str, utilisateur: str = "") -> str:
    cible = nom_hote.strip()
    if cible.startswith("-"):
        raise SecurityViolation("Le nom d'hôte SSH ne peut pas commencer par un tiret.")

    user_part = ""
    host_part = cible

    if "@" in cible:
        parts = cible.split("@", 1)
        user_part, host_part = parts[0], parts[1]
    elif utilisateur:
        user_part = utilisateur.strip()

    if user_part and not USERNAME_REGEX.match(user_part):
        raise SecurityViolation(f"Identifiant utilisateur SSH invalide : '{user_part}'")

    est_ip = False
    try:
        ipaddress.ip_address(host_part)
        est_ip = True
    except ValueError:
        pass

    if not est_ip and not HOSTNAME_REGEX.match(host_part):
        raise SecurityViolation(f"Nom d'hôte invalide pour la connexion : '{host_part}'")

    return f"{user_part}@{host_part}" if user_part else host_part


def est_commande_lecture_seule(commande_brute: str) -> bool:
    cmd = commande_brute.strip()
    if not cmd:
        return True
    if OPERATEURS_PIPE_DANGEREUX.search(cmd):
        return False
    if ("curl" in cmd or "wget" in cmd) and "|" in cmd:
        return False

    try:
        tokens_globaux = shlex.split(cmd)
    except Exception:
        return False

    symboles_redirection = {">", ">>", "1>", "2>", "&>", ">|", "1>>", "2>>"}
    for tok in tokens_globaux:
        if tok in symboles_redirection or any(tok.startswith(sr) for sr in (">", "1>", "2>", "&>")):
            return False

    mots_cles_chainage = {"&&", "||", ";", "|"}
    current_segment: list[str] = []
    segments: list[list[str]] = []

    for t in tokens_globaux:
        if t in mots_cles_chainage:
            if current_segment:
                segments.append(current_segment)
                current_segment = []
        else:
            current_segment.append(t)
    if current_segment:
        segments.append(current_segment)

    for seg in segments:
        if not seg:
            continue
        binaire = Path(seg[0]).name.lower()
        if binaire not in BINAIRES_LECTURE_SEULE:
            return False
        if binaire == "find" and any(arg in seg for arg in ("-exec", "-execdir", "-delete", "-ok", "-okdir")):
            return False
        if binaire in ("sed", "awk", "perl") and ("-i" in seg or "--in-place" in seg):
            return False

    return True


def verifier_commande_securisee(commande: str) -> None:
    cmd_clean = commande.strip()
    for motif in COMMANDES_CRITIQUES_INTERDITES:
        if re.search(motif, cmd_clean, re.IGNORECASE):
            raise SecurityViolation(f"COMMANDE DESTRUCTIVE BLOQUÉE PAR LA SÉCURITÉ : '{commande}'")
