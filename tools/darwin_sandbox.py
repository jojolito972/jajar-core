"""
tools/darwin_sandbox.py — Bac à Sable Confiné Spécifique à macOS (Darwin Architecture).
Résout l'inopérance de RLIMIT_AS via un superviseur de mémoire psutil temps-réel et isolation POSIX.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Final

import psutil

import config
from config import SecurityTier
from core.security import verifier_commande_securisee
from core.tools_registry import outil

logger: Final[logging.Logger] = logging.getLogger("jajar.darwin_sandbox")


class DarwinSandbox:
    def __init__(self, max_ram_mb: int = 512, default_timeout_sec: int = 20) -> None:
        self.sandbox_dir: Path = config.SANDBOX_DIR
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.max_ram_bytes: int = max_ram_mb * 1024 * 1024
        self.default_timeout: int = default_timeout_sec

    async def _superviser_processus(self, proc: asyncio.subprocess.Process, pid: int, timeout: int) -> tuple[bool, str]:
        """Monitore la RSS (Resident Set Size) active du sous-processus sur Darwin."""
        t_debut = time.time()
        while proc.returncode is None:
            if time.time() - t_debut > timeout:
                try:
                    p = psutil.Process(pid)
                    p.kill()
                except Exception:
                    pass
                return False, f"Timeout : Exécution interrompue après {timeout}s."

            try:
                p = psutil.Process(pid)
                memoire_rss = p.memory_info().rss
                # Vérification des processus enfants
                for child in p.children(recursive=True):
                    memoire_rss += child.memory_info().rss

                if memoire_rss > self.max_ram_bytes:
                    p.kill()
                    return False, f"Dépassement mémoire (OOM Guard) : {round(memoire_rss / (1024*1024), 1)} Mo alloués (Max: {self.max_ram_bytes // (1024*1024)} Mo)."
            except psutil.NoSuchProcess:
                break
            except Exception:
                pass

            await asyncio.sleep(0.1)

        return True, ""

    async def executer_code_python_isole(self, code: str, timeout: int | None = None) -> dict[str, Any]:
        t_out = timeout or self.default_timeout
        run_id = uuid.uuid4().hex[:8]
        tmp_script = self.sandbox_dir / f"sandbox_{run_id}.py"
        tmp_script.write_text(code, encoding="utf-8")

        fichiers_initiaux = set(self.sandbox_dir.glob("*"))

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",  # Mode Isolé : ignore PYTHONPATH et les scripts de démarrage utilisateur
                str(tmp_script),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.sandbox_dir),
                start_new_session=True,
            )

            pid = proc.pid
            supervision_task = asyncio.create_task(self._superviser_processus(proc, pid, t_out))

            stdout_bytes, stderr_bytes = await proc.communicate()
            succes_memoire, erreur_memoire = await supervision_task

            fichiers_apres = set(self.sandbox_dir.glob("*"))
            fichiers_generes = [
                str(f.name) for f in (fichiers_apres - fichiers_initiaux)
                if f != tmp_script and not f.name.startswith(".")
            ]

            if not succes_memoire:
                return {
                    "stdout": "",
                    "stderr": erreur_memoire,
                    "returncode": -9,
                    "succes": False,
                    "fichiers_crees": [],
                }

            return {
                "stdout": stdout_bytes.decode("utf-8", errors="replace").strip(),
                "stderr": stderr_bytes.decode("utf-8", errors="replace").strip(),
                "returncode": proc.returncode,
                "succes": proc.returncode == 0,
                "fichiers_crees": fichiers_generes,
            }

        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Erreur Sandbox Darwin : {e}",
                "returncode": 1,
                "succes": False,
                "fichiers_crees": [],
            }
        finally:
            if tmp_script.exists():
                try:
                    tmp_script.unlink()
                except Exception:
                    pass


darwin_sandbox: Final[DarwinSandbox] = DarwinSandbox()


@outil(tier=SecurityTier.AUTO)
def executer_script_python_securise(code_python: str) -> str:
    """Exécute du code Python confiné avec limitation RAM stricte et surveillance d'effets de bord."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            res = pool.submit(lambda: asyncio.run(darwin_sandbox.executer_code_python_isole(code_python))).result()
    else:
        res = loop.run_until_complete(darwin_sandbox.executer_code_python_isole(code_python))

    if res["succes"]:
        out = f"✅ **Exécution Réussie (Code 0) :**\n```text\n{res['stdout'] or '(Aucune sortie console)'}\n```"
        if res["fichiers_crees"]:
            out += f"\n📁 **Fichiers réels créés :** {', '.join(f'`{f}`' for f in res['fichiers_crees'])}"
        return out
    else:
        return f"⚠️ **Échec d'Exécution (Code {res['returncode']}) :**\n```text\n{res['stderr'] or res['stdout']}\n```"
