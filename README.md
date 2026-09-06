# JARVIS v2

Base reconstruite à partir de `JARVIS_MARDI.zip` + du `main.py` fourni à part.
**Commence par `docs/SECURITY_INCIDENT.md`** — un jeton Telegram a fuité dans
l'ancien projet, à traiter avant de relancer quoi que ce soit.

## Lire dans cet ordre

1. `docs/SECURITY_INCIDENT.md` — urgent, 2 minutes.
2. `docs/AUDIT_JARVIS.md` — l'état des lieux complet de l'ancien projet,
   avec chaque bug reproduit et vérifié (pas juste supposé).
3. `docs/ARCHITECTURE.md` — comment la nouvelle base fonctionne, et pourquoi
   elle a été construite ainsi (répond notamment à la question posée sur le
   moteur de réflexion/action du `main.py` fourni).
4. `docs/MIGRATION.md` — ce qui est prêt, ce qui reste à relire, dans quel
   ordre.

## Démarrage rapide

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# remplir .env : au minimum GEMINI_API_KEY (ou un serveur local qui tourne
# sur LLAMA_API_BASE), et TELEGRAM_TOKEN + TELEGRAM_ALLOWED_USER_IDS si tu
# comptes utiliser le mode telegram.

python run_jarvis.py cli jarvis
```

Autres modes :

```bash
python run_jarvis.py herdr leo        # dans un pane Herdr (HERDR_ENV=1 injecté par Herdr)
python run_jarvis.py telegram          # bot Telegram (texte pour l'instant)
python live_dashboard.py               # vue live de tous les agents (traces/*.jsonl)
python eval_harness.py                 # tests de non-régression
```

## Structure

Voir `docs/ARCHITECTURE.md` pour le détail. En bref : `config.py` (source
unique), `core/` (le moteur), `tools/` (outils revus et réécrits),
`scripts/consolidation_nocturne.py` (bilan nocturne réparé), `run_jarvis.py`
(point d'entrée unique). Les dossiers `*_legacy/` contiennent le reste de
l'ancien projet, migré mécaniquement mais pas encore relu — voir
`docs/MIGRATION.md` avant d'en rebrancher un.

## Ce qui n'a pas été repris tel quel, et pourquoi

- **`smolagents`** a été retiré des dépendances : son décorateur `@tool`
  n'était en réalité jamais branché dans le flux réel de l'ancien projet
  (voir `docs/AUDIT_JARVIS.md` §2.4) — un seul système d'outils maintenant
  (`core/tools_registry.py`), utilisable avec le modèle local comme avec
  Gemini cloud.
- **Le "function calling automatique" du SDK Gemini** (utilisé pour la
  délégation Herdr) est remplacé par la boucle de décision explicite du
  `main.py` fourni, généralisée à tous les outils — voir
  `docs/ARCHITECTURE.md` pour la justification complète.
