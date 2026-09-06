"""
automation/bot_laura_puntillo.py — Assistant Dédié pour Madame Laura Puntillo & Persona Alba
Fonctionne à 100% à distance (4G/5G/Wi-Fi) via Telegram Cloud sans aucune configuration réseau.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from google.genai import types
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

logger: Final[logging.Logger] = logging.getLogger("jajar.puntillo")

DOSSIER_PUNTILLO: Final[Path] = config.PUNTILLO_DIR
DOSSIER_FACTURES: Final[Path] = DOSSIER_PUNTILLO / "Factures_et_Commandes"
DOSSIER_PEAUSSERIES: Final[Path] = DOSSIER_PUNTILLO / "Catalogue_Cuirs"
DOSSIER_CLIENTS: Final[Path] = DOSSIER_PUNTILLO / "Fiches_Clients_Bespoke"
DOSSIER_JOURNAL: Final[Path] = DOSSIER_PUNTILLO / "Journal_Atelier"

for d in (DOSSIER_PUNTILLO, DOSSIER_FACTURES, DOSSIER_PEAUSSERIES, DOSSIER_CLIENTS, DOSSIER_JOURNAL):
    d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# TRANSCRIPTION MULTIMODALE & SYNTHÈSE VOCALE TÉLÉPHONIQUE
# ---------------------------------------------------------------------------

def _transcrire_audio_bilingue(audio_bytes: bytes) -> tuple[str, str]:
    """Transcrit fidèlement l'audio OGG de Telegram et détecte la langue parlée (FR ou IT)."""
    client = config.GENAI_CLIENT
    prompt = (
        "Tu es Alba, l'assistante d'atelier de Madame Laura Puntillo (Bottière d'art sur mesure).\n"
        "Transcris ce message vocal fidèlement.\n"
        "Détecte la langue parlée ('fr' ou 'it').\n"
        "Format JSON strict : {\"texte\": \"...\", \"langue\": \"fr\" | \"it\"}"
    )

    try:
        res = client.models.generate_content(
            model=config.MODELE_TEXTE_GEMINI,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
                prompt
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
        )
        data = json.loads(res.text.strip()) if res.text else {}
        return data.get("texte", ""), data.get("langue", "fr")
    except Exception as e:
        logger.error(f"Erreur transcription bilingue Alba : {e}")
        return "", "fr"


async def _repondre_audio_bilingue(bot: Any, chat_id: int, texte: str, langue: str = "fr") -> None:
    """Génère et expédie une note vocale chaleureuse (Elsa en IT, Vivienne en FR)."""
    try:
        import edge_tts
        voice_id = "it-IT-ElsaNeural" if langue == "it" else "fr-FR-VivienneNeural"
        audio_path = config.AUDIO_DIR / f"reply_alba_{os.urandom(4).hex()}.mp3"

        # Nettoyage strict pour une diction orale parfaite (zéro markdown lu à l'oreille)
        clean_txt = re.sub(r"[*#`_\[\]>]", "", texte)[:600]
        communicate = edge_tts.Communicate(clean_txt, voice_id)
        await communicate.save(str(audio_path))

        with open(audio_path, "rb") as f:
            await bot.send_voice(chat_id=chat_id, voice=f)

        if audio_path.exists():
            audio_path.unlink()
    except Exception as e:
        logger.warning(f"Échec synthèse vocale Alba : {e}")


async def _traiter_dialogue_oral_alba(texte_instruction: str, langue: str = "fr") -> str:
    """Génère une réponse orale fluide pour Laura tout en exécutant les actions de fond."""
    from core.engine import run_agent

    # 1. Exécution opérationnelle en arrière-plan (fiches Obsidian, calculs, etc. en français)
    consigne_action = (
        f"[MISSION ATELIER LAURA PUNTILLO]\n"
        f"Message de l'artisane : {texte_instruction}\n"
        f"RÈGLE IMPÉRATIVE : Exécute les outils nécessaires (fiches clients, notes peausseries, calculs). "
        f"TOUS les fichiers dans Obsidian doivent être rédigés EN FRANÇAIS."
    )
    res_agent, _, _, _ = run_agent(consigne_action, persona="alba")

    # 2. Formulation d'une réplique téléphonique courte et vivante pour l'oreille de Laura
    client = config.GENAI_CLIENT
    prompt_telephone = (
        f"Tu es Alba, au téléphone en direct avec Laura.\n"
        f"Langue : {'Italien' if langue == 'it' else 'Français'}.\n"
        f"Voici ce que tu viens d'accomplir dans le système : '{res_agent[:400]}'\n\n"
        "RÈGLE D'OR TÉLÉPHONIQUE :\n"
        "Formule une réponse orale directe, concise, chaleureuse et naturelle (1 à 2 phrases max) "
        "comme si tu lui parlais à l'oreille dans l'atelier. AUCUN balisage markdown, aucun tiret, aucun astérisque."
    )

    try:
        res_oral = client.models.generate_content(
            model=config.MODELE_TEXTE_GEMINI,
            contents=prompt_telephone,
            config=types.GenerateContentConfig(temperature=0.3)
        )
        return res_oral.text.strip() if res_oral.text else "C'est bien noté Laura, tout est enregistré."
    except Exception:
        return "C'est bien noté Laura, je m'en occupe tout de suite."


