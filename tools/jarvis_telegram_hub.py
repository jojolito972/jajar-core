from __future__ import annotations

"""
tools/jarvis_telegram_hub.py — Passerelle Telegram Multimodale 24/7 avec Verrou POSIX Atomique.
Garantit l'exclusivité d'instance via fcntl et purge automatique des conflits HTTP 409.
"""

import asyncio
import datetime
import fcntl
import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from core.engine import run_agent
from core.intent_classifier import intent_classifier
from core.llm_router import router
from core.security import assainir_nom_fichier, valider_confinement_chemin
from core.tracing import AgentTrace

from telegram import Update
from telegram.error import Conflict, NetworkError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

logger: Final[logging.Logger] = logging.getLogger("jarvis.telegram")
LOCK_FILE_PATH: Final[Path] = Path("/tmp/jarvis_telegram_hub.lock")
_lock_fd: Any = None

USER_SESSIONS: Final[dict[int, dict[str, Any]]] = {}


def _acquerir_verrou_exclusif() -> None:
    """Verrou POSIX strict au niveau du noyau pour empêcher tout conflit d'instance."""
    global _lock_fd
    _lock_fd = open(LOCK_FILE_PATH, "a+")
    
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.seek(0)
        _lock_fd.truncate()
        _lock_fd.write(f"{os.getpid()}\n")
        _lock_fd.flush()
    except BlockingIOError:
        # Une autre instance tourne : lecture de son PID et neutralisation forcée
        _lock_fd.seek(0)
        old_pid_str = _lock_fd.read().strip()
        if old_pid_str and old_pid_str.isdigit():
            old_pid = int(old_pid_str)
            try:
                os.kill(old_pid, 9)
                # [OPTIMISÉ MACHINE DE GUERRE] time.sleep -> asyncio.sleep recommandé
# time.sleep(1.0)
            except ProcessLookupError:
                pass
        
        # Ré-acquisition du verrou
        try:
            fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_fd.seek(0)
            _lock_fd.truncate()
            _lock_fd.write(f"{os.getpid()}\n")
            _lock_fd.flush()
        except Exception as e:
            print(f"❌ Impossible d'acquérir le verrou exclusif : {e}")
            sys.exit(1)


def _verifier_dns_telegram(hote: str = "api.telegram.org", port: int = 443, tentatives: int = 5) -> bool:
    for _ in range(tentatives):
        try:
            socket.getaddrinfo(hote, port)
            return True
        except Exception:
            # [OPTIMISÉ MACHINE DE GUERRE] time.sleep -> asyncio.sleep recommandé
# time.sleep(1.0)
    return False


def _get_session(chat_id: int) -> dict[str, Any]:
    if chat_id not in USER_SESSIONS:
        USER_SESSIONS[chat_id] = {
            "persona": "jarvis",
            "vocal": True,
            "mode_telephone": False,
            "mode_discussion": False,
        }
    return USER_SESSIONS[chat_id]


def _est_autorise(user_id: int) -> bool:
    if config.TELEGRAM_ALLOWED_USER_IDS:
        return user_id in config.TELEGRAM_ALLOWED_USER_IDS
    if config.TELEGRAM_CHAT_ID:
        return str(user_id) == str(config.TELEGRAM_CHAT_ID)
    return False


async def _verifier_auth(update: Update) -> bool:
    user = update.effective_user
    if not user or not _est_autorise(user.id):
        if update.message:
            await update.message.reply_text("⛔ Accès refusé : Instance sécurisée JAJAR.")
        config.audit_logger.warning(f"Accès non autorisé : ID={user.id if user else 'Inconnu'}")
        return False
    return True


def _extraire_texte_propre(reponse_brute: Any) -> str:
    if isinstance(reponse_brute, tuple):
        t = str(reponse_brute[0]).strip()
    else:
        t = str(reponse_brute).strip()

    if t.startswith("{") and ("\"answer\"" in t or "\"thinking\"" in t):
        try:
            data = json.loads(t, strict=False)
            if isinstance(data, dict):
                return str(data.get("answer") or data.get("thinking") or t)
        except Exception:
            pass

    return t


