"""
tools/second_cerveau.py — Gestionnaire de mémoire vectorielle LanceDB incrémentale.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any, Final

import config
from config import SecurityTier
from core.llm_router import router
from core.tools_registry import outil

logger: Final[logging.Logger] = logging.getLogger("jajar.second_cerveau")
META_PATH: Final[Path] = Path(config.DB_PATH) / "second_cerveau_meta.json"
NOM_TABLE: Final[str] = "second_cerveau"
TAILLE_CHUNK_MAX: Final[int] = 1200
TAILLE_LOT_EMBEDDING: Final[int] = 20


def _assurer_dossiers_vault() -> None:
    vault_dir = config.VAULT_DIR
    vault_dir.mkdir(parents=True, exist_ok=True)
    for sous_dir in ("01_Projets", "02_Journal", "03_Veille_Technologique", "04_Archives_Emails", "05_Maroquinerie_Puntillo", "06_Memoire_Vie"):
        (vault_dir / sous_dir).mkdir(parents=True, exist_ok=True)


def _trouver_fichiers_vault() -> list[Path]:
    _assurer_dossiers_vault()
    return [
        f for f in config.VAULT_DIR.rglob("*.md")
        if f.is_file() and not f.name.startswith(".") and f.stat().st_size > 0
    ]


def _decouper_en_passages(texte: str) -> list[str]:
    sections = re.split(r"\n(?=#{1,3}\s)", texte)
    passages: list[str] = []

    for section in sections:
        sec = section.strip()
        if not sec:
            continue
        if len(sec) <= TAILLE_CHUNK_MAX:
            passages.append(sec)
            continue

        courant = ""
        for para in sec.split("\n\n"):
            if courant and len(courant) + len(para) > TAILLE_CHUNK_MAX:
                passages.append(courant.strip())
                courant = ""
            courant += para + "\n\n"
        if courant.strip():
            passages.append(courant.strip())

    return passages or ([texte[:TAILLE_CHUNK_MAX]] if texte.strip() else [])


def _lire_meta() -> dict[str, Any] | None:
    if not META_PATH.exists():
        return None
    try:
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _synchroniser_second_cerveau_impl() -> str:
    import lancedb

    fichiers_md = _trouver_fichiers_vault()
    if not fichiers_md:
        return f"ℹ️ Aucune note Markdown dans le Vault ({config.VAULT_DIR})."

    meta_existant = _lire_meta() or {}
    fichiers_modifies_ts = meta_existant.get("mtimes", {})
    lignes_nouvelles: list[dict[str, Any]] = []
    nouveaux_mtimes: dict[str, float] = {}

    for f in fichiers_md:
        rel_path = str(f.relative_to(config.VAULT_DIR))
        mtime_actuel = f.stat().st_mtime
        nouveaux_mtimes[rel_path] = mtime_actuel

        try:
            contenu = f.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"Erreur lecture {f.name} : {e}")
            continue

        for i, passage in enumerate(_decouper_en_passages(contenu)):
            lignes_nouvelles.append({
                "id": f"{rel_path}::{i}",
                "chemin": rel_path,
                "chemin_absolu": str(f),
                "titre": f.stem,
                "passage_index": i,
                "texte": passage,
            })

    if not lignes_nouvelles:
        return "ℹ️ Aucun contenu indexable."

    textes = [l["texte"] for l in lignes_nouvelles]
    vecteurs: list[list[float]] = []
    moteur_utilise = "inconnu"

    try:
        for i in range(0, len(textes), TAILLE_LOT_EMBEDDING):
            lot = textes[i : i + TAILLE_LOT_EMBEDDING]
            vecs, mot = router.embed(lot)
            moteur_utilise = mot
            vecteurs.extend(vecs)
    except Exception as e:
        logger.error(f"Échec projection vectorielle : {e}")
        return f"⚠️ Échec génération vecteurs : {e}"

    for ligne, vecteur in zip(lignes_nouvelles, vecteurs):
        ligne["vector"] = vecteur

    dimension_vecteur = len(vecteurs[0]) if vecteurs else 0
    Path(config.DB_PATH).mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(config.DB_PATH)

    # Réécriture atomique du schéma avec gestion des dimensions
    db.create_table(NOM_TABLE, data=lignes_nouvelles, mode="overwrite")

    META_PATH.parent.mkdir(parents=True, exist_ok=True)
    META_PATH.write_text(
        json.dumps(
            {
                "moteur": moteur_utilise,
                "dimension": dimension_vecteur,
                "vault_dir": str(config.VAULT_DIR),
                "nb_notes": len(fichiers_md),
                "nb_passages": len(lignes_nouvelles),
                "date_sync": datetime.datetime.now().isoformat(),
                "mtimes": nouveaux_mtimes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return f"✅ Vault Obsidian synchronisé ({len(fichiers_md)} notes, {len(lignes_nouvelles)} passages via `{moteur_utilise}` [dim={dimension_vecteur}])."


@outil(tier=SecurityTier.AUTO)
def synchroniser_second_cerveau() -> str:
    """Reconstruit l'index vectoriel LanceDB pour le Vault Obsidian."""
    return _synchroniser_second_cerveau_impl()


