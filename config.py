from __future__ import annotations

"""
config.py — Configuration centrale du Studio JAJAR v2.
Filtrage racine des warnings Google GenAI et initialisation du client Gemini.
"""

import logging
import logging.handlers
import os
import re
import warnings
from enum import Enum
from pathlib import Path
from typing import Final

# 1. Neutralisation totale et immédiate des warnings du SDK Google GenAI
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*automatic function calling.*")
os.environ["PYTHONWARNINGS"] = "ignore"
logging.getLogger("google").setLevel(logging.ERROR)
logging.getLogger("google.genai").setLevel(logging.ERROR)

from dotenv import load_dotenv
from google import genai

BASE_DIR: Final[Path] = Path(__file__).resolve().parent

# Chargement du fichier .env
candidats_env = [
    BASE_DIR / ".env",
    BASE_DIR.parent / ".env",
    Path.cwd() / ".env",
    Path.home() / "Assistant_IA" / "jarvis" / ".env",
    Path.home() / "Assistant_IA" / ".env",
    Path.home() / ".env",
]

# Déduplication canonique des chemins pour éviter les parsings multiples
chemins_uniques = []
for p in candidats_env:
    if p.exists() and p.is_file():
        p_res = p.resolve()
        if p_res not in chemins_uniques:
            chemins_uniques.append(p_res)
            try:
                load_dotenv(p_res, override=False)
            except Exception:
                pass

UTILISATEUR: Final[str] = os.getenv("JARVIS_UTILISATEUR", "Denis")

# ---------------------------------------------------------------------------
# RÉPERTOIRES DU SYSTÈME
# ---------------------------------------------------------------------------
VAULT_DIR: Final[Path] = BASE_DIR / "second-cerveau"
PDF_DIR: Final[Path] = BASE_DIR / "pdf_bibliotheque"
BACKUP_DIR: Final[Path] = BASE_DIR / "backups_gdrive"
BACKUPS_FICHIERS_DIR: Final[Path] = BASE_DIR / "backups_fichiers"
SANDBOX_DIR: Final[Path] = BASE_DIR / "bac_a_sable"
IMAGE_DIR: Final[Path] = BASE_DIR / "images_generees"
AUDIO_DIR: Final[Path] = BASE_DIR / "audio_temp"
DEPOT_DIR: Final[Path] = BASE_DIR / "depot"
SKILLS_DIR: Final[Path] = BASE_DIR / "skills"
LOG_DIR: Final[Path] = BASE_DIR / "logs"
TRACE_DIR: Final[Path] = BASE_DIR / "traces"
LOG_FILE: Final[Path] = LOG_DIR / "jarvis.log"
AUDIT_LOG_FILE: Final[Path] = LOG_DIR / "commandes_executees.log"
DB_PATH: Final[Path] = BASE_DIR / "lancedb_store"
GRAPHE_DB_PATH: Final[Path] = BASE_DIR / "kuzu_store"
PUNTILLO_DIR: Final[Path] = VAULT_DIR / "05_Maroquinerie_Puntillo"

for d in (
    VAULT_DIR, PDF_DIR, BACKUP_DIR, BACKUPS_FICHIERS_DIR, SANDBOX_DIR,
    IMAGE_DIR, AUDIO_DIR, DEPOT_DIR, SKILLS_DIR, LOG_DIR, TRACE_DIR,
    DB_PATH, GRAPHE_DB_PATH, PUNTILLO_DIR
):
    d.mkdir(parents=True, exist_ok=True)


def _configurer_logger(nom: str, fichier: Path) -> logging.Logger:
    l = logging.getLogger(nom)
    if l.handlers:
        return l
    l.setLevel(logging.INFO)
    h = logging.handlers.RotatingFileHandler(fichier, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    l.addHandler(h)
    return l


logger: Final[logging.Logger] = _configurer_logger("jarvis", LOG_FILE)
audit_logger: Final[logging.Logger] = _configurer_logger("jarvis.audit", AUDIT_LOG_FILE)

# ---------------------------------------------------------------------------
# EXTRACTION DE LA CLÉ API GOOGLE
# ---------------------------------------------------------------------------
raw_key = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or os.getenv("GOOGLE_GENAI_API_KEY")
    or os.getenv("GEMINI_KEY")
    or ""
).strip().strip("'").strip('"')

if not raw_key or not raw_key.startswith("AIza"):
    for d in candidats_env:
        if d.exists() and d.is_file():
            try:
                texte = d.read_text(encoding="utf-8", errors="ignore")
                match_aiza = re.search(r'\b(AIza[0-9A-Za-z_-]{35})\b', texte)
                if match_aiza:
                    raw_key = match_aiza.group(1).strip()
                    break
            except Exception:
                pass

if not raw_key:
    raise RuntimeError("CRITICAL: Clé GEMINI_API_KEY introuvable dans votre fichier .env.")

GEMINI_API_KEY: Final[str] = raw_key
os.environ["GEMINI_API_KEY"] = raw_key
os.environ["GOOGLE_API_KEY"] = raw_key
GENAI_CLIENT: Final[genai.Client] = genai.Client(api_key=GEMINI_API_KEY)

# Clé Hugging Face (FLUX.1 HD)
raw_hf = (
    os.getenv("HUGGINGFACE_API_KEY")
    or os.getenv("HF_TOKEN")
    or os.getenv("HUGGING_FACE_HUB_TOKEN")
    or ""
).strip().strip("'").strip('"')