def _transcrire_audio_robuste(audio_bytes: bytes) -> tuple[str, str]:
    from google.genai import types

    client = config.GENAI_CLIENT
    model_name = getattr(config, "MODELE_TEXTE_GEMINI", "gemini-3.6-flash")

    prompt = (
        "Transcris ce message vocal fidèlement.\n"
        "Détecte la langue principale ('fr' ou 'it').\n"
        "Format JSON strict : {\"texte\": \"...\", \"langue\": \"fr\" | \"it\"}"
    )

    try:
        res = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
                prompt
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
        )
        if res.text and res.text.strip():
            data = json.loads(res.text.strip(), strict=False)
            return data.get("texte", ""), data.get("langue", "fr")
    except Exception as e:
        logger.warning(f"Échec transcription Gemini : {e}")

    return "", "fr"


async def _envoyer_vocal_reponse(bot: Any, chat_id: int, texte: str, persona: str = "jarvis", langue: str = "fr") -> None:
    try:
        import edge_tts
        if persona == "alba" and langue == "it":
            voice_id = "it-IT-ElsaNeural"
        elif persona == "alba":
            voice_id = "fr-FR-VivienneNeural"
        elif persona in ("tesla", "franklin"):
            voice_id = "fr-FR-HenriNeural"
        else:
            voice_id = "fr-FR-VivienneNeural"

        audio_path = config.AUDIO_DIR / f"reply_{os.urandom(4).hex()}.mp3"
        texte_audio = re.sub(r"[*#`_\[\]>]", "", texte)[:500]
        communicate = edge_tts.Communicate(texte_audio, voice_id)
        await communicate.save(str(audio_path))

        with open(audio_path, "rb") as f:
            await bot.send_voice(chat_id=chat_id, voice=f)
        if audio_path.exists():
            audio_path.unlink()
    except Exception as e:
        logger.warning(f"Échec TTS Telegram : {e}")


async def _detecter_et_envoyer_fichiers_generes(bot: Any, chat_id: int, reponse_texte: str) -> None:
    for img_str in re.findall(r"([/\w\.-]+\.(?:png|jpg|jpeg|webp))", reponse_texte):
        p = Path(img_str).expanduser()
        if not p.is_absolute():
            p = config.IMAGE_DIR / p.name
        if p.exists() and p.is_file():
            try:
                with open(p, "rb") as photo_file:
                    await bot.send_photo(chat_id=chat_id, photo=photo_file, caption=f"🎨 Image : {p.name}")
            except Exception as e:
                logger.warning(f"Erreur photo Telegram : {e}")

    for doc_str in re.findall(r"([/\w\.-]+\.(?:pdf|zip|tar\.gz|sh|py|docx|txt|json|md))", reponse_texte):
        p = Path(doc_str).expanduser()
        if not p.is_absolute():
            p = config.DEPOT_DIR / p.name
        if p.exists() and p.is_file() and p.stat().st_size > 0:
            try:
                with open(p, "rb") as doc_file:
                    await bot.send_document(chat_id=chat_id, document=doc_file, caption=f"📄 Document : {p.name}")
            except Exception as e:
                logger.warning(f"Erreur document Telegram : {e}")


# ---------------------------------------------------------------------------
# COMMANDES UTILISATEUR
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return
    session = _get_session(update.effective_chat.id)
    expert = config.PERSONAS.get(session["persona"], config.PERSONAS["jarvis"])
    texte = (
        f"🤖 **Studio JAJAR v2 — Passerelle Mobile**\n\n"
        f"Connecté en direct sur ton Mac (`/Users/denmac`).\n\n"
        f"• **Agent Actif :** `{expert['nom']}` ({expert['role']})\n"
        f"• **Mode Vocal :** `{'Activé' if session['vocal'] else 'Désactivé'}`\n\n"
        f"**Commandes :**\n"
        f"• `/perso` : Mode Discussion Rapide & Scribe Mémoriel (<0.4s)\n"
        f"• `/pro` : Mode Studio Pro (Action & Outils)\n"
        f"• `/capture` : Capture d'écran du Mac en direct\n"
        f"• `/brief` : Briefing complet du jour\n"
        f"• `/agent <nom>` : Changer d'agent (jarvis, alba, tesla, ray, cleo...)\n"
        f"• `/vocal on|off` : Activer/Désactiver les réponses vocales\n"
        f"• `/etat` : Statut du système"
    )
    await update.message.reply_text(texte, parse_mode="Markdown")


