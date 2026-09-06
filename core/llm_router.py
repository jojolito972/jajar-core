from __future__ import annotations

"""
core/llm_router.py — Routeur Tri-Moteur avec Purge VRAM Automatique lors des Bascules.
Décharge immédiatement llama-server de la RAM dès que Denis active /cloud ou /nvidia.
"""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from typing import Any, Final, Literal, Optional

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*automatic function calling.*")
os.environ["PYTHONWARNINGS"] = "ignore"
logging.getLogger("google").setLevel(logging.ERROR)
logging.getLogger("google.genai").setLevel(logging.ERROR)

from google.genai import types
import config
from tools.local_model_manager import server_manager, lire_derniers_logs_llama

logger: Final[logging.Logger] = logging.getLogger("jajar.router")

ModeInference = Literal["cloud", "local", "nvidia"]


class LLMRouter:
    def __init__(self) -> None:
        self.client = config.GENAI_CLIENT
        self.mode_actif: ModeInference = "cloud"
        self.local_api_url: str = "http://127.0.0.1:8080/v1/chat/completions"
        self.nvidia_api_url: str = "https://integrate.api.nvidia.com/v1/chat/completions"
        self.nvidia_model_actif: str = "nvidia/nemotron-3-super-120b-a12b"
        self.modeles_nvidia_valides: list[str] = [
            "nvidia/nemotron-3-super-120b-a12b",
            "minimaxai/minimax-m3",
            "nvidia/nemotron-3.5-lightning-30b-a3b",
            "meta/llama-3.2-11b-vision-instruct",
        ]
        self.modeles_candidats_cloud: list[str] = [
            "gemini-3.6-flash",
            "gemini-flash-lite-latest",
            getattr(config, "MODELE_TEXTE_GEMINI", "gemini-3.6-flash"),
        ]
        self._modele_cloud_valide: str | None = None

    def _obtenir_cle_nvidia(self) -> str:
        key = os.getenv("NVIDIA_API_KEY", "")
        if not key:
            env_p = Path(config.BASE_DIR) / ".env"
            if env_p.exists():
                m = re.findall(r'nvapi-[A-Za-z0-9_-]+', env_p.read_text(encoding="utf-8", errors="ignore"))
                if m:
                    key = m[-1]
        return key

    def basculer_mode(self, nouveau_mode: ModeInference) -> str:
        """Bascule le moteur et libère la VRAM locale dès qu'on quitte le mode local."""
        if nouveau_mode == "local":
            if server_manager.est_en_ecoute():
                self.mode_actif = "local"
                return "🔒 **Mode 100% Local Activé :** Gemma 4 connecté sur GPU Metal (port 8080)."
            succes, msg = server_manager.garantir_modele_charge()
            if succes:
                self.mode_actif = "local"
                return f"🔒 **Mode 100% Local Activé :** {msg}"
            return f"⚠️ Échec activation locale :\n{msg}"

        # PURGE FORCÉE DE LA VRAM DÈS QU'ON QUITTE LE MODE LOCAL
        msg_purge = ""
        if server_manager.est_en_ecoute() or self.mode_actif == "local":
            msg_purge = f"\n{server_manager.arreter_serveur()}"

        if nouveau_mode == "nvidia":
            key = self._obtenir_cle_nvidia()
            if not key:
                return "⚠️ Clé NVIDIA_API_KEY introuvable dans le .env."
            self.mode_actif = "nvidia"
            return f"🟢 **Mode NVIDIA NIM H100 Activé :** Orchestrateur connecté à `{self.nvidia_model_actif}` (120B).{msg_purge}"

        self.mode_actif = "cloud"
        return f"⚡ **Mode Cloud Activé :** Orchestrateur connecté à Google Gemini 3.6 Flash.{msg_purge}"

    def _generer_nvidia_nim_streaming(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> tuple[str, str]:
        key = self._obtenir_cle_nvidia()
        if not key:
            return '{"thinking": "Erreur", "action": "final_answer", "answer": "⚠️ Clé NVIDIA manquante."}', "nvidia:error"

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }

        for model_target in self.modeles_nvidia_valides:
            payload = {
                "model": model_target,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": 2048,
                "stream": True
            }
            try:
                req = urllib.request.Request(self.nvidia_api_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                chunks = []
                with urllib.request.urlopen(req, timeout=30) as resp:
                    for line in resp:
                        l_str = line.decode("utf-8", errors="ignore").strip()
                        if not l_str.startswith("data:"):
                            continue
                        chunk_data = l_str[5:].strip()
                        if chunk_data == "[DONE]":
                            break
                        try:
                            d = json.loads(chunk_data)
                            delta = d.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                chunks.append(delta)
                        except Exception:
                            continue

                texte_final = "".join(chunks).strip()
                if texte_final:
                    self.nvidia_model_actif = model_target
                    return texte_final, f"nvidia:{model_target}"

            except Exception as e:
                logger.debug(f"Bascule modèle NVIDIA [{model_target}] : {e}")
                continue

        return "⚠️ Modèles NVIDIA temporairement occupés.", "nvidia:error"

    def _generer_local_metal_streaming(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> tuple[str, str]:
        if not server_manager.est_en_ecoute():
            succes, msg = server_manager.garantir_modele_charge()
            if not succes:
                return f'{{"thinking": "Serveur local indisponible", "action": "final_answer", "answer": "⚠️ Erreur : {msg}"}}', "local:error"

        server_manager.last_activity_ts = time.time()
        prompt_local_system = (
            "Tu es JAJAR en mode 100% LOCAL sur Apple Silicon.\n"
            "Réponds en JSON strict : {\"thinking\": \"...\", \"action\": \"final_answer\", \"answer\": \"...\"}"
        )
        payload = {
            "messages": [
                {"role": "system", "content": prompt_local_system},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": 512,
            "stream": True
        }
        req = urllib.request.Request(
            self.local_api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            method="POST"
        )
        chunks: list[str] = []
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    l_str = line.decode("utf-8", errors="ignore").strip()
                    if not l_str.startswith("data:"):
                        continue
                    chunk_data = l_str[5:].strip()
                    if chunk_data == "[DONE]":
                        break
                    try:
                        d = json.loads(chunk_data)
                        delta = d.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            chunks.append(delta)
                    except Exception:
                        continue
            texte_final = "".join(chunks).strip() or "Opération terminée en local."
            nom_m = server_manager.active_model_path.name if server_manager.active_model_path else "gemma-4"
            return texte_final, f"local:metal-{nom_m}"
        except Exception as e:
            return f'{{"thinking": "Interruption", "action": "final_answer", "answer": "⚠️ Flux local interrompu ({e})."}}', "local:error"

    def _generer_cloud_gemini(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> tuple[str, str]:
        candidats = [self._modele_cloud_valide] + self.modeles_candidats_cloud if self._modele_cloud_valide else self.modeles_candidats_cloud
        candidats_uniques = [m for m in dict.fromkeys(candidats) if m]
        derniere_erreur = ""

        for model_name in candidats_uniques:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=[user_prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                    ),
                )
                if response.text and response.text.strip():
                    self._modele_cloud_valide = model_name
                    return response.text.strip(), f"cloud:{model_name}"
            except Exception as e:
                derniere_erreur = str(e)
                continue

        msg_erreur = f"⚠️ Erreur API Google Cloud : {derniere_erreur}. Tape /local ou /nvidia pour basculer."
        return f'{{"thinking": "Erreur Cloud", "action": "final_answer", "answer": "{msg_erreur}"}}', "cloud:error"

    def generer(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> tuple[str, str]:
        if self.mode_actif == "local":
            return self._generer_local_metal_streaming(system_prompt, user_prompt, temperature)
        elif self.mode_actif == "nvidia":
            return self._generer_nvidia_nim_streaming(system_prompt, user_prompt, temperature)
        return self._generer_cloud_gemini(system_prompt, user_prompt, temperature)

    def embed(self, textes: list[str]) -> tuple[list[list[float]], str]:
        if not textes:
            return [], "none"
        candidats_emb = ["text-embedding-004", "embedding-001", "models/text-embedding-004"]
        for emb_model in candidats_emb:
            try:
                res = self.client.models.embed_content(model=emb_model, contents=textes)
                if hasattr(res, "embeddings") and res.embeddings:
                    return [e.values for e in res.embeddings], emb_model
            except Exception:
                continue
        return [[0.0] * 768 for _ in textes], "local:fallback_zeros"


router: Final[LLMRouter] = LLMRouter()
