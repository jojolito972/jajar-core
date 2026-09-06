"""
test_afc_warning.py — Isole la source exacte du warning AFC de google-genai.
Lance ce script depuis ton dossier jarvis (venv activé) :
    python test_afc_warning.py
"""

import logging

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(name)s:%(message)s")

import config
from google.genai import types

client = config.GENAI_CLIENT

print("\n\n========== APPEL GEMINI EN COURS ==========\n")

response = client.models.generate_content(
    model="gemini-flash-lite-latest",
    contents=["Dis juste bonjour en un mot."],
    config=types.GenerateContentConfig(temperature=0.2),
)

print("\n========== FIN APPEL — REPONSE CI-DESSOUS ==========\n")
print(response.text)
