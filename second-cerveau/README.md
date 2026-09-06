# Second Cerveau

Mémoire long terme de Jarvis. Six fichiers Markdown (compatibles Obsidian si
tu veux les éditer avec une autre app en parallèle) :

| Fichier | Contenu |
|---|---|
| `profil.md` | Qui tu es, ton parcours, ton style de travail, tes valeurs |
| `objectifs-2026.md` | Objectifs pro/perso, mis à jour chaque mois |
| `clients-prospects.md` | Fiche par client : contexte, historique, préférences |
| `charte-graphique.md` | Tes propres codes visuels + ceux de tes clients actifs |
| `journal-decisions.md` | Log daté des décisions stratégiques importantes (append-only) |
| `projets-creatifs.md` | Suivi des packs d'assets visuels et des collections patrimoniales (agents Ansel/Indiana) |

## Pourquoi ces fichiers et pas une base de données

Parce que tu dois pouvoir les relire et les corriger toi-même en 30
secondes, sans passer par une interface. Un fichier texte que tu relis
vraiment vaut mieux qu'une base de données parfaitement structurée que tu
ne relis jamais.

## Comment les agents l'utilisent

Contrairement à une version précédente pensée pour Open WebUI (glisser les
fichiers dans une base de connaissances web), ici la synchronisation se
fait directement dans la mémoire LanceDB que tous les agents interrogent
déjà via `interroger_base_locale_graphrag` — que tu parles à Jarvis en
voix, sur Telegram, ou en ligne de commande, c'est la même mémoire.

Après avoir modifié un fichier de ce dossier, deux façons de resynchroniser :

```bash
# Depuis la racine du projet, venv activé
python -m scripts.importer_second_cerveau
```

Ou directement en conversation, avec n'importe quel agent :

> « Resynchronise mon second cerveau. »

(ça déclenche l'outil `synchroniser_second_cerveau`, voir `jarvis_tools.py`)

La synchronisation est **idempotente** : la relancer après avoir modifié un
seul fichier remplace proprement les anciennes entrées de ce fichier dans
LanceDB plutôt que d'empiler des doublons au fil des mois.

## Le rituel du dimanche (15 minutes)

C'est ce qui fait que les agents te connaissent vraiment — pas la
sophistication technique de la mémoire.

1. **`objectifs-2026.md`** — coche/barre ce qui a bougé, ajoute une ligne
   dans « ce qui a changé ce mois-ci » si pertinent.
2. **`clients-prospects.md`** — vérifie qu'aucune fiche n'est en retard
   (relance oubliée, statut plus à jour).
3. **`journal-decisions.md`** — si une décision structurante a été prise
   cette semaine, ajoute une entrée (append-only, en haut du fichier).
4. Resynchronise (`python -m scripts.importer_second_cerveau`, ou demande-le
   à un agent).

## Confidentialité

Ce dossier contient des informations personnelles et potentiellement des
informations clients (noms, montants, contexte). Il reste **local**, sur
ton disque (`~/Assistant_IA/second-cerveau/`), comme le reste de la mémoire
de Jarvis. Rien de ce dossier n'est transmis à l'extérieur, à l'exception
de ce que les outils de recherche/escalade envoient déjà (DuckDuckGo pour
la recherche web, Gemini si un agent escalade explicitement une tâche).
Sauvegarde-le quand même régulièrement (copie manuelle, Time Machine, ou
dépôt Git privé).
