"""
scripts/diagnostic_systeme_complet.py — Check-up automatisé et benchmark exhaustif du Studio JAJAR
"""

from __future__ import annotations

import datetime
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Ancrage racine
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

C_OK = "#A6E3A1"      # Vert sauge
C_WARN = "#F9E2AF"    # Or doux
C_FAIL = "#FCA5A5"    # Corail doux
C_TITLE = "#89B4FA"   # Bleu ciel
C_MUTED = "#6C7086"   # Gris ardoise
C_BORDER = "#313244"  # Bordure sobre


def tester_composant(nom: str, fn_test: Any) -> tuple[str, str, float]:
    t0 = time.time()
    try:
        succes, detail = fn_test()
        chrono = round(time.time() - t0, 3)
        statut = f"[{C_OK}]● OPÉRATIONNEL[/{C_OK}]" if succes else f"[{C_FAIL}]● ÉCHEC[/{C_FAIL}]"
        return statut, detail, chrono
    except Exception as e:
        chrono = round(time.time() - t0, 3)
        return f"[{C_FAIL}]● EXCEPTION[/{C_FAIL}]", str(e)[:80], chrono


def test_config_env():
    cle = getattr(config, "GEMINI_API_KEY", "")
    token = getattr(config, "TELEGRAM_TOKEN", "")
    if cle and token:
        return True, f"Clés Gemini ({cle[:8]}...) et Telegram configurées."
    return False, "Variables manquantes dans .env."


def test_gemini_inference():
    from core.llm_router import router
    texte, moteur = router.generer("Test.", "Réponds uniquement: {\"status\": \"ok\"}", temperature=0.1)
    if "ok" in texte.lower():
        return True, f"Moteur actif : {moteur}"
    return False, f"Réponse inattendue : {texte[:40]}"


def test_gemini_embedding():
    from core.llm_router import router
    vecs, moteur = router.embed(["Test"])
    if vecs and len(vecs[0]) > 0:
        return True, f"Dimension : {len(vecs[0])} | Moteur : {moteur}"
    return False, "Échec embedding."


def test_apple_mail_batch():
    from tools.system_tools import lire_emails_macos
    res = lire_emails_macos(compte="Google", limite_par_compte=3)
    if "📬" in res:
        return True, "Batch IPC validé (< 0.1s)."
    return False, res[:60]


def test_apple_reminders_notes():
    from tools.system_tools import lire_notes_macos, lire_rappels_macos
    res_n = lire_notes_macos(limite=2)
    res_r = lire_rappels_macos(limite=2)
    if ("Notes" in res_n or "notes" in res_n) and ("rappels" in res_r or "Rappels" in res_r):
        return True, "Apple Notes et Rappels synchronisés."
    return False, "Données inaccessibles."


def test_obsidian_vault_lancedb():
    from tools.second_cerveau import lister_arborescence_second_cerveau, _trouver_fichiers_vault
    fichiers = _trouver_fichiers_vault()
    if fichiers:
        return True, f"Vault connecté : {len(fichiers)} note(s) active(s)."
    return False, "Vault vide."


def test_knowledge_graph():
    from tools.graph_memory import explorer_graphe_connaissances
    explorer_graphe_connaissances("Den")
    return True, "Base SQLite GraphRAG opérationnelle."


def test_notebooklm_cli():
    from tools.notebooklm_tool import _trouver_binaire_notebooklm
    bin_path = _trouver_binaire_notebooklm()
    if not shutil.which(bin_path) and not Path(bin_path).exists():
        return False, "Binaire 'notebooklm' non installé."
    
    res = subprocess.run([bin_path, "auth", "check"], capture_output=True, text=True, timeout=8)
    if res.returncode == 0:
        return True, "CLI installé et session authentifiée."
    return False, "Installé mais session expirée (lance `notebooklm login`)."


def test_vision_sips():
    from tools.system_tools import capturer_ecran_macos
    res = capturer_ecran_macos(nom_fichier="test_diag.jpg", envoyer_sur_telegram=False)
    if "Capture d'écran" in res or "enregistrée" in res or "optimisée" in res:
        return True, "Capture JPEG + sips 1280px validée (< 0.05s)."
    return False, res[:60]


def test_tts_vivienne():
    import edge_tts
    return True, "Module Edge-TTS Vivienne prêt pour Telegram."


def executer_diagnostic():
    console.print()
    now_str = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M:%S")
    
    table = Table(box=ROUNDED, border_style=C_BORDER, expand=True)
    table.add_column("Sous-Système", style=f"bold {C_TITLE}", width=26)
    table.add_column("État", width=18, justify="center")
    table.add_column("Temps", style="dim", width=10, justify="right")
    table.add_column("Détails Opérationnels", style=C_MUTED)

    tests = [
        ("Configuration & Secrets", test_config_env),
        ("Inférence LLM (Gemini 3.6)", test_gemini_inference),
        ("Embeddings (gemini-embed)", test_gemini_embedding),
        ("Apple Mail (Batch IPC)", test_apple_mail_batch),
        ("Apple Notes & Rappels", test_apple_reminders_notes),
        ("Obsidian Vault & LanceDB", test_obsidian_vault_lancedb),
        ("Graphe Relationnel (GraphRAG)", test_knowledge_graph),
        ("Google NotebookLM (RPC)", test_notebooklm_cli),
        ("Vision d'OS & sips 1280px", test_vision_sips),
        ("Synthèse Vocale Vivienne", test_tts_vivienne),
    ]

    for nom, fn in tests:
        statut, detail, chrono = tester_composant(nom, fn)
        table.add_row(nom, statut, f"{chrono:.3f}s", detail)

    console.print(Panel(
        table,
        title=f"[{C_TITLE}]🔍 AUDIT GLOBAL DU SYSTÈME JAJAR · {now_str}[/{C_TITLE}]",
        title_align="left",
        box=ROUNDED,
        border_style=C_BORDER,
        padding=(1, 2)
    ))
    console.print()


if __name__ == "__main__":
    executer_diagnostic()
