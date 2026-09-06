"""
core/schemas.py — Modèles Pydantic v2 pour la décision, les preuves factuelles et la dialectique.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class FaitVerifie(BaseModel):
    affirmation: str = Field(..., description="Énoncé factuel concis.")
    statut: Literal["verifie", "hypothese", "inverifiable"] = Field(
        default="hypothese",
        description="Niveau de validation épistémique."
    )
    source: Optional[str] = Field(
        default=None,
        description="Identifiant de la preuve : 'fichier:<chemin>', 'commande:<cmd>', etc."
    )
    preuve_brute: Optional[str] = Field(
        default=None,
        description="Donnée brute ou retour de commande attestant l'affirmation."
    )


class PenseeDialectique(BaseModel):
    these: str = Field(..., description="Hypothèse de travail ou solution primaire.")
    antithese: str = Field(..., description="Objections sceptiques, risques et limites identifiées.")
    synthese: str = Field(..., description="Résolution arbitrée intégrant les contre-mesures.")
    doutes: list[str] = Field(default_factory=list, description="Incertitudes explicitement formulées.")
    faits_evalues: list[FaitVerifie] = Field(default_factory=list, description="Liste des faits analysés.")
    niveau_certitude: Literal["preuve", "forte_presomption", "hypothese", "doute_majeur"] = "hypothese"


class SolutionConcrete(BaseModel):
    id: str = Field(..., description="Identifiant unique de la solution ('A', 'B', 'C'...).")
    titre: str = Field(..., min_length=3, description="Titre de la solution.")
    approche: str = Field(..., min_length=5, description="Description opérationnelle.")
    impact: str = Field(default="", description="Résultat ou gain attendu.")
    type_alignement: Literal["technique", "organisationnelle", "automatisation", "business", "rupture"] = "technique"


StrategicOption = SolutionConcrete


class Decision(BaseModel):
    thinking: str = Field(default="", description="Raisonnement interne du modèle.")
    est_dilemme_ou_idee: bool = Field(default=False, description="Indicateur d'arbitrage stratégique.")
    solutions: list[SolutionConcrete] = Field(default_factory=list, description="Solutions alternatives proposées.")
    synergie_recommandee: Optional[str] = Field(default=None, description="Combinaison synergique optimale.")
    action: Literal["tool_call", "final_answer", "ask_clarification"] = "final_answer"
    tool_name: Optional[str] = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    answer: Optional[str] = None
    confidence: Literal["haute", "moyenne", "basse"] = "haute"
    faits: list[FaitVerifie] = Field(default_factory=list, description="Faits extraits et sourcés.")
    doute_exprime: Optional[str] = Field(default=None, description="Incertitude explicitée.")
    dialectique: Optional[PenseeDialectique] = Field(default=None, description="Analyse dialectique structurée.")
    interdiction_mensonge: bool = Field(default=True, description="Interdiction d'affirmer sans source validée.")

    def validate_coherence(self) -> None:
        if self.tool_args is None:
            self.tool_args = {}

        if self.action == "tool_call" and not self.tool_name:
            self.action = "final_answer"
            self.answer = self.thinking or "Action en cours de traitement."

        if self.interdiction_mensonge and self.action == "final_answer":
            non_verifies = [f for f in self.faits if f.statut == "hypothese" and not f.source]
            if non_verifies and not self.doute_exprime and len(non_verifies) > 2:
                points_str = " ; ".join(f.affirmation for f in non_verifies[:2])
                self.doute_exprime = f"Hypothèses non vérifiées physiquement : {points_str}"

        if not self.answer:
            self.answer = self.thinking or "Opération finalisée."


class SkillDefinition(BaseModel):
    id: str = Field(..., description="Identifiant unique du skill.")
    nom: str = Field(..., description="Nom de la procédure.")
    declencheurs: list[str] = Field(..., min_length=1, description="Mots-clés déclencheurs.")
    description: str = Field(..., description="Objectif de la procédure.")
    recette_etapes: list[str] = Field(..., description="Étapes ordonnées de l'exécution.")
    conditions_succes: str = Field(..., description="Indicateurs de complétion.")
    date_creation: str = Field(..., description="Horodatage ISO de création.")
    derniere_utilisation: str = Field(..., description="Horodatage ISO du dernier usage.")
    succes_compteur: int = Field(default=1, ge=1)
