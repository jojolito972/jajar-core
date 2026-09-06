from __future__ import annotations

"""
core/orchestrator_bus.py — Bus d'Orchestration Multi-Agents Asynchrone (Actor Model).
Gère l'exécution concurrente de tâches en arrière-plan, la priorité et les callbacks non-bloquants.
"""

import asyncio
import datetime
import enum
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Final, Optional

logger: Final[logging.Logger] = logging.getLogger("jajar.orchestrator")


class TaskPriority(enum.IntEnum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    BACKGROUND = 3


class TaskStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(order=True)
class AgentTask:
    priority: int
    created_at: float = field(compare=True)
    task_id: str = field(compare=False)
    source_agent: str = field(compare=False)
    target_agent: str = field(compare=False)
    instruction: str = field(compare=False)
    context: dict[str, Any] = field(default_factory=dict, compare=False)
    callback: Optional[Callable[[AgentTask], Coroutine[Any, Any, None]]] = field(default=None, compare=False)
    status: TaskStatus = field(default=TaskStatus.PENDING, compare=False)
    result: Optional[str] = field(default=None, compare=False)
    error: Optional[str] = field(default=None, compare=False)
    execution_time_sec: float = field(default=0.0, compare=False)


class MultiAgentBus:
    """Bus central d'orchestration non-bloquant pour l'écosystème d'agents JAJAR."""

    def __init__(self, max_concurrent_workers: int = 3) -> None:
        self.queue: asyncio.PriorityQueue[AgentTask] = asyncio.PriorityQueue()
        self.active_tasks: dict[str, AgentTask] = {}
        self.completed_tasks: dict[str, AgentTask] = {}
        self.max_workers: int = max_concurrent_workers
        self._workers: list[asyncio.Task[None]] = []
        self._is_running: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()
        self._notification_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def start(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        for i in range(self.max_workers):
            worker_task = asyncio.create_task(self._worker_loop(worker_id=i))
            self._workers.append(worker_task)
        logger.info(f"🚀 Bus Multi-Agents actif ({self.max_workers} workers concurrents).")

    async def stop(self) -> None:
        self._is_running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("🛑 Bus Multi-Agents arrêté.")

    async def deleguer_tache(
        self,
        source_agent: str,
        target_agent: str,
        instruction: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        context: Optional[dict[str, Any]] = None,
        callback: Optional[Callable[[AgentTask], Coroutine[Any, Any, None]]] = None,
    ) -> str:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        t = AgentTask(
            priority=int(priority),
            created_at=asyncio.get_event_loop().time(),
            task_id=task_id,
            source_agent=source_agent.lower(),
            target_agent=target_agent.lower(),
            instruction=instruction,
            context=context or {},
            callback=callback,
        )
        async with self._lock:
            self.active_tasks[task_id] = t

        await self.queue.put(t)
        logger.info(f"📋 Tâche [{task_id}] déléguée : {source_agent.upper()} ➔ {target_agent.upper()} (Prio: {priority.name})")
        return task_id

    async def _worker_loop(self, worker_id: int) -> None:
        from core.engine import run_agent

        while self._is_running:
            try:
                task = await self.queue.get()
                task.status = TaskStatus.RUNNING
                t_debut = asyncio.get_event_loop().time()

                logger.info(f"⚙️ Worker-{worker_id} : Exécution tâche [{task.task_id}] par {task.target_agent.upper()}")

                try:
                    rep, tokens, chrono, moteur = await asyncio.to_thread(
                        run_agent,
                        task=task.instruction,
                        persona=task.target_agent,
                        mode_operationnel="auto",
                    )
                    task.result = rep
                    task.status = TaskStatus.COMPLETED
                    task.execution_time_sec = round(asyncio.get_event_loop().time() - t_debut, 2)
                    logger.info(f"✅ Tâche [{task.task_id}] complétée par {task.target_agent.upper()} en {task.execution_time_sec}s")

                except Exception as err:
                    task.error = str(err)
                    task.status = TaskStatus.FAILED
                    task.execution_time_sec = round(asyncio.get_event_loop().time() - t_debut, 2)
                    logger.error(f"❌ Échec tâche [{task.task_id}] : {err}")

                # Émission de notification vers l'UI
                await self._notification_queue.put({
                    "task_id": task.task_id,
                    "agent": task.target_agent,
                    "status": task.status.value,
                    "result": task.result,
                    "chrono": task.execution_time_sec,
                })

                if task.callback:
                    try:
                        await task.callback(task)
                    except Exception as cb_err:
                        logger.error(f"Erreur callback tâche [{task.task_id}] : {cb_err}")

                async with self._lock:
                    self.completed_tasks[task.task_id] = task
                    self.active_tasks.pop(task.task_id, None)

                self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as loop_err:
                logger.error(f"Erreur Worker-{worker_id} : {loop_err}")
                await asyncio.sleep(1.0)

    async def recuperer_notifications_en_attente(self) -> list[dict[str, Any]]:
        notifs = []
        while not self._notification_queue.empty():
            try:
                notifs.append(self._notification_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return notifs

    def obtenir_statut_taches(self) -> dict[str, Any]:
        return {
            "en_cours": [
                {"id": t.task_id, "cible": t.target_agent, "instruction": t.instruction[:40]}
                for t in self.active_tasks.values() if t.status == TaskStatus.RUNNING
            ],
            "en_attente": self.queue.qsize(),
            "terminees_recentes": len(self.completed_tasks),
        }


orchestrator_bus: Final[MultiAgentBus] = MultiAgentBus(max_concurrent_workers=3)
