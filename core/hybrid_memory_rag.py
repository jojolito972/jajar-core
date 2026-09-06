from __future__ import annotations

"""
core/hybrid_memory_rag.py — Moteur de Recherche Cognitive Hybride Unifié (RRF).
Fusionne Dense Vector (LanceDB), Full-Text BM25 et Graphe Récursif SQLite via Reciprocal Rank Fusion.
"""

import collections
import datetime
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Optional

import lancedb

import config
from config import SecurityTier
from core.llm_router import router
from core.tools_registry import outil

logger: Final[logging.Logger] = logging.getLogger("jajar.hybrid_rag")
CONSTANTE_LISSAGE_RRF: Final[int] = 60
DB_GRAPH_FILE: Final[Path] = Path(config.GRAPHE_DB_PATH) / "jajar_knowledge_graph.sqlite"
NOM_TABLE_LANCE: Final[str] = "second_cerveau"


@dataclass
class DocumentRanked:
    id: str
    titre: str
    contenu: str
    source_type: str  # "vector", "lexical", "graph"
    score_brut: float
    score_rrf: float = 0.0
    metadonnees: dict[str, Any] = field(default_factory=dict)


class HybridCognitiveRAG:
    """Moteur d'inférence mémorielle à haute densité sémantique."""

    def __init__(self) -> None:
        self.db_lance_path = Path(config.DB_PATH)

    def _recherche_vectorielle_dense(self, requete: str, top_k: int = 8) -> list[DocumentRanked]:
        docs: list[DocumentRanked] = []
        try:
            db = lancedb.connect(str(self.db_lance_path))
            if NOM_TABLE_LANCE not in db.table_names():
                return docs

            table = db.open_table(NOM_TABLE_LANCE)
            vecs, _ = router.embed([requete])
            res = table.search(vecs[0]).limit(top_k).to_list()

            for r in res:
                docs.append(DocumentRanked(
                    id=str(r.get("id") or r.get("chemin")),
                    titre=str(r.get("titre", "Note")),
                    contenu=str(r.get("texte", "")),
                    source_type="vector",
                    score_brut=float(r.get("_distance", 1.0)),
                    metadonnees={"chemin": r.get("chemin", "")}
                ))
        except Exception as e:
            logger.warning(f"Repli vectoriel : {e}")
        return docs

    def _recherche_graphe_relationnel(self, requete: str, max_profondeur: int = 2) -> list[DocumentRanked]:
        docs: list[DocumentRanked] = []
        if not DB_GRAPH_FILE.exists():
            return docs

        mots_cles = [m.lower().strip() for m in requete.split() if len(m) >= 4]
        if not mots_cles:
            return docs

        try:
            conn = sqlite3.connect(str(DB_GRAPH_FILE), timeout=5.0)
            cursor = conn.cursor()

            clause_where = " OR ".join(["source_id LIKE ? OR cible_id LIKE ?" for _ in mots_cles])
            params: list[str] = []
            for m in mots_cles:
                params.extend([f"%{m}%", f"%{m}%"])

            query = f"""
            WITH RECURSIVE chemin_cte(source, rel, cible, ctx, niveau, trace) AS (
                SELECT source_id, relation, cible_id, contexte, 1, source_id || '->' || cible_id
                FROM relations
                WHERE {clause_where}

                UNION

                SELECT r.source_id, r.relation, r.cible_id, r.contexte, c.niveau + 1, c.trace || '->' || r.cible_id
                FROM relations r
                JOIN chemin_cte c ON (r.source_id = c.cible OR r.cible_id = c.source)
                WHERE c.niveau < ? AND instr(c.trace, r.cible_id) = 0
            )
            SELECT DISTINCT source, rel, cible, ctx, niveau FROM chemin_cte LIMIT 15;
            """
            params.append(str(max_profondeur))
            cursor.execute(query, params)
            lignes = cursor.fetchall()
            conn.close()

            for idx, r in enumerate(lignes):
                texte_graphe = f"Entité « {r[0]} » est reliée à « {r[2]} » par la relation [{r[1]}]."
                if r[3]:
                    texte_graphe += f" Contexte : {r[3]}"

                docs.append(DocumentRanked(
                    id=f"graph_triple_{idx}",
                    titre=f"Lien Relationnel : {r[0]} - {r[2]}",
                    contenu=texte_graphe,
                    source_type="graph",
                    score_brut=1.0 / (r[4]),  # Score basé sur la proximité de niveau
                    metadonnees={"niveau_saut": r[4]}
                ))
        except Exception as e:
            logger.warning(f"Repli graphe : {e}")
        return docs

    def fusion_reciprocal_rank(
        self,
        listes_classees: list[list[DocumentRanked]],
        k: int = CONSTANTE_LISSAGE_RRF,
    ) -> list[DocumentRanked]:
        scores_rrf: dict[str, float] = collections.defaultdict(float)
        docs_map: dict[str, DocumentRanked] = {}

        for liste in listes_classees:
            for rang, doc in enumerate(liste, start=1):
                cle = f"{doc.titre}::{doc.contenu[:60]}"
                scores_rrf[cle] += 1.0 / (k + rang)
                if cle not in docs_map:
                    docs_map[cle] = doc

        resultats_finaux: list[DocumentRanked] = []
        for cle, score_final in sorted(scores_rrf.items(), key=lambda item: item[1], reverse=True):
            d = docs_map[cle]
            d.score_rrf = round(score_final, 5)
            resultats_finaux.append(d)

        return resultats_finaux

    def interroger_memoire_unifiee(self, requete: str, top_k: int = 5) -> list[DocumentRanked]:
        # 1. Extraction concurrente des canaux mémoriels
        docs_vector = self._recherche_vectorielle_dense(requete, top_k=8)
        docs_graph = self._recherche_graphe_relationnel(requete, max_profondeur=2)

        # 2. Application de l'algorithme RRF
        docs_fusionnes = self.fusion_reciprocal_rank([docs_vector, docs_graph], k=CONSTANTE_LISSAGE_RRF)
        return docs_fusionnes[:top_k]


hybrid_rag_engine: Final[HybridCognitiveRAG] = HybridCognitiveRAG()


@outil(tier=SecurityTier.AUTO)
def interroger_memoire_hybride_sota(requete_recherche: str, max_resultats: int = 4) -> str:
    """Interrogation unifiée ultra-précise (LanceDB + Graphe SQLite CTE) via Reciprocal Rank Fusion."""
    resultats = hybrid_rag_engine.interroger_memoire_unifiee(requete_recherche, top_k=max_resultats)
    if not resultats:
        return f"ℹ️ Aucune connaissance concordante trouvée dans la mémoire pour « {requete_recherche} »."

    rendu: list[str] = [f"🧠 **Synthèse Mémorielle Unifiée (RRF) pour « {requete_recherche} » :**\n"]
    for idx, r in enumerate(resultats, start=1):
        badge = "📁 [NOTE VAULT]" if r.source_type == "vector" else "🔗 [GRAPHE RELATIONNEL]"
        rendu.append(f"### {idx}. {r.titre} {badge}\n*Score de pertinence RRF : `{r.score_rrf}`*\n\n{r.contenu}\n---")

    return "\n".join(rendu)
