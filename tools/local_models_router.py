"""
tools/local_models_router.py — Routeur local avec chargement à la demande et libération de RAM.
"""

from __future__ import annotations

import base64
import logging
import time
from pathlib import Path
from typing import Any, Final

import config
from config import SecurityTier
from core.tools_registry import outil
from tools.local_model_manager import server_manager

logger: Final[logging.Logger] = logging.getLogger("jajar.local_router")
LOCAL_ENDPOINT: Final[str] = "http://127.0.0.1:8080/v1"


@outil(tier=SecurityTier.AUTO)
def executer_analyse_rapide_qwen_vl(
    consigne_ou_question: str,
    chemin_image_ou_pdf: str = "",
) -> str:
    """Exécute une analyse locale ultra-rapide avec chargement automatique en RAM et extinction après 10 min."""
    from openai import OpenAI

    t0 = time.time()
    cible = Path(chemin_image_ou_pdf).expanduser().resolve() if chemin_image_ou_pdf else None

    # 1. Garantir que le modèle Qwen-VL est monté en RAM (Cold start < 1.5s si éteint)
    if not server_manager.garantir_modele_charge("qwenvl2b"):
        # Fallback automatique sur Gemini Cloud si le binaire local est absent
        from core.llm_router import router
        rep, mot = router.generer("Tu es un analyste visuel.", consigne_ou_question, temperature=0.2)
        return f"⚡ **Analyse Cloud ({mot}) :**\n\n{rep}"

    # 2. Construction du payload multimodal
    contenu_msg: list[dict[str, Any]] = []

    if cible and cible.exists() and cible.is_file():
        ext = cible.suffix.lower()
        if ext in (".jpg", ".jpeg", ".png", ".webp"):
            img_b64 = base64.b64encode(cible.read_bytes()).decode("utf-8")
            contenu_msg.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
            })
            contenu_msg.append({"type": "text", "text": f"Document / Image : {consigne_ou_question}"})
        elif ext == ".pdf":
            from tools.gemma_heavy_engine import _extraire_texte_pdf_reel
            txt_pdf = _extraire_texte_pdf_reel(cible, max_pages=6)
            contenu_msg.append({
                "type": "text",
                "text": f"Extrait du PDF '{cible.name}' :\n\n{txt_pdf[:5000]}\n\nConsigne : {consigne_ou_question}"
            })
    else:
        contenu_msg.append({"type": "text", "text": consigne_ou_question})

    prompt_systeme = (
        "Tu es Qwen-VL, l'analyste local ultra-rapide du Studio JAJAR pour Denis.\n"
        "Réponds en Français, de manière dense, nette et structurée en Markdown."
    )

    try:
        client = OpenAI(base_url=LOCAL_ENDPOINT, api_key="local")
        resp = client.chat.completions.create(
            model="qwen3-vl-2b",
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user", "content": contenu_msg}
            ],
            temperature=0.2,
            max_tokens=1000,
            timeout=45,
        )

        reponse = resp.choices[0].message.content or "Analyse terminée."
        chrono = round(time.time() - t0, 2)
        debit = round((len(reponse) // 4) / max(0.1, chrono), 1)

        return (
            f"⚡ **Analyse Locale Qwen-VL 2B ({chrono}s ➔ ~{debit} t/s) :**\n\n"
            f"{reponse}\n\n"
            f"[dim italic]💡 La mémoire RAM sera automatiquement libérée après 10 minutes d'inactivité.[/dim italic]"
        )

    except Exception as e:
        logger.error(f"Erreur inférence locale : {e}")
        return f"⚠️ Erreur locale : {e}"
