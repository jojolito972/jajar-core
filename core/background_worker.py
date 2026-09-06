"""
core/background_worker.py — Worker asynchrone thread-safe avec notifications Telegram
et persistance atomique des tâches.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Final

import config

logger: Final[logging.Logger] = logging.getLogger("jarvis.worker")
QUEUE_DIR: Final[Path] = config.BASE_DIR / "tasks_queue"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TacheAsync:
    id: str
    nom: str
    statut: str  # "en_cours", "termine", "erreur"
    date_creation: str
    date_fin: str = ""
    resultat: str = ""
    erreur: str = ""
    notifier_telegram: bool = True
    chat_id: str = ""


class BackgroundWorkerManager:
    def __init__(self, max_workers: int = 4) -> None:
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="jajar_worker")
        self.taches: dict[str, TacheAsync] = {}
        self._lock: threading.RLock = threading.RLock()
        self._charger_taches_existantes()

    def _charger_taches_existantes(self) -> None:
        with self._lock:
            for f in QUEUE_DIR.glob("task_*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    self.taches[data["id"]] = TacheAsync(**data)
                except Exception as e:
                    logger.warning(f"Tâche corrompue ignorée '{f.name}': {e}")

    def _sauvegarder_tache(self, t: TacheAsync) -> None:
        with self._lock:
            p = QUEUE_DIR / f"task_{t.id}.json"
            tmp = QUEUE_DIR / f"task_{t.id}.json.tmp_{os.urandom(4).hex()}"
            try:
                tmp.write_text(json.dumps(asdict(t), ensure_ascii=False, indent=2), encoding="utf-8")
                tmp.replace(p)
            except Exception as e:
                logger.error(f"Erreur d'écriture tâche {t.id}: {e}")
                if tmp.exists():
                    tmp.unlink()

    def _notifier_telegram_synchrone(self, chat_id: str, message: str, chemin_fichier: str = "") -> None:
        token = config.TELEGRAM_TOKEN
        target_chat = chat_id or config.TELEGRAM_CHAT_ID
        if not token or not target_chat:
            return

        import requests

        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": target_chat, "text": message, "parse_mode": "Markdown"},
                timeout=15,
            )
        except Exception as e:
            logger.warning(f"Échec notification texte Telegram : {e}")

        if chemin_fichier:
            p = Path(chemin_fichier).expanduser().resolve()
            if p.exists() and p.is_file():
                ext = p.suffix.lower()
                is_audio = ext in (".mp3", ".ogg", ".wav", ".m4a")
                endpoint = "sendVoice" if is_audio else "sendDocument"
                field_name = "voice" if is_audio else "document"
                try:
                    with open(p, "rb") as f_obj:
                        requests.post(
                            f"https://api.telegram.org/bot{token}/{endpoint}",
                            data={"chat_id": target_chat, "caption": f"📦 Fichier généré : {p.name}"},
                            files={field_name: f_obj},
                            timeout=120,
                        )
                except Exception as e:
                    logger.warning(f"Échec envoi artefact : {e}")

    def lancer_en_arriere_plan(
        self,
        nom_tache: str,
        fonction_cible: Callable[..., Any],
        args: tuple = (),
        kwargs: dict | None = None,
        notifier_telegram: bool = True,
        chat_id: str = "",
    ) -> str:
        kwargs = kwargs or {}
        task_id = uuid.uuid4().hex[:8]
        ts_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        tache = TacheAsync(
            id=task_id,
            nom=nom_tache,
            statut="en_cours",
            date_creation=ts_now,
            notifier_telegram=notifier_telegram,
            chat_id=chat_id,
        )

        with self._lock:
            self.taches[task_id] = tache
            self._sauvegarder_tache(tache)

        def _runner() -> None:
            try:
                res = fonction_cible(*args, **kwargs)
                with self._lock:
                    tache.statut = "termine"
                    tache.resultat = str(res)
                    tache.date_fin = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self._sauvegarder_tache(tache)

                match_fichier = re.search(r"([/\w\.-]+\.(?:mp3|pdf|md|zip|png|jpg|json|txt))", tache.resultat)
                chemin_fic = match_fichier.group(1) if match_fichier else ""

                if tache.notifier_telegram:
                    msg = (
                        f"🚀 **Tâche d'Arrière-Plan Achevée !**\n\n"
                        f"• **Mission :** `{tache.nom}` (ID: `{tache.id}`)\n"
                        f"• **Fin :** {tache.date_fin}\n\n"
                        f"**Bilan :**\n{tache.resultat[:1200]}"
                    )
                    self._notifier_telegram_synchrone(tache.chat_id, msg, chemin_fic)

            except Exception as err:
                with self._lock:
                    tache.statut = "erreur"
                    tache.erreur = str(err)
                    tache.date_fin = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self._sauvegarder_tache(tache)

                if tache.notifier_telegram:
                    msg_err = (
                        f"⚠️ **Échec de la Tâche d'Arrière-Plan**\n\n"
                        f"• **Mission :** `{tache.nom}` (ID: `{tache.id}`)\n"
                        f"• **Erreur :** `{tache.erreur}`"
                    )
                    self._notifier_telegram_synchrone(tache.chat_id, msg_err)

        self.executor.submit(_runner)
        return f"🚀 Tâche « **{nom_tache}** » lancée en arrière-plan (ID: `{task_id}`)."

    def lister_statut_taches(self) -> str:
        with self._lock:
            if not self.taches:
                return "Aucune tâche enregistrée dans la file d'arrière-plan."

            lignes = ["📋 **État des Tâches d'Arrière-Plan :**"]
            for t in sorted(self.taches.values(), key=lambda x: x.date_creation, reverse=True)[:10]:
                icone = "🟢" if t.statut == "termine" else ("🟡" if t.statut == "en_cours" else "🔴")
                duree = f" (Fin: {t.date_fin})" if t.date_fin else " (En cours...)"
                lignes.append(f"• {icone} `[{t.id}]` **{t.nom}** — *{t.statut.upper()}*{duree}")

            return "\n".join(lignes)


worker_manager: Final[BackgroundWorkerManager] = BackgroundWorkerManager()
