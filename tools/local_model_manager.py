from __future__ import annotations

"""
tools/local_model_manager.py — Gestionnaire de cycle de vie dynamique de llama-server.
Contexte étendu à 8192 tokens avec quantification KV-Cache Q8_0 pour Apple Silicon Metal.
"""

import atexit
import datetime
import logging
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Final, Optional

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from config import SecurityTier
from core.tools_registry import outil

logger: Final[logging.Logger] = logging.getLogger("jajar.model_manager")
MODELES_DIR: Final[Path] = Path("/Users/denmac/Assistant_IA/modeles")
LOG_LLAMA_FILE: Final[Path] = config.LOG_DIR / "llama_server.log"


def _trouver_fichier_gemma() -> Path:
    if not MODELES_DIR.exists():
        MODELES_DIR.mkdir(parents=True, exist_ok=True)
    exact = MODELES_DIR / "gemma-4-12b-it-UD-Q4_K_XL.gguf"
    if exact.exists() and exact.stat().st_size > 0:
        return exact
    candidats = list(MODELES_DIR.glob("*gemma*.gguf")) + list(MODELES_DIR.glob("*.gguf"))
    if candidats:
        candidats.sort(key=lambda x: x.stat().st_size, reverse=True)
        return candidats[0]
    return exact


def lire_derniers_logs_llama(lignes: int = 15) -> str:
    """Lit les dernières lignes du log de llama-server en cas de crash."""
    if not LOG_LLAMA_FILE.exists():
        return "(Aucun log disponible)"
    try:
        toutes = LOG_LLAMA_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(toutes[-lignes:])
    except Exception:
        return "(Impossible de lire les logs)"


class DynamicLlamaServerManager:
    def __init__(self, idle_timeout_sec: int = 600) -> None:
        self.idle_timeout_sec: int = idle_timeout_sec
        self.process: subprocess.Popen | None = None
        self.active_model_path: Path | None = None
        self.last_activity_ts: float = 0.0
        self._lock: Final[threading.RLock] = threading.RLock()
        self._watchdog_thread: threading.Thread | None = None
        self._arreter_watchdog_event: Final[threading.Event] = threading.Event()
        atexit.register(self.arreter_serveur)

    def _trouver_binaire_server(self) -> str:
        candidats = [
            shutil.which("llama-server"),
            "/opt/homebrew/bin/llama-server",
            "/usr/local/bin/llama-server",
            str(BASE_DIR / "llama-server"),
            str(Path.home() / "Assistant_IA" / "jarvis" / "llama-server"),
        ]
        for c in candidats:
            if c:
                p = Path(str(c))
                if p.is_file() and os.access(str(p), os.X_OK):
                    return str(p)
        return "llama-server"

    def est_en_ecoute(self) -> bool:
        try:
            req = urllib.request.Request("http://127.0.0.1:8080/health", method="GET")
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                return resp.status == 200
        except Exception:
            return False

    def arreter_serveur(self) -> str:
        with self._lock:
            self._arreter_watchdog_event.set()
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=1)
                except Exception as e:
                    logger.warning(f"Erreur arrêt serveur : {e}")
                finally:
                    self.process = None

            subprocess.run(["pkill", "-9", "-f", "llama-server"], capture_output=True)
            self.active_model_path = None
            return "🧹 Serveur local arrêté. 100% de la VRAM libérée."

    def _demarrer_watchdog_si_besoin(self) -> None:
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return
        self._arreter_watchdog_event.clear()

        def _watchdog_loop() -> None:
            while not self._arreter_watchdog_event.is_set():
                if self._arreter_watchdog_event.wait(timeout=5.0):
                    break
                with self._lock:
                    if self.process and self.last_activity_ts > 0:
                        inactivite = time.time() - self.last_activity_ts
                        if inactivite >= self.idle_timeout_sec:
                            logger.info(f"Inactivité de {self.idle_timeout_sec}s atteinte. Libération VRAM...")
                            self.arreter_serveur()
                            break

        self._watchdog_thread = threading.Thread(target=_watchdog_loop, daemon=True, name="llama_watchdog")
        self._watchdog_thread.start()

    def _demarrer_instance(self, model_file: Path) -> tuple[bool, str]:
        self.arreter_serveur()
        bin_server = self._trouver_binaire_server()

        if not model_file.exists():
            return False, f"Fichier modèle introuvable : {model_file}"

        try:
            res_cores = subprocess.run(["sysctl", "-n", "hw.perflevel0.physicalcpu"], capture_output=True, text=True)
            threads = res_cores.stdout.strip() or "4"
        except Exception:
            threads = "4"

        # Contexte 8192 tokens + KV-Cache Q8_0 pour optimiser la VRAM sur 16 Go
        cmd: list[str] = [
            bin_server,
            "--host", "127.0.0.1",
            "--port", "8080",
            "--model", str(model_file),
            "--n-gpu-layers", "99",
            "--threads", str(threads),
            "--parallel", "1",
            "--batch-size", "512",
            "--ubatch-size", "128",
            "-c", "8192",
            "--cache-type-k", "q8_0",
            "--cache-type-v", "q8_0",
        ]

        LOG_LLAMA_FILE.parent.mkdir(parents=True, exist_ok=True)
        log_out = open(LOG_LLAMA_FILE, "a", encoding="utf-8")
        log_out.write(f"\n\n=== DÉMARRAGE LLAMA-SERVER (-c 8192 / KV Q8_0) : {datetime.datetime.now()} ===\n")
        log_out.flush()

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=log_out,
                stderr=log_out,
                start_new_session=True,
            )
            self.active_model_path = model_file
            self.last_activity_ts = time.time()

            # Attente active jusqu'à 60s
            for _ in range(60):
                if self.process.poll() is not None:
                    logs = lire_derniers_logs_llama(8)
                    self.arreter_serveur()
                    return False, f"Crash de llama-server (Code {self.process.returncode}) :\n{logs}"

                if self.est_en_ecoute():
                    self._demarrer_watchdog_si_besoin()
                    return True, "Serveur prêt et opérationnel avec 8192 tokens de contexte."
                # [OPTIMISÉ MACHINE DE GUERRE] time.sleep -> asyncio.sleep recommandé
