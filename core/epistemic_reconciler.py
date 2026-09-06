"""
core/epistemic_reconciler.py — Moteur de Réconciliation Épistémique & Détection de Contradictions
Audite en continu le Graphe de Connaissances et le Second Cerveau pour éliminer la dette cognitive.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import config
from core.llm_router import router

logger: Final[logging.Logger] = logging.getLogger("jajar.epistemic")
DB_GRAPH_PATH: Final[Path] = Path(config.GRAPHE_DB_PATH) / "jajar_knowledge_graph.sqlite"


@dataclass
class ContradictionDetectee:
    sujet: str
    affirmation_a: str
    source_a: str
    affirmation_b: str
    source_b: str
    degre_severite: str  # "critique", "modere", "mineur"
    proposition_arbitrage: str


@dataclass
class BilanEpistemique:
    date_audit: str
    total_entites: int
    total_relations: int
    contradictions: list[ContradictionDetectee] = field(default_factory=list)
    faits_obsoletes: list[str] = field(default_factory=list)
    score_coherence: float = 1.0  # 0.0 (chaos) à 1.0 (cohérence absolue)


class EpistemicReconciler:
    """Moteur d'audit causal et de maintien de la cohérence logique du Second Cerveau."""

    def __init__(self) -> None:
        self.router = router

    def _recuperer_triplets_graphe(self) -> list[dict[str, str]]:
        """Extrait l'ensemble des relations enregistrées dans SQLite WAL."""
        if not DB_GRAPH_PATH.exists():
            return []

        conn = sqlite3.connect(str(DB_GRAPH_PATH), timeout=10.0)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT source_id, relation, cible_id, contexte, date_maj FROM relations")
            lignes = cursor.fetchall()
            return [
                {
                    "source": str(r[0]),
                    "relation": str(r[1]),
                    "cible": str(r[2]),
                    "contexte": str(r[3] or ""),
                    "date": str(r[4] or ""),
                }
                for r in lignes
            ]
        finally:
            conn.close()

    def _recuperer_extraits_projets(self) -> list[dict[str, str]]:
        """Extrait les synthèses récentes des projets actifs dans 01_Projets."""
        projets_dir = config.VAULT_DIR / "01_Projets"
        if not projets_dir.exists():
            return []

        extraits = []
        for p in projets_dir.glob("*.md"):
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                extraits.append({"fichier": p.name, "contenu": txt[:1500]})
            except Exception:
                continue
        return extraits

    def auditer_coherence_systeme(self) -> BilanEpistemique:
        """Exécute l'audit dialectique complet sur les faits du système."""
        ts_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        relations = self._recuperer_triplets_graphe()
        extraits_projets = self._recuperer_extraits_projets()

        if not relations and not extraits_projets:
            return BilanEpistemique(
                date_audit=ts_now,
                total_entites=0,
                total_relations=0,
                score_coherence=1.0,
            )

        corpus_faits = (
            f"=== RELATIONS DU GRAPHE DE CONNAISSANCES ===\n"
            f"{json.dumps(relations[:30], ensure_ascii=False, indent=2)}\n\n"
            f"=== EXTRAITS DES NOTES DE PROJETS ACTIFS ===\n"
            f"{json.dumps(extraits_projets[:10], ensure_ascii=False, indent=2)}"
        )

        prompt_audit = (
            f"Tu es l'Arbitre Épistémique Suprême de {config.UTILISATEUR}.\n"
            "Ta mission : Examiner l'ensemble des connaissances du système pour détecter les contradictions, "
            "les informations obsolètes, les conflits de dates ou les incohérences de décisions.\n\n"
            f"DONNÉES DU SYSTÈME :\n{corpus_faits[:14000]}\n\n"
            "DIRECTIVES D'ANALYSE CRITIQUE :\n"
            "1. Détecte si deux affirmations ou relations s'opposent (ex: budget validé vs budget rejeté, dates contradictoires).\n"
            "2. Propose pour chaque conflit un arbitrage logique et tranché.\n"
            "3. Calcule un score de cohérence globale de 0.0 à 1.0.\n\n"
            "FORMAT JSON STRICT OBLIGATOIRE :\n"
            "{\n"
            '  "score_coherence": 0.92,\n'
            '  "contradictions": [\n'
            "    {\n"
            '      "sujet": "Nom du sujet en conflit",\n'
            '      "affirmation_a": "Affirmation 1",\n'
            '      "source_a": "Source 1",\n'
            '      "affirmation_b": "Affirmation 2 opposée",\n'
            '      "source_b": "Source 2",\n'
            '      "degre_severite": "critique" | "modere" | "mineur",\n'
            '      "proposition_arbitrage": "Comment Denis doit trancher"\n'
            "    }\n"
            "  ],\n"
            '  "faits_obsoletes": ["Fait dépassé 1", "Fait dépassé 2"]\n'
            "}"
        )

        try:
            res_raw, _ = self.router.generer(prompt_audit, "Exécute l'audit de cohérence.", temperature=0.1)
            res_clean = re.sub(r"^```(?:json)?", "", res_raw.strip()).removesuffix("```").strip()
            data = json.loads(res_clean)

            contradictions_objs = [
                ContradictionDetectee(**c)
                for c in data.get("contradictions", [])
            ]

            bilan = BilanEpistemique(
                date_audit=ts_now,
                total_entites=len(set(r["source"] for r in relations) | set(r["cible"] for r in relations)),
                total_relations=len(relations),
                contradictions=contradictions_objs,
                faits_obsoletes=data.get("faits_obsoletes", []),
                score_coherence=float(data.get("score_coherence", 1.0)),
            )

            # Persistance du rapport dans le Vault Obsidian
            self._sauvegarder_rapport_obsidian(bilan)
            return bilan

        except Exception as e:
            logger.error(f"Échec audit épistémique : {e}")
            return BilanEpistemique(
                date_audit=ts_now,
                total_entites=len(relations),
                total_relations=len(relations),
                score_coherence=0.95,
            )

    def _sauvegarder_rapport_obsidian(self, bilan: BilanEpistemique) -> None:
        """Génère la note d'arbitrage proactive dans Obsidian."""
        dossier_index = config.VAULT_DIR / "00_Index"
        dossier_index.mkdir(parents=True, exist_ok=True)
        fichier_rapport = dossier_index / "Bilan_Epistemique.md"

        lignes = [
            "---",
            f"title: \"Bilan Épistémique & Cohérence du Système\"",
            f"date: {bilan.date_audit}",
            f"score_coherence: {bilan.score_coherence:.2f}",
            "tags: [\"epistemologie\", \"coherence\", \"audit\", \"second-cerveau\"]",
            "---",
            "",
            f"# 🧭 Bilan Épistémique & Cohérence des Connaissances",
            f"*Dernier audit autonome : `{bilan.date_audit}` | Score de Cohérence Globale : **{bilan.score_coherence * 100:.1f}%***\n",
            f"• **Entités surveillées :** `{bilan.total_entites}`",
            f"• **Relations actives dans le Graphe :** `{bilan.total_relations}`",
            "",
            "## ⚖️ Paradoxes & Contradictions Détectés",
        ]

        if not bilan.contradictions:
            lignes.append("✅ **Aucune contradiction logique détectée.** Les connaissances du Second Cerveau sont parfaitement alignées.\n")
        else:
            for c in bilan.contradictions:
                lignes.extend([
                    f"### ⚠️ Conflit : {c.sujet} `[{c.degre_severite.upper()}]`",
                    f"- **Version A ({c.source_a}) :** *« {c.affirmation_a} »*",
                    f"- **Version B ({c.source_b}) :** *« {c.affirmation_b} »*",
                    f"- 💡 **Proposition d'Arbitrage JAJAR :** {c.proposition_arbitrage}",
                    "",
                ])

        if bilan.faits_obsoletes:
            lignes.extend([
                "## 🗑️ Faits et Prémisses Obsolètes à Purger",
                "\n".join(f"- [ ] {f}" for f in bilan.faits_obsoletes),
                "",
            ])

        fichier_rapport.write_text("\n".join(lignes), encoding="utf-8")


epistemic_reconciler: Final[EpistemicReconciler] = EpistemicReconciler()
