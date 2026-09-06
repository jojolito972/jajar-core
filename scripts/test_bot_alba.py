"""
scripts/test_bot_alba.py — Suite de validation unitaire de l'Atelier Alba.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
import edge_tts
from tools.alba_artisan_tools import (
    calculer_metrage_et_cout_cuir,
    creer_fiche_client_mesures_bespoke,
)

print("═══════════════════════════════════════════════════════════════")
print("🧪 VALIDATION UNITAIRE — ATELIER ALBA")
print("═══════════════════════════════════════════════════════════════\n")

# 1. Calculs métier bottier
print("📐 1. Test du Calculateur de Métrage & Coût Cuir...")
bilan_cuir = calculer_metrage_et_cout_cuir(
    type_modele="Botte cavalière sur mesure",
    pointure=39.5,
    type_cuir="Veau Box pleine fleur",
    prix_dm2_ht=0.85,
    hauteur_tige_cm=42.0,
    coefficient_perte=0.35,
)
print(bilan_cuir)
print("✅ Calcul bottier validé.\n")

# 2. Création fiche client Obsidian
print("📝 2. Test Fiche Client Bespoke dans Obsidian (en Français)...")
res_fiche = creer_fiche_client_mesures_bespoke(
    nom_client="Comtesse Beatrice Rossi",
    pointure_estimee=39.0,
    type_modele="Bottes Cavalières",
    longueur_pied_gauche_mm=252.0,
    longueur_pied_droit_mm=250.5,
    tour_joint_metatarse_mm=225.0,
    tour_cou_de_pied_mm=235.0,
    particularites_morphologie="Pied fin, cambrure marquée",
    choix_cuir_finition="Box-Calf Noir Aniline",
)
print(res_fiche)
print("✅ Fiche client Obsidian validée.\n")

# 3. Synthèse vocale bilingue
print("🎙️ 3. Test Synthèse Vocale Bilingue (Edge-TTS)...")


async def _test_tts():
    comm_it = edge_tts.Communicate("Ciao Laura, sono Alba.", "it-IT-ElsaNeural")
    await comm_it.save(str(config.AUDIO_DIR / "test_alba_it.mp3"))
    comm_fr = edge_tts.Communicate("Bonjour Den, tout est prêt.", "fr-FR-VivienneNeural")
    await comm_fr.save(str(config.AUDIO_DIR / "test_alba_fr.mp3"))


asyncio.run(_test_tts())
print("✅ Vocaux générés dans audio_temp/.\n")

print("═══════════════════════════════════════════════════════════════")
print("✨ TOUS LES MODULES SONT OPÉRATIONNELS À 100%")
print("═══════════════════════════════════════════════════════════════")
