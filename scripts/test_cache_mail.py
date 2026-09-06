"""
scripts/test_cache_mail.py — Test d'extraction Batch IPC Apple Mail & Cache Sémantique (< 30s)
"""

import sys
import time
from pathlib import Path

# Ancrage racine
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.system_tools
from core.tools_registry import executer_outil

print("═══════════════════════════════════════════════════════════════")
print("⚡ TEST 1 : Extraction Apple Mail réelle (Batch IPC < 0.1s)")
print("═══════════════════════════════════════════════════════════════")
t0 = time.time()
res1 = executer_outil('lire_emails_macos', {'compte': 'Google', 'limite_par_compte': 5}, 'jarvis')
t_appel1 = time.time() - t0
print(res1)
print(f"\n⏱️ Temps d'exécution Appel 1 : {t_appel1:.4f} seconde(s)\n")

print("═══════════════════════════════════════════════════════════════")
print("⚡ TEST 2 : Récupération Instantanée depuis le Cache Sémantique (< 30s)")
print("═══════════════════════════════════════════════════════════════")
t0 = time.time()
res2 = executer_outil('lire_emails_macos', {'compte': 'Google', 'limite_par_compte': 5}, 'jarvis')
t_appel2 = time.time() - t0
print(res2)
print(f"\n⚡ Temps d'accès Appel 2 (Cache) : {t_appel2:.6f} seconde(s)")
if t_appel2 > 0:
    print(f"🚀 Accélération mesurée : x{int(t_appel1 / t_appel2)} plus rapide !")
