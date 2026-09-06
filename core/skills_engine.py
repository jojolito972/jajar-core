"""
core/skills_engine.py — Moteur d'auto-apprentissage, persistance de skills et réinjection dynamique.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path
from typing import Any, Final

import config
from core.llm_router import router
from core.schemas import SkillDefinition

logger: Final[logging.Logger] = logging.getLogger("jarvis.skills")


class SkillsManager:
    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir: Path = skills_dir or config.SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills_cache: dict[str, SkillDefinition] = {}
        self.recharger_skills()

    def recharger_skills(self) -> None:
        self._skills_cache.clear()
        for f in self.skills_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                skill = SkillDefinition(**data)
                self._skills_cache[skill.id] = skill
            except Exception as e:
                logger.warning(f"Chargement skill '{f.name}' ignoré : {e}")

    def chercher_skills_pertinents(self, requete: str, limite: int = 3) -> list[SkillDefinition]:
        if not self._skills_cache:
            return []

        req_clean = requete.lower()
        scores: list[tuple[int, SkillDefinition]] = []

        for skill in self._skills_cache.values():
            score = 0
            for d in skill.declencheurs:
                if d.lower() in req_clean:
                    score += 3
            for m in skill.nom.split():
                if len(m) > 3 and m.lower() in req_clean:
                    score += 1

            if score > 0:
                scores.append((score, skill))

        scores.sort(key=lambda x: (x[0], x[1].succes_compteur), reverse=True)
        return [item[1] for item in scores[:limite]]

    def sauvegarder_skill(self, skill: SkillDefinition) -> None:
        fichier = self.skills_dir / f"{skill.id}.json"
        try:
            fichier.write_text(skill.model_dump_json(indent=2), encoding="utf-8")
            self._skills_cache[skill.id] = skill
            logger.info(f"✨ Compétence enregistrée : '{skill.nom}' ({skill.id})")
        except Exception as e:
            logger.error(f"Échec sauvegarde skill '{skill.id}': {e}")

    def incrementer_succes(self, skill_id: str) -> None:
        if skill_id in self._skills_cache:
            skill = self._skills_cache[skill_id]
            skill.succes_compteur += 1
            skill.derniere_utilisation = datetime.datetime.now().isoformat()
            self.sauvegarder_skill(skill)

    def distiller_et_apprendre(self, tache: str, historique_actions: list[dict[str, Any]]) -> None:
        if len(historique_actions) < 1:
            return

        trace_brute = json.dumps(historique_actions, ensure_ascii=False)
        prompt_systeme = (
            "Tu es l'Architecte Métacognitif de JAJAR.\n"
            "Une tâche opérationnelle a été résolue avec succès via une suite d'outils.\n"
            "Extrais une compétence réutilisable (Skill).\n"
            "Format JSON strict :\n"
            "{\n"
            '  "id": "slug_unique_action",\n'
            '  "nom": "Titre explicite",\n'
            '  "declencheurs": ["mot_cle_1", "expression 2"],\n'
            '  "description": "Objectif de la procédure",\n'
            '  "recette_etapes": ["Étape 1: ...", "Étape 2: ..."],\n'
            '  "conditions_succes": "Critère de succès validé"\n'
            "}"
        )

        try:
            reponse, _ = router.generer(
                system_prompt=prompt_systeme,
                user_prompt=f"Tâche : {tache}\nTrace d'actions :\n{trace_brute}",
                temperature=0.1,
            )
            texte_clean = re.sub(r"^```(?:json)?", "", reponse.strip()).removesuffix("```").strip()
            data = json.loads(texte_clean)

            maintenant = datetime.datetime.now().isoformat()
            slug_id = re.sub(r"[^\w-]", "_", data.get("id", "skill_procedural").lower())

            if slug_id in self._skills_cache:
                self.incrementer_succes(slug_id)
                return

            nouveau_skill = SkillDefinition(
                id=slug_id,
                nom=data.get("nom", "Procédure"),
                declencheurs=data.get("declencheurs", [tache[:30]]),
                description=data.get("description", "Résolution"),
                recette_etapes=data.get("recette_etapes", []),
                conditions_succes=data.get("conditions_succes", "Succès"),
                date_creation=maintenant,
                derniere_utilisation=maintenant,
                succes_compteur=1,
            )
            self.sauvegarder_skill(nouveau_skill)
        except Exception as e:
            logger.warning(f"Distillation de compétence ignorée : {e}")


skill_registry: Final[SkillsManager] = SkillsManager()
