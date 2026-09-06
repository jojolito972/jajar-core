import os
import re
import json
import requests
import time
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
    "Accept": "application/json"
}

print("🔍 1. Interrogation du catalogue réel NVIDIA NIM (GET /v1/models)...")
try:
    resp = requests.get("https://integrate.api.nvidia.com/v1/models", headers=headers, timeout=10)
    if resp.status_code != 200:
        print(f"❌ Erreur accès catalogue ({resp.status_code}) : {resp.text}")
        exit(1)
        
    modeles_data = resp.json().get("data", [])
    modeles_ids = [m["id"] for m in modeles_data if "id" in m]
    print(f"✅ {len(modeles_ids)} modèles actuellement actifs sur votre compte NVIDIA !")
    
    # Filtrer les meilleurs modèles de texte / chat disponibles
    candidats_prioritaires = [
        "deepseek-ai/deepseek-r1",
        "deepseek-ai/deepseek-v3",
        "meta/llama-3.1-405b-instruct",
        "meta/llama-3.1-70b-instruct",
        "meta/llama-3.1-8b-instruct",
        "mistralai/mixtral-8x7b-instruct-v0.1",
        "mistralai/mistral-7b-instruct-v0.3",
        "nvidia/nemotron-4-340b-instruct",
        "moonshotai/kimi-k3",
    ]
    
    modeles_valides = [m for m in candidats_prioritaires if m in modeles_ids]
    if not modeles_valides:
        # Fallback : prendre les 5 premiers modèles de type chat/instruct du catalogue
        modeles_valides = [m for m in modeles_ids if "instruct" in m or "chat" in m][:5]
        
    print(f"\n🎯 Modèles recommandés détectés : {modeles_valides}")

except Exception as e:
    print(f"❌ Erreur de récupération catalogue : {e}")
    exit(1)

# --- 2. Test d'inférence réel en direct ---
invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
headers_chat = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "text/event-stream",
    "Content-Type": "application/json"
}

for model_target in modeles_valides:
    print(f"\n⚡ Test d'inférence en streaming sur [{model_target}]...")
    payload = {
        "model": model_target,
        "messages": [{"role": "user", "content": "Présente-toi en une phrase percutante pour Denis."}],
        "max_tokens": 128,
        "temperature": 0.2,
        "stream": True
    }
    t0 = time.time()
    try:
        r = requests.post(invoke_url, headers=headers_chat, json=payload, stream=True, timeout=20)
        if r.status_code == 200:
            print("🤖 Réponse reçue : ", end="")
            for line in r.iter_lines():
                if line:
                    l_str = line.decode("utf-8")
                    if l_str.startswith("data: "):
                        data_str = l_str[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            d = json.loads(data_str)
                            delta = d.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            print(delta, end="", flush=True)
                        except Exception:
                            pass
            print(f"\n⏱️ Temps de réponse : {round(time.time() - t0, 2)}s (200 OK)")
            print(f"\n🏆 VICTOIRE : Le modèle [{model_target}] est 100% opérationnel sur NVIDIA NIM !")
            break
        else:
            print(f"⚠️ Échec sur {model_target} ({r.status_code}) : {r.text[:120]}")
    except Exception as err:
        print(f"⚠️ Erreur sur {model_target} : {err}")
