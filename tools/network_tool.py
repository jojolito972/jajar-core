"""
tools/network_tool.py — Outils réseau et SSH durcis avec exécution directe et validation RFC 1123.
"""

from __future__ import annotations

import subprocess
from typing import Final

import config
from config import SecurityTier
from core.security import SecurityViolation, valider_hote_ssh
from core.tools_registry import outil


@outil(tier=SecurityTier.AUTO)
def scanner_reseau_local() -> str:
    """Scanne les appareils actifs sur le réseau local via la table ARP."""
    try:
        res = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10)
        return res.stdout.strip() or "Aucun appareil détecté."
    except Exception as e:
        return f"Erreur lors du scan réseau : {e}"


@outil(tier=SecurityTier.AUTO)
def ouvrir_ecran_distant(nom_hote: str) -> str:
    """Ouvre une session de partage d'écran (VNC) vers un Mac distant."""
    try:
        hote_valide = valider_hote_ssh(nom_hote)
        subprocess.run(["open", f"vnc://{hote_valide}"], check=True, timeout=5)
        return f"Lancement de la connexion VNC vers {hote_valide}..."
    except SecurityViolation as e:
        return f"⛔ Hôte refusé : {e}"
    except Exception as e:
        return f"Échec VNC : {e}"


@outil(tier=SecurityTier.AUTO)
def executer_commande_ssh(nom_hote: str, commande: str = "ls -la", utilisateur: str = "") -> str:
    """Exécute une commande distante via SSH sans blocage (Sécurisé RFC 1123)."""
    try:
        cible = valider_hote_ssh(nom_hote, utilisateur)
    except SecurityViolation as e:
        return f"⛔ Refus de sécurité SSH : {e}"

    try:
        res = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes", cible, commande],
            shell=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        sortie = (res.stdout + res.stderr).strip()
        if res.returncode == 0:
            return f"✅ Succès SSH ({cible}) :\n{sortie or 'Commande exécutée.'}"
        return f"⚠️ Retour SSH ({res.returncode}) : {sortie}"
    except subprocess.TimeoutExpired:
        return f"⚠️ Timeout SSH sur {cible} (30s dépassées)."
    except Exception as e:
        return f"Erreur connexion SSH vers {cible} : {e}"


@outil(tier=SecurityTier.AUTO)
def monter_partage_smb(nom_hote: str, dossier_partage: str) -> str:
    """Monte un dossier réseau partagé (SMB) dans le Finder."""
    try:
        hote_valide = valider_hote_ssh(nom_hote)
        dossier_clean = dossier_partage.strip().replace("..", "").strip("/")
        subprocess.run(["open", f"smb://{hote_valide}/{dossier_clean}"], check=True, timeout=5)
        return f"Ouverture du partage SMB {hote_valide}/{dossier_clean}..."
    except SecurityViolation as e:
        return f"⛔ Hôte invalide : {e}"
    except Exception as e:
        return f"Erreur de montage SMB : {e}"


@outil(tier=SecurityTier.AUTO)
def envoyer_notification_macos(titre: str, message: str) -> str:
    """Affiche une notification système native sur macOS de manière sécurisée."""
    clean_titre = titre.replace('"', '\\"').replace("\n", " ")
    clean_msg = message.replace('"', '\\"').replace("\n", " ")
    script = f'display notification "{clean_msg}" with title "{clean_titre}"'
    try:
        proc = subprocess.Popen(["osascript", "-"], stdin=subprocess.PIPE, text=True)
        proc.communicate(input=script, timeout=5)
        return "Notification envoyée."
    except Exception as e:
        return f"Erreur notification : {e}"
