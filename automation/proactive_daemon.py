from __future__ import annotations

"""
automation/proactive_daemon.py — Démon Cognitif Proactif 24/7 pour macOS.
Surveille en tâche de fond les emails urgents, l'espace disque et pousse des alertes Telegram.
"""

import asyncio
import datetime
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Final

import config

logger: Final[logging.Logger] = logging.getLogger("jajar.daemon")


class ProactiveCognitiveDaemon:
    """Sentinelle d'arrière-plan autonome pour le Mac de Denis."""

    def __init__(self, intervalle_sec: int = 1800) -> None:
        self.intervalle_sec: int = intervalle_sec
        self._is_running: bool = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        self._task = asyncio.create_task(self._daemon_loop())
        logger.info(f"👁️ Démon Cognitif Proactif actif (Cadence: {self.intervalle_sec}s).")

    async def stop(self) -> None:
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Démon Cognitif arrêté.")

    async def _notifier_telegram_urgent(self, message: str) -> None:
        if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
            return
        import urllib.parse
        import urllib.request

        url = (
            f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage?"
            f"chat_id={config.TELEGRAM_CHAT_ID}&text={urllib.parse.quote(message)}&parse_mode=Markdown"
        )
        try:
            req = urllib.request.Request(url, method="GET")
            await asyncio.to_thread(urllib.request.urlopen, req, timeout=10)
        except Exception as e:
            logger.warning(f"Échec push proactif Telegram : {e}")

    async def _auditer_disque_proactif(self) -> None:
        try:
            total, used, free = shutil.disk_usage("/System/Volumes/Data")
            pct_used = (used / total) * 100
            if pct_used > 88.0:
                free_go = round(free / (1024**3), 1)
                msg = f"🚨 **Alerte Disque Mac ({config.UTILISATEUR})**\nLe disque est saturé à `{pct_used:.1f}%` (Seulement `{free_go} Go` libres).\nDis-moi `/pro` pour lancer un nettoyage des caches Xcode et Simulateurs."
                await self._notifier_telegram_urgent(msg)
        except Exception:
            pass

    async def _verifier_mails_recents_critiques(self) -> None:
        mail_dir = Path.home() / "Library/Mail"
        if not mail_dir.exists():
            return
        now_ts = time.time()
        # Scan des .emlx créés dans la dernière heure
        recents = [
            p for p in mail_dir.rglob("*.emlx")
            if p.is_file() and (now_ts - p.stat().st_mtime) < self.intervalle_sec
        ]
        if len(recents) >= 5:
            msg = f"📬 **Activité Mail Détectée :** `{len(recents)}` nouveaux emails reçus dans la dernière demi-heure. Prêt pour un tri automatique via Alfred."
            await self._notifier_telegram_urgent(msg)

    async def _daemon_loop(self) -> None:
        # Pause initiale au démarrage
        await asyncio.sleep(60)

        while self._is_running:
            try:
                logger.info("💓 Exécution du cycle Heartbeat Cognitif...")
                await self._auditer_disque_proactif()
                await self._verifier_mails_recents_critiques()
                await asyncio.sleep(self.intervalle_sec)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur Heartbeat Daemon : {e}")
                await asyncio.sleep(60)


proactive_daemon: Final[ProactiveCognitiveDaemon] = ProactiveCognitiveDaemon(intervalle_sec=1800)
