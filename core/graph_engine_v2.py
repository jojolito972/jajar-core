"""
core/graph_engine_v2.py — Graphe de Connaissances Transactionnel SQLite WAL avec Recursive CTE.
Supporte le parcours multi-sauts (multi-hop traversal) et la détection topologique de cycles/contradictions.
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
from pathlib import Path
from typing import Any, Final

import config
from config import SecurityTier
from core.tools_registry import outil

logger: Final[logging.Logger] = logging.getLogger("jajar.graph_v2")
DB_GRAPH_FILE: Final[Path] = Path(config.GRAPHE_DB_PATH) / "graph_v2.sqlite"


class GraphEngineV2:
    def __init__(self) -> None:
        DB_GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_GRAPH_FILE), timeout=20.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS entites (
                    id TEXT PRIMARY KEY,
                    nom TEXT NOT NULL,
                    categorie TEXT NOT NULL,
                    attributs_json TEXT DEFAULT '{}',
                    date_maj TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS relations (
                    source_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    cible_id TEXT NOT NULL,
                    poids REAL DEFAULT 1.0,
                    contexte TEXT DEFAULT '',
                    date_maj TEXT NOT NULL,
                    PRIMARY KEY (source_id, relation, cible_id),
                    FOREIGN KEY (source_id) REFERENCES entites(id) ON DELETE CASCADE,
                    FOREIGN KEY (cible_id) REFERENCES entites(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_rel_source ON relations(source_id);
                CREATE INDEX IF NOT EXISTS idx_rel_cible ON relations(cible_id);
                CREATE INDEX IF NOT EXISTS idx_rel_type ON relations(relation);
            """)

    def inserer_relation(self, source: str, relation: str, cible: str, contexte: str = "", poids: float = 1.0) -> None:
        s_id = source.strip().lower()
        c_id = cible.strip().lower()
        rel = relation.strip().lower()
        now = datetime.datetime.now().isoformat()

        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO entites (id, nom, categorie, date_maj) VALUES (?, ?, 'general', ?) ON CONFLICT(id) DO UPDATE SET date_maj=excluded.date_maj",
                (s_id, source.strip(), now),
            )
            conn.execute(
                "INSERT INTO entites (id, nom, categorie, date_maj) VALUES (?, ?, 'general', ?) ON CONFLICT(id) DO UPDATE SET date_maj=excluded.date_maj",
                (c_id, cible.strip(), now),
            )
            conn.execute(
                """
                INSERT INTO relations (source_id, relation, cible_id, poids, contexte, date_maj)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, relation, cible_id) DO UPDATE SET
                    poids=excluded.poids,
                    contexte=excluded.contexte,
                    date_maj=excluded.date_maj
                """,
                (s_id, rel, c_id, poids, contexte.strip(), now),
            )

    def parcours_multi_sauts(self, entite_depart: str, max_profondeur: int = 2) -> list[dict[str, Any]]:
        """Exécute une traversée en largeur via une expression de table commune récursive (CTE)."""
        e_id = entite_depart.strip().lower()
        query = """
        WITH RECURSIVE chemin_graphe(source, rel, cible, niveau, chemin_visite) AS (
            SELECT source_id, relation, cible_id, 1, source_id || '->' || cible_id
            FROM relations
            WHERE source_id = :start_node OR cible_id = :start_node
            
            UNION
            
            SELECT r.source_id, r.relation, r.cible_id, cg.niveau + 1, cg.chemin_visite || '->' || r.cible_id
            FROM relations r
            JOIN chemin_graphe cg ON (r.source_id = cg.cible OR r.cible_id = cg.source)
            WHERE cg.niveau < :max_depth
              AND instr(cg.chemin_visite, r.cible_id) = 0
        )
        SELECT DISTINCT source, rel, cible, niveau FROM chemin_graphe ORDER BY niveau ASC;
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, {"start_node": e_id, "max_depth": max_profondeur})
            lignes = cursor.fetchall()
            return [{"source": r[0], "relation": r[1], "cible": r[2], "niveau": r[3]} for r in lignes]


graph_v2: Final[GraphEngineV2] = GraphEngineV2()


@outil(tier=SecurityTier.AUTO)
def explorer_relations_profondes(entite: str, profondeur: int = 2) -> str:
    """Traverse le graphe de connaissances sur N sauts pour extraire les liens indirects."""
    liens = graph_v2.parcours_multi_sauts(entite, max_profondeur=min(3, max(1, profondeur)))
    if not liens:
        return f"ℹ️ Aucune connexion trouvée pour l'entité « {entite} »."

    rendu = [f"🌐 **Cartographie Récursive pour « {entite} » (Profondeur {profondeur}) :**\n"]
    for l in liens:
        indent = "  " * (l["niveau"] - 1)
        rendu.append(f"{indent}• [Niveau {l['niveau']}] `{l['source']}` ➔ **[{l['relation']}]** ➔ `{l['cible']}`")

    return "\n".join(rendu)
