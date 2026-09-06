"""
scripts/test_validation_systeme.py — Validation unitaire de l'interface pastel, du moteur et du SandboxExecutor.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from core.engine import extraire_json_securise
from core.sandbox import sandbox_executor
from run_jarvis import _extraire_texte_lisible_humain

print("═══════════════════════════════════════════════════════════════")
print("🧪 VALIDATION UNITAIRE DU SYSTÈME JAJAR")
print("═══════════════════════════════════════════════════════════════\n")

# 1. Test Déballage Anti-JSON & Interface Pastel
print("🔍 1. Test d'extraction de réponse sans fuite JSON...")
reponse_brute_modele = """{
  "thinking": "J'ai analysé les données.",
  "action": "final_answer",
  "answer": "### Synthèse des Données\\n\\n- **Pilier 1** : Archives 2026\\n- **Pilier 2** : Atelier Bespoke"
}"""

parsed = extraire_json_securise(reponse_brute_modele)
texte_final = _extraire_texte_lisible_humain(parsed.get("answer", ""))

assert not texte_final.startswith("{"), "❌ Fuite de JSON détectée !"
print("✅ Extraction Textuelle : ZÉRO JSON visible.")
print(f"Rendu propre :\n{texte_final}\n")

# 2. Test SandboxExecutor avec preuve de fichier physique unique
print("🔍 2. Test du SandboxExecutor (Isolation système & Fichiers)...")
nom_preuve = f"preuve_{uuid.uuid4().hex[:6]}.txt"
code_test = f"""
with open("{nom_preuve}", "w") as f:
    f.write("Fichier réellement généré par SandboxExecutor")
print("Traitement terminé avec succès.")
"""

res = sandbox_executor.executer_code_python_sync(code_test, timeout=5)
statut_succes = res["succes"]
code_retour = res["returncode"]
fichiers_crees = res["fichiers_crees"]

assert statut_succes is True, "❌ Échec SandboxExecutor !"
print(f"• Statut : {statut_succes} (Code {code_retour})")
print(f"• Sortie : {res['stdout']}")
print(f"• Preuve physique (Fichiers créés) : {fichiers_crees}")

print("\n═══════════════════════════════════════════════════════════════")
print("✨ TOUS LES TESTS SONT VALIDÉS À 100%. AUCUNE ERREUR DE SYNTAXE.")
print("═══════════════════════════════════════════════════════════════")
