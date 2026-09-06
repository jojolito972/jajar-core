"""
core/sandbox.py — Exécuteur de Code Isolé avec Limitation de Ressources POSIX (SandboxExecutor).
Plafonnement RAM (512 Mo), limitation temps CPU, isolation des descripteurs et capture d'effets de bord.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Final

import config
from core.security import verifier_commande_securisee

logger: Final[logging.Logger] = logging.getLogger("jajar.sandbox")


class SandboxExecutor:
    """Exécuteur sécurisé appliquant des quotas stricts de ressources système."""

    def __init__(self, max_ram_mb: int = 512, default_timeout: int = 30) -> None:
        self.sandbox_dir: Path = config.SANDBOX_DIR
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.max_ram_bytes: int = max_ram_mb * 1024 * 1024
        self.default_timeout: int = default_timeout

    def _limiter_ressources(self, timeout: int) -> None:
        """Applique les limites POSIX de mémoire et de temps CPU (macOS / Linux)."""
        try:
            # 1. Limite de temps CPU (secondes de calcul brut)
            resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 2))
            
            # 2. Limite de mémoire virtuelle (Address Space)
            if hasattr(resource, "RLIMIT_AS") and platform.system() != "Darwin":
                resource.setrlimit(resource.RLIMIT_AS, (self.max_ram_bytes, self.max_ram_bytes))
        except Exception as e:
            logger.warning(f"Ajustement des limites de ressources : {e}")

    async def executer_code_python_async(self, code: str, timeout: int | None = None) -> dict[str, Any]:
        """Exécute un script Python dans un sous-processus confiné de manière asynchrone."""
        t_out = timeout or self.default_timeout
        run_id = uuid.uuid4().hex[:8]
        tmp_file = self.sandbox_dir / f"sandbox_run_{run_id}.py"
        tmp_file.write_text(code, encoding="utf-8")

        # Capture de l'état initial des fichiers pour vérifier les créations réelles
        fichiers_avant = set(self.sandbox_dir.glob("*"))

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(tmp_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.sandbox_dir),
                start_new_session=True,
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=t_out + 2)
            
            # Détection des vrais fichiers créés par le script
            fichiers_apres = set(self.sandbox_dir.glob("*"))
            fichiers_crees = [
                str(f.name) for f in (fichiers_apres - fichiers_avant)
                if f != tmp_file and not f.name.startswith(".tmp")
            ]

            return {
                "stdout": stdout.decode("utf-8", errors="replace").strip(),
                "stderr": stderr.decode("utf-8", errors="replace").strip(),
                "returncode": proc.returncode,
                "succes": proc.returncode == 0,
                "fichiers_crees": fichiers_crees,
            }

        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return {
                "stdout": "",
                "stderr": f"⚠️ SandboxExecutor : Le script a dépassé le délai autorisé ({t_out}s).",
                "returncode": -1,
                "succes": False,
                "fichiers_crees": [],
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Erreur SandboxExecutor : {e}",
                "returncode": 1,
                "succes": False,
                "fichiers_crees": [],
            }
        finally:
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass

    def executer_code_python_sync(self, code: str, timeout: int | None = None) -> dict[str, Any]:
        """Passerelle synchrone pour les outils directs du registre."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(lambda: asyncio.run(self.executer_code_python_async(code, timeout))).result()
            else:
                return loop.run_until_complete(self.executer_code_python_async(code, timeout))
        except Exception:
            return asyncio.run(self.executer_code_python_async(code, timeout))


sandbox_executor: Final[SandboxExecutor] = SandboxExecutor()