# ---------------------------------------------------------------------------
# GESTIONNAIRES TELEGRAM DISTANTS (4G / 5G / Wi-Fi)
# ---------------------------------------------------------------------------

async def gerer_message_vocal_distant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestionnaire de conversation vocale continue à distance."""
    msg = update.message
    if not msg:
        return

    chat_id = update.effective_chat.id
    voice = msg.voice or msg.audio
    if not voice:
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")

    file = await context.bot.get_file(voice.file_id)
    audio_path = config.AUDIO_DIR / f"in_alba_{os.urandom(4).hex()}.ogg"
    await file.download_to_drive(str(audio_path))

    try:
        audio_bytes = audio_path.read_bytes()
        texte_transcrit, langue = _transcrire_audio_bilingue(audio_bytes)
    finally:
        if audio_path.exists():
            audio_path.unlink()

    if not texte_transcrit:
        await msg.reply_text("⚠️ Je n'ai pas bien entendu. Peux-tu répéter ?")
        return

    # Traitement et réponse vocale instantanée
    reponse_orale = await _traiter_dialogue_oral_alba(texte_transcrit, langue)
    
    # Envoi du message texte (pour archive) et de la note vocale (pour l'oreille)
    await msg.reply_text(reponse_orale)
    await _repondre_audio_bilingue(context.bot, chat_id, reponse_orale, langue=langue)


async def gerer_photo_peausserie_distante(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyse visuelle d'un cuir ou d'une facture envoyée en direct depuis l'iPhone."""
    msg = update.message
    if not msg or not msg.photo:
        return

    chat_id = update.effective_chat.id
    caption = msg.caption or "Analyse cette peausserie ou cette facture pour l'atelier."
    await msg.reply_text("🔍 Analyse en cours...")

    photo = msg.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_path = config.IMAGE_DIR / f"alba_visu_{os.urandom(4).hex()}.jpg"
    await file.download_to_drive(str(img_path))

    try:
        client = config.GENAI_CLIENT
        img_bytes = img_path.read_bytes()

        prompt_vision = (
            "Tu es Alba, experte bottière d'art pour Madame Laura Puntillo.\n"
            "Analyse cette image envoyée depuis l'atelier :\n"
            "1. S'il s'agit d'un CUIR / PEAUSSERIE : Analyse la matière (veau box, agneau, cordovan, cuir à semelle), le grain, la couleur, les défauts visibles et le potentiel de coupe.\n"
            "2. S'il s'agit d'une FACTURE / BON DE TANNERIE : Extrais le fournisseur (Puy, Annonay, Haas, JR...), la date, le métrage et les montants.\n"
            f"Notes de Laura : '{caption}'\n\n"
            "Rédige une fiche d'atelier claire EN FRANÇAIS."
        )

        res = client.models.generate_content(
            model=config.MODELE_TEXTE_GEMINI,
            contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"), prompt_vision],
        )
        rapport = res.text.strip() if res.text else "Analyse terminée."

        # Enregistrement dans Obsidian
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        is_facture = any(k in rapport.lower() for k in ("facture", "fournisseur", "tannerie", "montant", "ht", "ttc"))
        dossier_cible = DOSSIER_FACTURES if is_facture else DOSSIER_PEAUSSERIES
        type_fiche = "Facture_Tannerie" if is_facture else "Fiche_Peausserie"

        fichier_note = dossier_cible / f"{type_fiche}_{ts}.md"
        frontmatter = f"---\ndate: {datetime.datetime.now().isoformat()}\ntype: \"{type_fiche.lower()}\"\natelier: \"Laura Puntillo\"\nexpert: \"Alba\"\n---\n\n"
        fichier_note.write_text(frontmatter + f"# {type_fiche.replace('_', ' ')} — {ts}\n\n{rapport}", encoding="utf-8")

        try:
            from tools.second_cerveau import synchroniser_second_cerveau
            synchroniser_second_cerveau()
        except Exception:
            pass

        await msg.reply_text(f"{rapport}\n\n📂 *Fiche archivée dans Obsidian :* `[[{fichier_note.stem}]]`", parse_mode="Markdown")

    except Exception as e:
        await msg.reply_text(f"⚠️ Erreur lors de l'analyse : {e}")
    finally:
        if img_path.exists():
            img_path.unlink()


def main() -> None:
    token = config.TELEGRAM_TOKEN
    if not token:
        print("❌ TELEGRAM_TOKEN absent du fichier .env.")
        sys.exit(1)

    print("🚀 Bot Atelier Laura Puntillo & Alba connecté au Cloud Telegram 24/7.")
    print("📡 Opérationnel à distance sur 4G / 5G / Wi-Fi dans le monde entier.")

    app = Application.builder().token(token).build()

    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, gerer_message_vocal_distant))
    app.add_handler(MessageHandler(filters.PHOTO, gerer_photo_peausserie_distante))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: asyncio.create_task(u.message.reply_text("Alba connectée. Envoie une note vocale ou une photo d'atelier."))))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
