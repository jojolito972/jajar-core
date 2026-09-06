from __future__ import annotations

"""
core/intent_classifier.py — Classifieur Dynamique d'Intention (Acoustique, Sémantique & Contextuelle).
Détecte instantanément si Denis engage une discussion personnelle ou ordonne une action technique.
"""

import logging
import re
from typing import Final, Literal

logger: Final[logging.Logger] = logging.getLogger("jajar.classifier")

TypeIntention = Literal["perso", "pro", "ambigu"]

# Verbes et motifs déclencheurs d'action technique obligatoire
MOTIFS_ACTION_PRO: Final[list[str]] = [
    r"\b(?:scan|scanne|analyse|nettoie|purge|supprime|efface)\b",
    r"\b(?:génère|cree|dessine|illustre|image|photo|visuel)\b",
    r"\b(?:script|code|python|terminal|shell|commande|bash)\b",
    r"\b(?:mail|email|gmail|rappel|note|agenda|obsidian|vault)\b",
    r"\b(?:disque|ram|cpu|processus|fichier|dossier|bac à sable)\b",
    r"\b(?:cuir|pointure|mesure|patron|instagram|bespoke)\b",
    r"\b(?:cherche sur le web|deep research|télécharge|url)\b",
]

# Motifs purement conversationnels / intimes
MOTIFS_DISCUSSION_PERSO: Final[list[str]] = [
    r"\b(?:tu penses quoi|qu'est-ce que tu en penses|ton avis)\b",
    r"\b(?:je me sens|je suis fatigué|je doute|raconte-moi)\b",
    r"\b(?:philosophie|vie|anecdote|histoire|blague|discutons)\b",
    r"\b(?:bonjour|salut|coucou|ça va|merci|bonne nuit)\b",
]


class IntentClassifier:
    """Arbitre contextuel temps-réel déterminant le routage des outils et la posture de l'agent."""

    @staticmethod
    def classifier_texte(prompt: str) -> TypeIntention:
        t = prompt.strip().lower()

        # 1. Vérification des déclencheurs d'action technique formelle
        for motif in MOTIFS_ACTION_PRO:
            if re.search(motif, t):
                return "pro"

        # 2. Vérification des motifs de conversation humaine / personnelle
        for motif in MOTIFS_DISCUSSION_PERSO:
            if re.search(motif, t):
                return "perso"

        # 3. Règle heuristique de longueur : les phrases courtes interrogatives sans verbe d'action sont perso
        mots = t.split()
        if len(mots) <= 8 and not any(k in t for k in ("fais", "lance", "trouve", "ouvre")):
            return "perso"

        return "pro"

    @staticmethod
    def classifier_audio_et_texte(transcription: str, langue: str = "fr") -> TypeIntention:
        """Affine la détection en combinant la langue détectée et le registre discursif."""
        intention = IntentClassifier.classifier_texte(transcription)
        logger.info(f"Classification intention vocale : « {transcription[:40]}... » ➔ [{intention.upper()}]")
        return intention


intent_classifier: Final[IntentClassifier] = IntentClassifier()
