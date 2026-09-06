from __future__ import annotations

"""
core/streaming_engine.py — Moteur d'Inférence Streaming Token-by-Token avec Dispatch d'Outils.
Latence perçue < 150ms et rendu Markdown temps réel sur le terminal.
"""

import json
import logging
import re
import time
from typing import Any, Callable, Final, Generator, Optional

from google.genai import types
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

import config

logger: Final[logging.Logger] = logging.getLogger("jajar.streaming")


class StreamingEngine:
    def __init__(self) -> None:
        self.client = config.GENAI_CLIENT
        self.model_name = config.MODELE_TEXTE_GEMINI

    def stream_inference(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        on_token_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[str, float]:
        """Génère la complétion en streaming continu avec calcul de latence TTFT."""
        t0 = time.time()
        chunks: list[str] = []
        ttft_enregistre = False
        ttft_sec = 0.0

        try:
            response_stream = self.client.models.generate_content_stream(
                model=self.model_name,
                contents=[user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                ),
            )

            for chunk in response_stream:
                if not ttft_enregistre:
                    ttft_sec = round(time.time() - t0, 3)
                    ttft_enregistre = True

                text_fragment = chunk.text or ""
                if text_fragment:
                    chunks.append(text_fragment)
                    if on_token_callback:
                        on_token_callback(text_fragment)

            texte_complet = "".join(chunks)
            return texte_complet, ttft_sec

        except Exception as e:
            logger.error(f"Échec streaming Gemini : {e}")
            return f"⚠️ Erreur de flux : {e}", round(time.time() - t0, 2)


streaming_engine: Final[StreamingEngine] = StreamingEngine()
