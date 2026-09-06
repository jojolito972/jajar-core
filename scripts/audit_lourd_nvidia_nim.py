from __future__ import annotations

"""
scripts/audit_lourd_nvidia_nim.py — Pipeline d'Audit Lourd et d'Analyse Architecturale SOTA.
Propulsé par NVIDIA NIM (nvidia/nemotron-3-super-120b-a12b sur clusters H100).
"""

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path("/Users/denmac/Assistant_IA/jarvis")
ENV_PATH = BASE_DIR / ".env"
OUTPUT_REPORT_PATH = BASE_DIR / "sandbox_audit" / "AUDIT_NVIDIA_NIM_SOTA.md"


def extraire_cle_nvidia() -> str:
    """Extrait proprement la clé NVIDIA_API_KEY depuis le .env."""
    if not ENV_PATH.exists():
        print(f"❌ Fichier .env introuvable dans {ENV_PATH}")
        sys.exit(1)

    contenu = ENV_PATH.read_text(encoding="utf-8", errors="ignore")
    m_var = re.search(r'NVIDIA_API_KEY\s*=\s*["\x27]?(nvapi-[A-Za-z0-9_-]+)["\x27]?', contenu)
    if m_var:
        return m_var.group(1)

    m_token = re.findall(r'nvapi-[A-Za-z0-9_-]+', contenu)
    if m_token:
        return m_token[-1]

    print("❌ Aucune clé 'nvapi-...' trouvée dans le fichier .env.")
    sys.exit(1)


def charger_fichiers_sources() -> str:
    """Agrège le code source des modules critiques pour l'analyse par le modèle 120B."""
    fichiers_cibles = [
        "core/engine.py",
        "core/state.py",
        "core/llm_router.py",
        "core/tools_registry.py",
        "core/security.py",
        "run_jarvis.py",
        "tools/system_tools.py",
        "tools/local_model_manager.py",
    ]
    
    corpus = []
    total_lignes = 0
    
    for rel_path in fichiers_cibles:
        full_path = BASE_DIR / rel_path
        if full_path.exists():
            texte = full_path.read_text(encoding="utf-8", errors="ignore")
            lignes = len(texte.splitlines())
            total_lignes += lignes
            corpus.append(
                f"================================================================================\n"
                f"FICHIER : {rel_path} ({lignes} lignes)\n"
                f"================================================================================\n"
                f"{texte}\n"
            )

    print(f"📦 Codebase agrégée : {len(corpus)} fichiers critiques ({total_lignes} lignes de code).")
    return "\n".join(corpus)


def executer_audit_nvidia_h100(codebase_str: str, api_key: str) -> str:
    """Interroge Nemotron-3 Super 120B sur NVIDIA NIM en streaming."""
    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    model_name = "nvidia/nemotron-3-super-120b-a12b"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    prompt_system = (
        "Tu es le Principal AI Research Engineer & Systems Architect Suprême chez NVIDIA et Apple.\n"
        "Tu réalises un audit de code impitoyable (no-kill, zéro complaisance, zéro flatterie) "
        "sur l'architecture d'un système d'exploitation IA personnel (JARVIS sur macOS Apple Silicon).\n\n"
        "DIRECTIVES STRICTES D'ANALYSE FACTUELLE :\n"
        "1. Identifie chaque goulot d'étranglement de latence, allocation mémoire inutile, fuite d'event loop ou I/O bloquante.\n"
        "2. Relève les failles de concurrence, deadlocks potentiels et mauvaise gestion des threads/asyncio.\n"
        "3. Fournis des blocs de refactorisation en code Python de production (strictement typé, zéro placeholder).\n"
        "4. Évalue la sécurité, le sandboxing et la robustesse face aux pannes d'API.\n"
        "5. Rédige un rapport dense, hautement technique, structuré en Markdown chirurgical."
    )

    prompt_user = (
        f"Voici l'intégralité du code source du cœur de JARVIS sur macOS :\n\n"
        f"{codebase_str}\n\n"
        "Livre ton diagnostic d'ingénierie complet et ton plan de refactorisation immédiat."
    )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": prompt_system},
            {"role": "user", "content": prompt_user},
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
        "stream": True,
    }

    print(f"⚡ Connexion aux clusters GPU H100 ({model_name})...\n")
    req = urllib.request.Request(
        invoke_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    chunks = []
    t0 = time.time()

    with urllib.request.urlopen(req, timeout=180) as resp:
        for line in resp:
            l_str = line.decode("utf-8", errors="ignore").strip()
            if not l_str.startswith("data:"):
                continue
            data_str = l_str[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                d = json.loads(data_str)
                delta = d.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    chunks.append(delta)
                    sys.stdout.write(delta)
                    sys.stdout.flush()
            except Exception:
                continue

    duree = round(time.time() - t0, 2)
    print(f"\n\n⏱️ Audit 120B achevé en {duree}s.")
    return "".join(chunks)


def main() -> None:
    print("\n" + "=" * 80)
    print("🚀 LANCEMENT DU PIPELINE D'AUDIT LOURD VIA NVIDIA NIM H100 (120B)")
    print("=" * 80 + "\n")

    api_key = extraire_cle_nvidia()
    print(f"🔑 Clé NVIDIA active : {api_key[:12]}...{api_key[-6:]}")

    codebase_str = charger_fichiers_sources()
    
    OUTPUT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rapport = executer_audit_nvidia_h100(codebase_str, api_key)

    OUTPUT_REPORT_PATH.write_text(rapport, encoding="utf-8")
    print("\n" + "=" * 80)
    print(f"✅ RAPPORT D'AUDIT COMPLET ENREGISTRÉ DANS :\n   {OUTPUT_REPORT_PATH}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
