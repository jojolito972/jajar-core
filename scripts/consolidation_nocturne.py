"""
scripts/consolidation_nocturne.py — Bilan nocturne, débat automatique et journalisation Obsidian
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from core.llm_router import router
from tools.debat_agents import orchestrer_debat_studio
from tools.graph_memory import enregistrer_relation_graphe
from tools.second_cerveau import synchroniser_second_cerveau


def executer_consolidation():
    ts_jour = datetime.datetime.now().strftime("%Y-%m-%d")
    ts_complet = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"🌙 Lancement de la consolidation nocturne & Débat du Studio ({ts_jour})...")

    # 1. Lecture des traces d'activité
    log_audit = config.LOG_DIR / "commandes_executees.log"
    traces_log = ""
    if log_audit.exists():
        traces_log = "\n".join(log_audit.read_text(encoding="utf-8", errors="replace").splitlines()[-50:])

    # 2. Débat contradictoire nocturne sur les apprentissages
    sujet_debat_nocturne = f"Bilan des opérations et orientations stratégiques pour la journée du {ts_jour}"
    res_debat = orchestrer_debat_studio(sujet_debat_nocturne, agents_participants=["ray", "tesla", "cleo"])
    print("  🏛️ Débat nocturne entre Ray, Tesla et Cléo complété.")

    # 3. Synthèse et briefing du matin
    prompt_synthese = (
        f"Tu es l'Architecte de Synthèse du Studio JAJAR pour {config.UTILISATEUR}.\n"
        f"Date : {ts_jour}\n\n"
        f"ACTIVITÉS DU JOUR :\n{traces_log}\n\n"
        f"RÉSULTAT DU DÉBAT DES AGENTS :\n{res_debat[:3000]}\n\n"
        "TÂCHES :\n"
        "1. Rédige le briefing du matin (3 priorités concrètes).\n"
        "2. Extrais les règles apprises.\n"
        "Format JSON : {\"resume\": \"...\", \"regles_apprises\": [\"...\"], \"priorites_matin\": [{\"titre\": \"...\", \"description\": \"...\"}]}"
    )

    try:
        res_raw, _ = router.generer(prompt_synthese, "Génère le bilan.", temperature=0.1)
        res_clean = res_raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(res_clean)

        # 4. Écriture du Journal Quotidien au format Obsidian
        dossier_journal = config.VAULT_DIR / "02_Journal"
        dossier_journal.mkdir(parents=True, exist_ok=True)
        f_journal = dossier_journal / f"{ts_jour}.md"

        frontmatter = (
            f"---\n"
            f"title: \"Journal du {ts_jour}\"\n"
            f"date: {ts_complet}\n"
            f"tags: [\"journal\", \"quotidien\", \"bilan\"]\n"
            f"---\n\n"
        )

        corps_journal = (
            f"{frontmatter}# Journal Quotidien : {ts_jour}\n\n"
            f"## 📋 Briefing & Priorités\n{data.get('resume')}\n\n"
            f"### Priorités du Jour :\n"
        )
        for p in data.get("priorites_matin", []):
            corps_journal += f"- [ ] **{p.get('titre')}** : {p.get('description')}\n"

        corps_journal += f"\n## 🏛️ Débat Nocturne des Experts\n{res_debat}\n"

        f_journal.write_text(corps_journal, encoding="utf-8")
        print(f"  📝 Note quotidienne Obsidian créée : `[[{f_journal.stem}]]`")

        # Sauvegarde briefing_matin.json
        (config.BASE_DIR / "briefing_matin.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    except Exception as e:
        print(f"  ⚠️ Erreur synthèse nocturne : {e}")

    # 5. Synchronisation globale LanceDB
    synchroniser_second_cerveau()
    print("✨ Consolidation et débat nocturne terminés avec succès.")


if __name__ == "__main__":
    executer_consolidation()