async def cmd_perso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return
    session = _get_session(update.effective_chat.id)
    session["mode_discussion"] = True
    expert = config.PERSONAS.get(session["persona"], config.PERSONAS["jarvis"])
    await update.message.reply_text(
        f"💬 **Mode Discussion Perso Activé avec {expert['nom']} !**\n"
        f"Réponses instantanées (<0.4s). Zéro outil, pensées archivées automatiquement.",
        parse_mode="Markdown"
    )


async def cmd_pro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return
    session = _get_session(update.effective_chat.id)
    session["mode_discussion"] = False
    expert = config.PERSONAS.get(session["persona"], config.PERSONAS["jarvis"])
    await update.message.reply_text(
        f"⚡ **Mode Studio Pro Activé avec {expert['nom']} !**\n"
        f"Accès direct aux 49 outils, au bus multi-agents et à macOS.",
        parse_mode="Markdown"
    )


async def cmd_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return
    chat_id = update.effective_chat.id
    msg_wait = await update.message.reply_text("📸 Capture d'écran du Mac en cours...")

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    img_path = config.IMAGE_DIR / f"capture_{ts}.jpg"

    def _capturer() -> bool:
        res = subprocess.run(["screencapture", "-x", "-t", "jpg", str(img_path)], capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and img_path.exists() and img_path.stat().st_size > 0:
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "75", "-Z", "1280", str(img_path)], capture_output=True, timeout=4)
            return True
        return False

    succes = await asyncio.to_thread(_capturer)
    if not succes:
        await msg_wait.edit_text("⚠️ Échec capture d'écran (vérifie les permissions macOS).")
        return

    try:
        with open(img_path, "rb") as f:
            await context.bot.send_photo(chat_id=chat_id, photo=f, caption=f"🖥️ Mac ({datetime.datetime.now().strftime('%H:%M:%S')})")
        await msg_wait.delete()
    except Exception as e:
        await msg_wait.edit_text(f"Erreur envoi capture : {e}")


async def cmd_brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return
    await update.message.reply_text("⏳ Synthèse de ton briefing en cours...")
    res_raw = await asyncio.to_thread(run_agent, "Fais un briefing complet des priorités du jour (emails 2026, rappels, projets).", persona="alfred")
    await update.message.reply_text(_extraire_texte_propre(res_raw))


async def cmd_agent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return
    session = _get_session(update.effective_chat.id)
    if not context.args:
        liste = ", ".join(f"`{k}`" for k in config.PERSONAS.keys())
        await update.message.reply_text(f"Agents disponibles : {liste}\nUsage : `/agent alba`", parse_mode="Markdown")
        return

    nouv = context.args[0].lower().strip()
    if nouv in config.PERSONAS:
        session["persona"] = nouv
        expert = config.PERSONAS[nouv]
        await update.message.reply_text(f"➔ **Agent connecté :** `{expert['nom']}` ({expert['role']})", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"Agent inconnu `{nouv}`. Disponibles : {', '.join(config.PERSONAS.keys())}", parse_mode="Markdown")


async def cmd_vocal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return
    session = _get_session(update.effective_chat.id)
    if context.args and context.args[0].lower() in ("on", "1", "oui"):
        session["vocal"] = True
        await update.message.reply_text("🎙️ **Mode vocal activé.**", parse_mode="Markdown")
    elif context.args and context.args[0].lower() in ("off", "0", "non"):
        session["vocal"] = False
        session["mode_telephone"] = False
        await update.message.reply_text("💬 **Mode vocal désactivé (Réponses texte).**", parse_mode="Markdown")
    else:
        etat = "Activé" if session["vocal"] else "Désactivé"
        await update.message.reply_text(f"Mode vocal actuel : `{etat}`. (Usage : `/vocal on` ou `/vocal off`)", parse_mode="Markdown")