HUGGINGFACE_API_KEY: Final[str] = raw_hf
if raw_hf:
    os.environ["HUGGINGFACE_API_KEY"] = raw_hf
    os.environ["HF_TOKEN"] = raw_hf

MODELE_TEXTE_GEMINI: Final[str] = "gemini-3.6-flash"
MODELE_PRO_GEMINI: Final[str] = "gemini-2.5-pro"
MODELE_IMAGE_GEMINI: Final[str] = "gemini-2.5-flash-image"
MODELE_EMBEDDING_GEMINI: Final[str] = "text-embedding-004"

ZONE_SECURISEE: Final[Path] = Path.home()
TIMEOUT_COMMANDE: Final[int] = int(os.getenv("JARVIS_TIMEOUT_COMMANDE", "120"))


class SecurityTier(str, Enum):
    AUTO = "auto"
    CONFIRM = "confirm"
    NEVER_AUTO = "never_auto"


COMMANDES_INTERDITES: Final[list[str]] = [
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/\s*$",
    r"\bmkfs\b",
    r"\bdd\s+if=",
]

COMMANDES_INTERDITES_PATTERNS: Final[list[str]] = COMMANDES_INTERDITES

LLAMA_API_BASE: Final[str] = os.getenv("LLAMA_API_BASE", "http://localhost:8080/v1")
LLAMA_MODEL_ID: Final[str] = os.getenv("LLAMA_MODEL_ID", "gemma-4-12b-it")
MODELE_UTILISER_LOCAL_DABORD: Final[bool] = os.getenv("JARVIS_MODELE_LOCAL_DABORD", "0") == "1"

LLAMA_EMBEDDINGS_API_BASE: Final[str | None] = os.getenv("LLAMA_EMBEDDINGS_API_BASE")
LLAMA_EMBEDDINGS_MODEL_ID: Final[str] = os.getenv("LLAMA_EMBEDDINGS_MODEL_ID", "nomic-embed-text")
SEUIL_TOKENS_COMPRESSION: Final[int] = int(os.getenv("SEUIL_TOKENS_COMPRESSION", "250000"))

# Telegram
TELEGRAM_TOKEN: Final[str] = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
TELEGRAM_CHAT_ID: Final[str] = os.getenv("TELEGRAM_CHAT_ID", "776819401")
_raw_ids = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "") or ""
TELEGRAM_ALLOWED_USER_IDS: Final[set[int]] = {int(x.strip()) for x in _raw_ids.split(",") if x.strip().isdigit()}

HERDR_ENV: Final[bool] = os.environ.get("HERDR_ENV") == "1"
HERDR_PANE_ID: Final[str | None] = os.environ.get("HERDR_PANE_ID")

PERSONAS: Final[dict[str, dict]] = {
    "jarvis": {"nom": "JAJAR", "role": "Superviseur Suprême & Coordination Générale", "domaine": "Système macOS, arbitrage, sécurité et direction globale", "couleur": "bright_cyan", "peut_deleguer": True},
    "alfred": {"nom": "ALFRED", "role": "Assistant Exécutif & Administration", "domaine": "Google Suite, mails, agenda, rappels, tri administratif", "couleur": "bright_blue", "peut_deleguer": False},
    "ray": {"nom": "RAY", "role": "Recherche Profonde & Veille Autonome", "domaine": "Veille web, synthèses, recherche continue sur les projets actifs", "couleur": "bright_white", "peut_deleguer": False},
    "cleo": {"nom": "CLÉO", "role": "Stratégie Business & Rentabilité", "domaine": "Tarification, devis, Micro-BNC, modèles d'actifs et trésorerie", "couleur": "bright_yellow", "peut_deleguer": False},
    "leo": {"nom": "LEO", "role": "Direction Artistique & UI/UX", "domaine": "Design, typographies, chartes graphiques, médias", "couleur": "bright_magenta", "peut_deleguer": False},
    "franklin": {"nom": "FRANKLIN", "role": "Développement Commercial & Relations Clients", "domaine": "Prospection, suivi client, négociation, valorisation d'actifs", "couleur": "bright_green", "peut_deleguer": False},
    "tesla": {"nom": "TESLA", "role": "Ingénieur Systèmes, Réseaux & Open-Source", "domaine": "Scripts Python, outils CLI open-source, Tailscale, automatisation", "couleur": "bright_red", "peut_deleguer": False},
    "ansel": {"nom": "ANSEL", "role": "Fabrique Visuelle & Génération d'Images", "domaine": "Génération d'images haute fidélité FLUX.1, assets visuels, prompts artistiques", "couleur": "bright_magenta", "peut_deleguer": False},
    "indiana": {"nom": "INDIANA", "role": "Édition Patrimoine & Numérisation", "domaine": "OCR, indexation, archives, NotebookLM", "couleur": "bright_yellow", "peut_deleguer": False},
    "alba": {"nom": "ALBA", "role": "Maître Atelier Bespoke, Maroquinerie & Voix Italienne", "domaine": "Bottière d'art (Laura Puntillo), patronnage, peausseries, fiches clients, bilinguisme IT/FR", "couleur": "bright_green", "peut_deleguer": False},
}

AGENTS_DELEGABLES: Final[list[str]] = [k for k in PERSONAS if k != "jarvis"]
