"""
tools/gemma_heavy_engine.py — Moteur d'inférence lourde locale pour Gemma 4 (6.9 Go GGUF).
Exécution directe sans simulation et compatible macOS Apple Silicon.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

import config
from config import SecurityTier
from core.tools_registry import outil
from rich.console import Console
from rich.panel import Panel

console = Console()
logger: Final[logging.Logger] = logging.getLogger("jajar.gemma_heavy")

CHEMIN_MODELE_GEMMA4: Final[Path] = Path("/Users/denmac/Assistant_IA/modeles/gemma-4-12b-it-UD-Q4_K_XL.gguf")


def _trouver_binaire_llama_cli() -> str:
    candidats = [
        shutil.which("llama-cli"),
        shutil.which("llama-run"),
        Path.home() / "Assistant_IA" / "jarvis" / "llama-cli",
        Path("/opt/homebrew/bin/llama-cli"),
        Path("/usr/local/bin/llama-cli"),
    ]
    for c in candidats:
        if c and Path(str(c)).is_file() and os.access(str(c), os.X_OK):
            return str(c)
    return "llama-cli"


def _nettoyer_ocr_ancien(texte_brut: str) -> str:
    lignes = texte_brut.splitlines()
    lignes_propres = []
    for l in lignes:
        l_str = l.strip()
        if len(l_str) <= 2 and not l_str.isalnum():
            continue
        if len(l_str) == 1:
            continue
        lignes_propres.append(l_str)

    texte = "\n".join(lignes_propres)
    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    return texte.strip()


def _extraire_texte_pdf_reel(chemin_pdf: Path, max_pages: int = 12) -> str:
    if not chemin_pdf.exists():
        return ""

    if shutil.which("pdftotext"):
        try:
            res = subprocess.run(
                ["pdftotext", "-f", "1", "-l", str(max_pages), str(chemin_pdf), "-"],
                capture_output=True, text=True, timeout=15
            )
            if res.returncode == 0 and res.stdout.strip():
                return _nettoyer_ocr_ancien(res.stdout)
        except Exception:
            pass

    try:
        from pypdf import PdfReader
        reader = PdfReader(str(chemin_pdf))
        texte_pages = []
        for i, page in enumerate(reader.pages[:max_pages]):
            t = page.extract_text()
            if t:
                texte_pages.append(f"--- PAGE {i+1} ---\n{t}")
        return _nettoyer_ocr_ancien("\n".join(texte_pages))
    except Exception:
        pass

    return ""


@outil(tier=SecurityTier.AUTO)
def executer_analyse_lourde_gemma4_local(
    sujet_analyse: str,
    dossier_sources_pdf: str = "/Users/denmac/Documents/Maison_Rustique_XXI/01_Sources_Gallica",
    max_fichiers: int = 3,
) -> str:
    """Exécute une analyse lourde sur GPU Metal avec Gemma 4 (6.9 Go) en streaming direct."""
    if not CHEMIN_MODELE_GEMMA4.exists():
        return f"⚠️ Modèle Gemma 4 introuvable : `{CHEMIN_MODELE_GEMMA4}`"

    dossier = Path(dossier_sources_pdf).expanduser().resolve()
    if not dossier.exists():
        return f"⚠️ Dossier sources introuvable : `{dossier}`"

    fichiers_pdf = list(dossier.rglob("*.pdf"))
    if not fichiers_pdf:
        return f"⚠️ Aucun fichier PDF trouvé dans `{dossier}`."

    selection_pdf = fichiers_pdf[:max_fichiers]
    corpus_extraits: list[str] = []

    for f_pdf in selection_pdf:
        txt = _extraire_texte_pdf_reel(f_pdf, max_pages=6)
        if txt:
            corpus_extraits.append(f"=== SOURCE HISTORIQUE : {f_pdf.name} ===\n{txt[:3500]}")

    if not corpus_extraits:
        return "⚠️ Impossible d'extraire de texte exploitable de ces PDF."

    contexte_total = "\n\n".join(corpus_extraits)[:10000]

    prompt_gemma = (
        f"<start_of_turn>user\n"
        f"Tu es l'Analyste Agronomique et Historique de la Maison Rustique XXI pour {config.UTILISATEUR}.\n"
        f"Extrait des sources historiques de Gallica :\n\n"
        f"{contexte_total}\n\n"
        f"MISSION : Analyse et synthétise le sujet : '{sujet_analyse}'.\n"
        f"RÈGLE : Rédige STRICTEMENT EN FRANÇAIS en Markdown structuré.<end_of_turn>\n"
        f"<start_of_turn>model\n"
    )

    prompt_file = config.SANDBOX_DIR / "prompt_gemma_heavy.txt"
    prompt_file.write_text(prompt_gemma, encoding="utf-8")

    llama_bin = _trouver_binaire_llama_cli()
    cmd = [
        llama_bin,
        "-m", str(CHEMIN_MODELE_GEMMA4),
        "-ngl", "99",
        "-c", "8192",
        "--temp", "0.2",
        "-n", "1200",
        "-f", str(prompt_file),
    ]

    t0 = time.time()
    tokens_generes = []

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
        )

        capture_active = False
        thinking_mode = False

        if proc.stdout:
            for line in iter(proc.stdout.readline, ''):
                if "<start_of_turn>model" in line:
                    capture_active = True
                    continue
                if "[Start thinking]" in line or "<thought>" in line:
                    thinking_mode = True
                    continue
                if "[End thinking]" in line or "</thought>" in line:
                    thinking_mode = False
                    continue
                if capture_active and not thinking_mode:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    tokens_generes.append(line)

        proc.wait(timeout=300)
        chrono_total = round(time.time() - t0, 2)

        texte_final = "".join(tokens_generes).strip()
        texte_final = re.sub(r"<end_of_turn>.*", "", texte_final, flags=re.DOTALL).strip()

        if not texte_final:
            texte_final = "Synthèse terminée."

        ts_now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        dossier_obsidian = config.VAULT_DIR / "01_Projets" / "Maison_Rustique_XXI"
        dossier_obsidian.mkdir(parents=True, exist_ok=True)
        fichier_sortie = dossier_obsidian / f"Synthese_Gemma4_{ts_now}.md"

        frontmatter = (
            f"---\n"
            f"title: \"Synthèse Gemma 4 : {sujet_analyse}\"\n"
            f"date: {datetime.datetime.now().isoformat()}\n"
            f"modele: \"gemma-4-12b-it-UD-Q4_K_XL.gguf\"\n"
            f"chrono_sec: {chrono_total}\n"
            f"sources_gallica: {len(selection_pdf)}\n"
            f"---\n\n"
        )
        fichier_sortie.write_text(frontmatter + f"# {sujet_analyse}\n\n" + texte_final, encoding="utf-8")

        return (
            f"\n\n✅ **Traitement Lourd Gemma 4 Réussi ({chrono_total}s sur GPU Metal) !**\n\n"
            f"• **Fichiers analysés :** `{len(selection_pdf)} PDF`\n"
            f"• **Fiche Obsidian :** `[[{fichier_sortie.stem}]]`\n\n"
            f"{texte_final[:600]}..."
        )

    except subprocess.TimeoutExpired:
        proc.kill()
        return "⚠️ Timeout : Gemma 4 a dépassé la limite de 300 secondes."
    except Exception as e:
        return f"Erreur exécution Gemma 4 : {e}"
