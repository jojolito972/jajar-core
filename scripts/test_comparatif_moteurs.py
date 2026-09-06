"""
scripts/test_comparatif_moteurs.py — Banc d'essai comparatif haute résolution
Teste Google Imagen 3 et Hugging Face FLUX.1 de manière isolée et ouvre les rendus dans Aperçu.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config

print("═══════════════════════════════════════════════════════════════")
print("🧪 BANC D'ESSAI COMPARATIF : GOOGLE IMAGEN 3 VS HUGGING FACE FLUX.1")
print("═══════════════════════════════════════════════════════════════\n")

# PROMPT PHOTOGRAPHIQUE PROFESSIONNEL (Anti-Poupée / Argentique 35mm)
PROMPT_TEST = (
    "A raw candid medium portrait photograph of a 28-year-old artisan woman in her leather workshop, "
    "natural skin texture with visible pores and subtle imperfections, no makeup, natural eyes, "
    "warm daylight coming from a side window, depth of field, 35mm film aesthetic, Kodak Portra 400, "
    "extremely detailed textures, master photography, no CGI, no doll look"
)

images_a_ouvrir: list[Path] = []

# ---------------------------------------------------------------------------
# TEST 1 : GOOGLE IMAGEN 3 (VIA GEMINI_API_KEY)
# ---------------------------------------------------------------------------
print("🔍 1. TEST DU MOTEUR GOOGLE IMAGEN 3 (Google AI Studio)...")
t0_google = time.time()
fichier_google = config.IMAGE_DIR / "test_comparatif_google_imagen3.jpg"

try:
    from google.genai import types
    client_gemini = config.GENAI_CLIENT

    print(f"   • Modèle ciblé : `imagen-3.0-generate-002`")
    print(f"   • Clé API active : {config.GEMINI_API_KEY[:6]}...{config.GEMINI_API_KEY[-4:]}")

    res_imagen = client_gemini.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt=PROMPT_TEST,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="3:4",
            output_mime_type="image/jpeg",
            person_generation="ALLOW_ADULT",
        ),
    )

    if res_imagen.generated_images and res_imagen.generated_images[0].image.image_bytes:
        data_google = res_imagen.generated_images[0].image.image_bytes
        fichier_google.write_bytes(data_google)
        chrono_google = round(time.time() - t0_google, 2)
        poids_ko = round(len(data_google) / 1024, 1)

        print(f"   ✅ SUCCÈS GOOGLE IMAGEN 3 !")
        print(f"      - Fichier : `{fichier_google.name}` ({poids_ko} Ko)")
        print(f"      - Temps de génération : {chrono_google}s")
        images_a_ouvrir.append(fichier_google)
    else:
        print("   ⚠️ Réponse reçue sans flux d'image exploitable.")

except Exception as err_g:
    chrono_google = round(time.time() - t0_google, 2)
    print(f"   ❌ Échec Google Imagen 3 ({chrono_google}s) :")
    print(f"      Détail de l'erreur : {err_g}")
    if "404" in str(err_g) or "403" in str(err_g) or "RESOURCE_EXHAUSTED" in str(err_g):
        print("      💡 Cause : Le modèle Imagen 3 nécessite l'activation du mode Pay-As-You-Go sur aistudio.google.com.")

# ---------------------------------------------------------------------------
# TEST 2 : HUGGING FACE FLUX.1-SCHNELL (VIA HUGGINGFACE_API_KEY)
# ---------------------------------------------------------------------------
print("\n───────────────────────────────────────────────────────────────")
print("🔍 2. TEST DU MOTEUR HUGGING FACE FLUX.1-SCHNELL...")
t0_hf = time.time()
fichier_hf = config.IMAGE_DIR / "test_comparatif_hf_flux.png"
hf_token = getattr(config, "HUGGINGFACE_API_KEY", "")

if not hf_token:
    print("   ⚠️ Clé HUGGINGFACE_API_KEY absente du fichier .env.")
else:
    print(f"   • Modèle ciblé : `black-forest-labs/FLUX.1-schnell`")
    print(f"   • Token HF actif : {hf_token[:6]}...{hf_token[-4:]}")

    succes_hf = False

    # Méthode A : Client officiel huggingface_hub si installé
    try:
        from huggingface_hub import InferenceClient
        hf_client = InferenceClient(provider="hf-inference", api_key=hf_token)
        img_pil = hf_client.text_to_image(
            prompt=PROMPT_TEST,
            model="black-forest-labs/FLUX.1-schnell",
            width=896,
            height=1152,
        )
        img_pil.save(str(fichier_hf), format="PNG")
        chrono_hf = round(time.time() - t0_hf, 2)
        poids_ko = round(fichier_hf.stat().st_size / 1024, 1)

        print(f"   ✅ SUCCÈS HUGGING FACE (Via SDK InferenceClient) !")
        print(f"      - Fichier : `{fichier_hf.name}` ({poids_ko} Ko)")
        print(f"      - Temps de génération : {chrono_hf}s")
        images_a_ouvrir.append(fichier_hf)
        succes_hf = True
    except ImportError:
        print("   ℹ️ Package huggingface_hub non installé, tentative via API HTTP REST directe...")
    except Exception as e_sdk:
        print(f"   ⚠️ Échec SDK HF : {e_sdk}, tentative HTTP directe...")

    # Méthode B : Fallback HTTP REST officiel (api-inference)
    if not succes_hf:
        endpoints_hf = [
            "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
            "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
        ]
        for url_endpoint in endpoints_hf:
            try:
                payload = json.dumps({
                    "inputs": PROMPT_TEST,
                    "parameters": {"width": 896, "height": 1152}
                }).encode("utf-8")

                req = urllib.request.Request(
                    url_endpoint,
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {hf_token}",
                        "Content-Type": "application/json",
                        "User-Agent": "JAJAR-Test/2.0",
                    },
                    method="POST"
                )

                with urllib.request.urlopen(req, timeout=60) as resp:
                    if resp.status == 200:
                        data_hf = resp.read()
                        if len(data_hf) > 10000:
                            fichier_hf.write_bytes(data_hf)
                            chrono_hf = round(time.time() - t0_hf, 2)
                            poids_ko = round(len(data_hf) / 1024, 1)

                            print(f"   ✅ SUCCÈS HUGGING FACE (Via HTTP API {url_endpoint.split('/')[-2]}) !")
                            print(f"      - Fichier : `{fichier_hf.name}` ({poids_ko} Ko)")
                            print(f"      - Temps de génération : {chrono_hf}s")
                            images_a_ouvrir.append(fichier_hf)
                            succes_hf = True
                            break
            except Exception as e_http:
                print(f"   ⚠️ Échec endpoint {url_endpoint} : {e_http}")
                continue

        if not succes_hf:
            chrono_hf = round(time.time() - t0_hf, 2)
            print(f"   ❌ Échec complet Hugging Face ({chrono_hf}s).")

# ---------------------------------------------------------------------------
# OUVERTURE DES IMAGES DANS APERÇU (MACOS PREVIEW)
# ---------------------------------------------------------------------------
print("\n═══════════════════════════════════════════════════════════════")
if images_a_ouvrir:
    print(f"🖼️ Ouverture de {len(images_a_ouvrir)} image(s) dans Aperçu pour comparaison...")
    for img_p in images_a_ouvrir:
        subprocess.run(["open", "-a", "Preview", str(img_p)])
    print("✨ Comparez le piqué et le grain de peau directement sur votre écran.")
else:
    print("❌ Aucune image n'a pu être générée par les deux clés API.")
print("═══════════════════════════════════════════════════════════════")
