"""
tools/graph_memory.py — Graphe de Connaissances Relationnel SQLite (GraphRAG Local).
Mode WAL activé et timeout étendu pour supporter la concurrence sans verrouillage.
"""

from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path
from typing import Final

import config
from config import SecurityTier
from core.tools_registry import outil

DB_GRAPH_PATH: Final[Path] = Path(config.GRAPHE_DB_PATH) / "jajar_knowledge_graph.sqlite"


def _init_graph_db() -> sqlite3.Connection:
    DB_GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_GRAPH_PATH), timeout=30.0)
    with conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entites (
                id TEXT PRIMARY KEY,
                type TEXT,
                nom TEXT,
                attributs TEXT,
                date_maj TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                source_id TEXT,
                relation TEXT,
                cible_id TEXT,
                contexte TEXT,
                date_maj TEXT,
                PRIMARY KEY (source_id, relation, cible_id)
            )
        """)
    return conn


@outil(tier=SecurityTier.AUTO)
def enregistrer_relation_graphe(source_nom: str, type_relation: str, cible_nom: str, details: str = "") -> str:
    """Enregistre un lien relationnel dans le Graphe sans risque de verrouillage."""
    conn = _init_graph_db()
    ts = datetime.datetime.now().isoformat()
    s_id = source_nom.strip().lower()
    c_id = cible_nom.strip().lower()
    rel = type_relation.strip().lower()

    try:
        with conn:
            conn.execute("INSERT OR REPLACE INTO entites VALUES (?, ?, ?, ?, ?)", (s_id, "entite", source_nom.strip(), details, ts))
            conn.execute("INSERT OR REPLACE INTO entites VALUES (?, ?, ?, ?, ?)", (c_id, "entite", cible_nom.strip(), details, ts))
            conn.execute("INSERT OR REPLACE INTO relations VALUES (?, ?, ?, ?, ?)", (s_id, rel, c_id, details, ts))
        return f"🔗 Relation enregistrée : « {source_nom} » ➔ [{type_relation}] ➔ « {cible_nom} »"
    finally:
        conn.close()


@outil(tier=SecurityTier.AUTO)
def explorer_graphe_connaissances(entite_cle: str) -> str:
    """Explore toutes les relations associées à une entité dans le Graphe."""
    conn = _init_graph_db()
    e_id = entite_cle.strip().lower()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.source_id, r.relation, r.cible_id, r.contexte 
            FROM relations r 
            WHERE r.source_id = ? OR r.cible_id = ?
        """, (e_id, e_id))
        lignes = cursor.fetchall()

        if not lignes:
            return f"ℹ️ Aucune relation enregistrée pour « {entite_cle} »."

        rendu = [f"🌐 **Graphe de Connaissances pour « {entite_cle} » :**"]
        for s, r, c, ctx in lignes:
            note_ctx = f" *(Détail : {ctx})*" if ctx else ""
            rendu.append(f"• `{s}` ➔ **[{r}]** ➔ `{c}`{note_ctx}")

        return "\n".join(rendu)
    finally:
        conn.close()
