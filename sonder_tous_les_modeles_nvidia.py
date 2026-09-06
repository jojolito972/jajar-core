import os
import re
import json
import requests
import concurrent.futures
from pathlib import Path
from dotenv import load_dotenv

env_path = Path("/Users/denmac/Assistant_IA/jarvis/.env")
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("NVIDIA_API_KEY", "")
if not api_key and env_path.exists():
    texte = env_path.read_text(encoding="utf-8", errors="ignore")
    m = re.findall(r'nvapi-[A-Za-z0-9_-]+', texte)
    if m:
        api_key = m[-1]

if not api_key:
    print("❌ Aucune clé NVIDIA_API_KEY trouvée !")
    exit(1)

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

print("🔍 Récupération des modèles du catalogue NVIDIA...")
resp = requests.get("https://integrate.api.nvidia.com/v1/models", headers=headers, timeout=10)
if resp.status_code != 200:
    print(f"❌ Erreur catalogue : {resp.status_code}")
    exit(1)

modeles = [m["id"] for m in resp.json().get("data", []) if "id" in m]
print(f"📋 {len(modeles)} modèles trouvés. Sondage en cours...")

invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"

modeles_actifs_200 = []
modeles_non_autorises_404 = []

def tester_modele(model_id):
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1
    }
    try:
        r = requests.post(invoke_url, headers=headers, json=payload, timeout=5)
        if r.status_code == 200:
            return model_id, True, "200 OK"
        elif "Not found for account" in r.text or r.status_code == 404:
            return model_id, False, "Non activé sur le compte (404)"
        else:
            return model_id, False, f"HTTP {r.status_code}"
    except Exception as e:
        return model_id, False, f"Timeout / Erreur"

# Sondage parallèle de 10 requêtes à la fois pour tester les 82 modèles en 5 secondes
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    resultats = list(executor.map(tester_modele, modeles))

for m_id, succes, raison in resultats:
    if succes:
        modeles_actifs_200.append(m_id)
    else:
        modeles_non_autorises_404.append((m_id, raison))

print("\n" + "="*80)
print(f"🏆 MODÈLES DÉJÀ DÉVERROUILLÉS ET OPÉRATIONNELS POUR VOTRE CLÉ ({len(modeles_actifs_200)}) :")
print("="*80)
if modeles_actifs_200:
    for m in modeles_actifs_200:
        print(f"  ✅ {m}")
else:
    print("  ⚠️ Aucun modèle n'est encore déverrouillé sur ce compte.")
    print("  👉 Allez sur https://build.nvidia.com, ouvrez la page du modèle de votre choix (ex: kimi-k3 ou llama-3.1-70b) et cliquez sur 'Get API Key' pour accepter les conditions.")

print("\n" + "="*80)