@outil(tier=SecurityTier.AUTO)
def lister_arborescence_second_cerveau() -> str:
    """Liste toutes les notes du Vault Obsidian avec dates de modification."""
    fichiers = _trouver_fichiers_vault()
    if not fichiers:
        return f"Le Vault Obsidian est vide. Dossier : `{config.VAULT_DIR}`"

    lignes = [f"📚 **Notes du Vault Obsidian (`{config.VAULT_DIR}`) :**"]
    for f in sorted(fichiers, key=lambda x: x.stat().st_mtime, reverse=True):
        rel = f.relative_to(config.VAULT_DIR)
        date_mod = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        lignes.append(f"• `[[{f.stem}]]` ({date_mod}) ➔ `{rel}`")

    return "\n".join(lignes)


@outil(tier=SecurityTier.AUTO)
def ouvrir_note_dans_obsidian(nom_ou_chemin_note: str) -> str:
    """Ouvre une note dans Obsidian sur macOS."""
    fichiers = _trouver_fichiers_vault()
    cible_trouvee: Path | None = None
    nom_clean = nom_ou_chemin_note.strip().replace("[[", "").replace("]]", "").replace(".md", "")

    for f in fichiers:
        if f.stem.lower() == nom_clean.lower() or nom_clean.lower() in str(f).lower():
            cible_trouvee = f
            break

    if not cible_trouvee:
        return f"⚠️ Note « {nom_ou_chemin_note} » introuvable dans le Vault."

    encoded_path = urllib.parse.quote(str(cible_trouvee.resolve()))
    try:
        subprocess.run(["open", f"obsidian://open?path={encoded_path}"], check=True, timeout=5)
        return f"📖 Note ouverte dans Obsidian : `[[{cible_trouvee.stem}]]`"
    except Exception as e:
        return f"Erreur ouverture Obsidian : {e}"


def _recherche_textuelle_vault(requete: str, max_resultats: int = 4) -> list[dict[str, Any]]:
    fichiers = _trouver_fichiers_vault()
    mots = [m.lower() for m in requete.split() if len(m) > 2]
    resultats: list[dict[str, Any]] = []

    for f in fichiers:
        try:
            texte = f.read_text(encoding="utf-8", errors="replace")
            texte_lower = texte.lower()
            score = sum(1 for m in mots if m in texte_lower)
            if score > 0 or any(m in f.stem.lower() for m in mots):
                rel = str(f.relative_to(config.VAULT_DIR))
                resultats.append({
                    "titre": f.stem,
                    "chemin": rel,
                    "texte": texte[:900],
                    "score": score + (5 if any(m in f.stem.lower() for m in mots) else 0),
                })
        except Exception:
            continue

    resultats.sort(key=lambda x: x["score"], reverse=True)
    return resultats[:max_resultats]


@outil(tier=SecurityTier.AUTO)
def interroger_memoire_locale(requete: str, max_resultats: int = 4) -> str:
    """Recherche vectorielle (Priorité Gemini) avec repli textuel."""
    import lancedb

    meta = _lire_meta()
    if meta is None:
        _synchroniser_second_cerveau_impl()
        meta = _lire_meta()

    passages: list[dict[str, Any]] = []

    if meta is not None:
        try:
            db = lancedb.connect(config.DB_PATH)
            table = db.open_table(NOM_TABLE)
            vecteurs, _ = router.embed([requete])
            res = table.search(vecteurs[0]).limit(max_resultats).to_list()
            for r in res:
                passages.append({
                    "titre": r["titre"],
                    "chemin": r["chemin"],
                    "texte": r["texte"],
                })
        except Exception as e:
            logger.warning(f"Recherche vectorielle LanceDB en repli textuel ({e})")

    if not passages:
        passages = _recherche_textuelle_vault(requete, max_resultats)

    if not passages:
        arbo = lister_arborescence_second_cerveau()
        return f"ℹ️ Aucune occurrence trouvée dans le Vault Obsidian pour « {requete} ».\n\n{arbo}"

    rendu = [f"📓 **{len(passages)} note(s) extraite(s) pour « {requete} » :**\n"]
    for p in passages:
        rendu.append(f"### [[{p['titre']}]] (`{p['chemin']}`)\n{p['texte']}\n---")

    return "\n".join(rendu)