async def cmd_etat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return
    now = datetime.datetime.now().strftime("%H:%M:%S")
    session = _get_session(update.effective_chat.id)
    mode_actuel = "PERSO (Discussion)" if session.get("mode_discussion") else "PRO (Opérationnel)"
    await update.message.reply_text(
        f"🟢 **Système JAJAR connecté et opérationnel sur ton Mac** ({now}).\n"
        f"• Agent actif : `{session['persona'].upper()}`\n"
        f"• Mode courant : `{mode_actuel}`\n"
        f"• Mode vocal : `{'Activé' if session['vocal'] else 'Désactivé'}`",
        parse_mode="Markdown"
    )


# ---------------------------------------------------------------------------
# GESTIONNAIRES MULTIMÉDIA
# ---------------------------------------------------------------------------

async def gerer_message_texte(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return

    msg = update.message
    chat_id = update.effective_chat.id
    user_text = msg.text.strip() if msg.text else ""
    if not user_text:
        return

    session = _get_session(chat_id)
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    if session.get("mode_discussion"):
        mode_op = "discussion"
    else:
        intention = intent_classifier.classifier_texte(user_text)
        mode_op = "discussion" if intention == "perso" else "auto"

    tracer = AgentTrace(session["persona"])
    res_brut = await asyncio.to_thread(
        run_agent,
        task=user_text,
        persona=session["persona"],
        mode_operationnel=mode_op,
        tracer=tracer,
    )
    reponse = _extraire_texte_propre(res_brut)

    if len(reponse) > 4000:
        for chunk in [reponse[i:i + 4000] for i in range(0, len(reponse), 4000)]:
            await msg.reply_text(chunk)
    else:
        try:
            await msg.reply_text(reponse, parse_mode="Markdown")
        except Exception:
            await msg.reply_text(reponse)

    await _detecter_et_envoyer_fichiers_generes(context.bot, chat_id, reponse)

    demande_vocale = any(k in user_text.lower() for k in ("vocal", "en audio", "voix", "dis-le moi", "parle-moi"))
    if session["vocal"] or demande_vocale or session["mode_telephone"]:
        await _envoyer_vocal_reponse(context.bot, chat_id, reponse, persona=session["persona"])


async def gerer_message_vocal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return

    msg = update.message
    chat_id = update.effective_chat.id
    session = _get_session(chat_id)

    voice = msg.voice or msg.audio
    if not voice:
        return

    await msg.reply_text("🎧 Écoute et analyse de ton message vocal...")
    await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")

    file = await context.bot.get_file(voice.file_id)
    audio_path = config.AUDIO_DIR / f"incoming_{os.urandom(4).hex()}.ogg"
    await file.download_to_drive(str(audio_path))

    try:
        audio_bytes = audio_path.read_bytes()
        texte_transcrit, langue = _transcrire_audio_robuste(audio_bytes)
    except Exception as e:
        await msg.reply_text(f"⚠️ Erreur lors du décodage audio : {e}")
        return
    finally:
        if audio_path.exists():
            try:
                audio_path.unlink()
            except Exception:
                pass

    if not texte_transcrit:
        await msg.reply_text("⚠️ Je n'ai pas pu décoder l'audio. Peux-tu répéter ?")
        return

    flag = "🇮🇹" if langue == "it" else "🇫🇷"
    await msg.reply_text(f"{flag} **Compris :** « {texte_transcrit} »", parse_mode="Markdown")

    if session.get("mode_discussion"):
        mode_op = "discussion"
    else:
        intention = intent_classifier.classifier_audio_et_texte(texte_transcrit, langue=langue)
        mode_op = "discussion" if intention == "perso" else "auto"

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    res_brut = await asyncio.to_thread(run_agent, task=texte_transcrit, persona=session["persona"], mode_operationnel=mode_op)
    reponse = _extraire_texte_propre(res_brut)

    try:
        await msg.reply_text(reponse, parse_mode="Markdown")
    except Exception:
        await msg.reply_text(reponse)

    await _detecter_et_envoyer_fichiers_generes(context.bot, chat_id, reponse)
    await _envoyer_vocal_reponse(context.bot, chat_id, reponse, persona=session["persona"], langue=langue)


async def gerer_photo_recue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return

    msg = update.message
    if not msg.photo:
        return

    caption = msg.caption or "Analyse cette photo et décris ce qu'elle contient ou ce qu'il faut faire."
    await msg.reply_text("👁️ Analyse de la photo avec Gemini Vision...")

    photo = msg.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_path = config.IMAGE_DIR / f"recu_{os.urandom(4).hex()}.jpg"
    await file.download_to_drive(str(img_path))

    try:
        from google.genai import types
        client = config.GENAI_CLIENT
        img_bytes = img_path.read_bytes()

        session = _get_session(update.effective_chat.id)
        prompt_systeme = (
            f"Tu es {session['persona'].upper()} pour {config.UTILISATEUR}.\n"
            f"Analyse l'image transmise depuis son iPhone.\n"
            f"Demande : {caption}"
        )

        res = client.models.generate_content(
            model=config.MODELE_TEXTE_GEMINI,
            contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"), prompt_systeme],
        )
        reponse = res.text.strip() if res.text else "Image analysée."
        await msg.reply_text(reponse)
    except Exception as e:
        await msg.reply_text(f"⚠️ Erreur vision : {e}")
    finally:
        if img_path.exists():
            try:
                img_path.unlink()
            except Exception:
                pass


async def gerer_document_recu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _verifier_auth(update) or not update.message:
        return

    msg = update.message
    doc = msg.document
    if not doc or not doc.file_name:
        return

    nom_propre = assainir_nom_fichier(doc.file_name)
    dest_path = config.DEPOT_DIR / nom_propre

    try:
        valider_confinement_chemin(dest_path, config.DEPOT_DIR)
    except Exception as e:
        await msg.reply_text(f"⛔ Fichier refusé par la politique de sécurité : {e}")
        return

    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(str(dest_path))

    await msg.reply_text(f"📥 **Fichier déposé :** `{nom_propre}`", parse_mode="Markdown")
    prompt = f"Le document '{nom_propre}' a été déposé dans {dest_path}. Fais-en l'analyse ou exécute l'action requise."
    reponse, _, _, _ = await asyncio.to_thread(run_agent, task=prompt, persona="indiana")
    await msg.reply_text(reponse)


# ---------------------------------------------------------------------------
# POINT D'ENTRÉE PRINCIPAL
# ---------------------------------------------------------------------------

def main() -> None:
    if not config.TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN absent du fichier .env.")
        sys.exit(1)

    # 1. Acquisition du verrou exclusif matériel POSIX
    _acquerir_verrou_exclusif()

    # 2. Vérification DNS
    print("⏳ Vérification de la liaison DNS vers api.telegram.org...")
    if not _verifier_dns_telegram():
        subprocess.run(["dscacheutil", "-flushcache"], capture_output=True)

    request_client = HTTPXRequest(
        connection_pool_size=10,
        connect_timeout=20.0,
        read_timeout=35.0,
        write_timeout=35.0,
        pool_timeout=15.0,
    )

    print("🚀 Hub Telegram JAJAR 24/7 Multimodal démarré (Verrou Exclusif Actif).")
    
    app = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .request(request_client)
        .get_updates_request(request_client)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("brief", cmd_brief))
    app.add_handler(CommandHandler("perso", cmd_perso))
    app.add_handler(CommandHandler("chat", cmd_perso))
    app.add_handler(CommandHandler("pro", cmd_pro))
    app.add_handler(CommandHandler("capture", cmd_capture))
    app.add_handler(CommandHandler("agent", cmd_agent))
    app.add_handler(CommandHandler("vocal", cmd_vocal))
    app.add_handler(CommandHandler("etat", cmd_etat))

    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, gerer_message_vocal))
    app.add_handler(MessageHandler(filters.PHOTO, gerer_photo_recue))
    app.add_handler(MessageHandler(filters.Document.ALL, gerer_document_recu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gerer_message_texte))

    try:
        app.run_polling(
            drop_pending_updates=True,
            bootstrap_retries=5,
            timeout=30,
        )
    except Conflict:
        print("⚠️ Conflit d'instance détecté sur les serveurs Telegram. Redémarrage propre...")
    except Exception as e:
        logger.error(f"Arrêt Hub Telegram : {e}")


if __name__ == "__main__":
    main()
