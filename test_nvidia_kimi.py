import os
import re
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# 1. Chargement robuste de la clé
env_path = Path("/Users/denmac/Assistant_IA/jarvis/.env")
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("NVIDIA_API_KEY", "")
if not api_key and env_path.exists():
    texte = env_path.read_text(encoding="utf-8", errors="ignore")
    m = re.findall(r'nvapi-[A-Za-z0-9_-]+', texte)
    if m:
        api_key = m[-1]

if not api_key:
    print("❌ ERREUR : Aucune clé NVIDIA_API_KEY trouvée !")
    exit(1)

print(f"🔑 Clé API chargée avec succès : {api_key[:12]}...{api_key[-6:]}")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "text/event-stream",
    "Content-Type": "application/json"
}

# --- TEST 1 : Vérification ultra-rapide des modèles disponibles (< 1s) ---
print("\n📡 Test 1 : Vérification du catalogue NVIDIA NIM (GET /v1/models)...")
try:
    resp_models = requests.get("https://integrate.api.nvidia.com/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
    if resp_models.status_code == 200:
        total_modeles = len(resp_models.json().get("data", []))
        print(f"✅ Authentification NVIDIA NIM validée (200 OK) — {total_modeles} modèles accessibles !")
    else:
        print(f"⚠️ Réponse catalogue ({resp_models.status_code}) : {resp_models.text[:200]}")
except Exception as e:
    print(f"⚠️ Erreur de sonde catalogue : {e}")

# --- TEST 2 : Envoi de la requête de chat Kimi-K3 en Streaming ---
model_target = "moonshotai/kimi-k3"
invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"

payload = {
    "model": model_target,
    "messages": [
        {
            "role": "user",
            "content": "Bonjour Kimi ! Peux-tu me confirmer en une phrase que tu réponds bien depuis l'infrastructure NVIDIA NIM pour Denis ?"
        }
    ],
    "max_tokens": 512,
    "temperature": 0.3,
    "stream": True
}

print(f"\n🚀 Test 2 : Envoi de la requête à {model_target} (Attente de l'allocation GPU)...")

try:
    # Timeout étendu à 180s pour absorber la file d'attente des modèles MoE 2.8T
    response = requests.post(invoke_url, headers=headers, json=payload, stream=True, timeout=(10, 180))
    print(f"📡 Statut HTTP : {response.status_code}")

    if response.status_code == 200:
        print("\n=== 🤖 RÉPONSE DE KIMI (STREAMING) ===\n")
        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data_str = line_str[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            print(delta, end="", flush=True)
                    except Exception:
                        pass
        print("\n\n✅ Connexion à Kimi via NVIDIA NIM 100% Réussie et Opérationnelle !")
    else:
        print(f"⚠️ Échec ({response.status_code}) : {response.text}")

except requests.exceptions.Timeout:
    print("\n⏳ Le modèle Kimi-K3 est en cours de chargement sur les clusters NVIDIA. Réessaie dans un instant.")
except Exception as e:
    print(f"\n❌ Erreur : {e}")