# time.sleep(0.5)

            logs = lire_derniers_logs_llama(8)
            self.arreter_serveur()
            return False, f"Délai d'attente dépassé :\n{logs}"

        except Exception as e:
            self.arreter_serveur()
            return False, f"Échec d'exécution du binaire : {e}"

    def garantir_modele_charge(self) -> tuple[bool, str]:
        with self._lock:
            self.last_activity_ts = time.time()
            model_file = _trouver_fichier_gemma()

            if not model_file.exists():
                return False, f"⚠️ Modèle GGUF introuvable dans {MODELES_DIR}."

            if self.est_en_ecoute():
                self.active_model_path = model_file
                self._demarrer_watchdog_si_besoin()
                return True, f"Modèle `{model_file.name}` actif en VRAM sur GPU Metal (8192 tokens, port 8080)."

            succes, msg = self._demarrer_instance(model_file)
            if succes:
                return True, f"Modèle `{model_file.name}` chargé avec succès sur GPU Metal (8192 tokens)."
            return False, f"⚠️ Impossible de démarrer llama-server :\n{msg}"


server_manager: Final[DynamicLlamaServerManager] = DynamicLlamaServerManager(idle_timeout_sec=600)


@outil(tier=SecurityTier.AUTO)
def liberer_memoire_modeles_locaux() -> str:
    return server_manager.arreter_serveur()


@outil(tier=SecurityTier.AUTO)
def obtenir_statut_memoire_locale() -> str:
    actif = server_manager.est_en_ecoute()
    path_m = server_manager.active_model_path
    if not actif or not path_m:
        return "🟢 **Mémoire Locale Vierge :** Aucun modèle chargé en RAM/VRAM."
    return f"🟡 **Modèle Résident en VRAM :** `{path_m.name}` sur Metal GPU (8192 tokens, port 8080)."
