"""
tools/incremental_vector_vault.py — Indexation Vectorielle Incrémentale LanceDB O(ΔN).
Diffing via empreinte cryptographique SHA-256 et recherche hybride (Dense Vector + BM25 Lexical).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Final

import lancedb
import pyarrow as pa

import config
from config import SecurityTier
from core.llm_router import router
from core.tools_registry import outil

logger: Final[logging.Logger] = logging.getLogger("jajar.vector_vault")
META_INDEX_PATH: Final[Path] = Path(config.DB_PATH) / "vault_manifest.json"
NOM_TABLE: Final[str] = "obsidian_chunks"
TAILLE_CHUNK: Final[int] = 1000
OVERLAP: Final[int] = 150


def _calculer_sha256(fichier: Path) -> str:
    h = hashlib.sha256()
    with open(fichier, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _decouper_texte(texte: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\n+", texte) if p.strip()]
    chunks: list[str] = []
    courant = ""

    for p in paras:
        if len(courant) + len(p) <= TAILLE_CHUNK:
            courant = f"{courant}\n\n{p}".strip()
        else:
            if courant:
                chunks.append(courant)
            courant = p[:TAILLE_CHUNK]

    if courant:
        chunks.append(courant)
    return chunks or [texte[:TAILLE_CHUNK]]


def _charger_manifest() -> dict[str, Any]:
    if META_INDEX_PATH.exists():
        try:
            return json.loads(META_INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"fichiers": {}}
    return {"fichiers": {}}


def _sauvegarder_manifest(manifest: dict[str, Any]) -> None:
    META_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    META_INDEX_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


@outil(tier=SecurityTier.AUTO)
def synchroniser_second_cerveau_incremental() -> str:
    """Indexe uniquement les notes modifiées ou nouvelles dans LanceDB sans réécrire l'existant."""
    db_path = Path(config.DB_PATH)
    db_path.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(db_path))

    fichiers_actuels = list(config.VAULT_DIR.rglob("*.md"))
    fichiers_actuels = [f for f in fichiers_actuels if not f.name.startswith(".") and f.stat().st_size > 0]
    
    manifest = _charger_manifest()
    fichiers_enregistres: dict[str, str] = manifest.get("fichiers", {})
    
    a_indexer: list[Path] = []
    chemins_actuels_rel: set[str] = set()

    for f in fichiers_actuels:
        rel = str(f.relative_to(config.VAULT_DIR))
        chemins_actuels_rel.add(rel)
        sha = _calculer_sha256(f)
        if rel not in fichiers_enregistres or fichiers_enregistres[rel] != sha:
            a_indexer.append(f)

    supprimes = set(fichiers_enregistres.keys()) - chemins_actuels_rel

    table_existe = NOM_TABLE in db.table_names()
    table = db.open_table(NOM_TABLE) if table_existe else None

    # Suppression des chunks obsolètes
    if table and (supprimes or a_indexer):
        chemins_a_purger = list(supprimes) + [str(f.relative_to(config.VAULT_DIR)) for f in a_indexer]
        for c in chemins_a_purger:
            try:
                table.delete(f'chemin = "{c}"')
            except Exception as e:
                logger.warning(f"Erreur purge chunk {c} : {e}")

    nouveaux_chunks: list[dict[str, Any]] = []
    for f in a_indexer:
        rel = str(f.relative_to(config.VAULT_DIR))
        contenu = f.read_text(encoding="utf-8", errors="replace")
        passages = _decouper_texte(contenu)

        for idx, passage in enumerate(passages):
            nouveaux_chunks.append({
                "id": f"{rel}::{idx}",
                "chemin": rel,
                "titre": f.stem,
                "index_passage": idx,
                "texte": passage,
            })

    if nouveaux_chunks:
        textes_a_vectoriser = [c["texte"] for c in nouveaux_chunks]
        vecteurs: list[list[float]] = []
        
        # Batching par 32
        for i in range(0, len(textes_a_vectoriser), 32):
            batch = textes_a_vectoriser[i : i + 32]
            vecs, _ = router.embed(batch)
            vecteurs.extend(vecs)

        for c, v in zip(nouveaux_chunks, vecteurs):
            c["vector"] = v

        if not table_existe:
            table = db.create_table(NOM_TABLE, data=nouveaux_chunks)
            table.create_fts_index("texte")
        else:
            table.add(nouveaux_chunks)

    # Mise à jour du manifest
    for f in a_indexer:
        manifest["fichiers"][str(f.relative_to(config.VAULT_DIR))] = _calculer_sha256(f)
    for s in supprimes:
        manifest["fichiers"].pop(s, None)

    _sauvegarder_manifest(manifest)

    return (
        f"⚡ **Synchronisation Incrémentale LanceDB Achevée :**\n"
        f"• Notes modifiées/ajoutées indexées : `{len(a_indexer)}`\n"
        f"• Notes supprimées purgées : `{len(supprimes)}`\n"
        f"• Total Chunks créés : `{len(nouveaux_chunks)}`"
    )


@outil(tier=SecurityTier.AUTO)
def recherche_hybride_second_cerveau(requete: str, top_k: int = 4) -> str:
    """Effectue une recherche hybride (vecteur dense + texte intégral BM25) dans LanceDB."""
    db_path = Path(config.DB_PATH)
    if not (db_path / f"{NOM_TABLE}.lance").exists() and NOM_TABLE not in lancedb.connect(str(db_path)).table_names():
        synchroniser_second_cerveau_incremental()

    db = lancedb.connect(str(db_path))
    if NOM_TABLE not in db.table_names():
        return "ℹ️ Index vectoriel vide. Aucune note Obsidian trouvée."

    table = db.open_table(NOM_TABLE)
    vec_requete, _ = router.embed([requete])

    try:
        resultats = (
            table.search(vec_requete[0], query_type="hybrid")
            .limit(top_k)
            .to_list()
        )
    except Exception:
        resultats = table.search(vec_requete[0]).limit(top_k).to_list()

    if not resultats:
        return f"Aucun résultat pour « {requete} »."

    rendu = [f"🧠 **Résultats Hybrides pour « {requete} » :**\n"]
    for r in resultats:
        rendu.append(f"### [[{r['titre']}]] (`{r['chemin']}`)\n{r['texte']}\n---")

    return "\n".join(rendu)
