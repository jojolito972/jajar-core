# Architecture — la nouvelle base JARVIS

## Ce que je pense du moteur de réflexion/action du `main.py` fourni

Directement, puisque c'était la question : c'est un bon choix, et je l'ai
généralisé à tout le projet plutôt que de le garder pour un seul
orchestrateur générique. Trois raisons concrètes :

1. **Le JSON validé par Pydantic + retry avec réparation** force le modèle à
   séparer explicitement "je réfléchis" de "je décide", et échoue vite et
   clairement quand la sortie est incohérente plutôt que de planter plus loin
   dans le code sans explication. C'est exactement le genre de rigueur qui
   manquait à `jarvis_main.py` : celui-ci extrayait des blocs de commande
   shell depuis du texte libre par regex (`extraire_commandes_shell`), ce qui
   marche tant que le modèle formate bien ses blocs ```bash — et échoue
   silencieusement sinon.
2. **La Reflexion explicite sur échec d'outil** (le tour suivant reçoit une
   instruction de diagnostic, pas juste l'erreur brute) existait déjà dans
   `jarvis_main.py` sous une forme proche — je l'ai gardée et généralisée à
   tous les outils, pas seulement aux commandes shell.
3. **Le plus important pour ce projet en particulier :** ce mécanisme ne
   dépend d'aucun SDK propriétaire. `jarvis_main.py` utilisait le "function
   calling automatique" du SDK Gemini pour la délégation Herdr — une
   fonctionnalité propre à Gemini, qui n'aurait pas fonctionné avec le modèle
   local. Comme corriger le fait que le modèle local n'était jamais appelé
   (voir `docs/AUDIT_JARVIS.md` §2.5) faisait partie du travail, il fallait un
   mécanisme de décision/outils qui marche identiquement quel que soit le
   modèle interrogé — c'est ce que fait la boucle explicite du `main.py`
   fourni, et pas l'AFC.

Ce que je n'ai PAS gardé tel quel du `main.py` fourni : c'était un squelette
générique, sans notion de persona ni d'outils métier. La fusion consiste à
brancher ce moteur sur les 9 personas, la délégation Herdr, le Second
Cerveau et les paliers de sécurité de JARVIS — pas à le copier à côté.

## Vue d'ensemble

```
jarvis2/
├── config.py                  Source unique : chemins, secrets, personas, paliers de sécurité
├── run_jarvis.py               Point d'entrée unique (cli / herdr / telegram)
├── core/
│   ├── schemas.py               Decision (Pydantic) — repris du main.py fourni
│   ├── state.py                 AgentState + monitoring de fenêtre de contexte
│   ├── llm_router.py            Modèle local d'abord, Gemini cloud en escalade (chat ET embeddings)
│   ├── tools_registry.py        Registre central des outils, paliers de sécurité
│   ├── engine.py                 La boucle Reason -> Act -> Observe (fusion des deux main.py)
│   └── tracing.py                Traçage JSONL par agent (repris de agent_trace.py)
├── tools/
│   ├── herdr_bridge.py           Délégation inter-agents (repris, déjà solide)
│   ├── system_tools.py           Shell (CONFIRM), AppleScript (CONFIRM), image, suppression sécurisée
│   ├── network_tool.py           SSH/VNC/SMB (injection shell corrigée, confirmation obligatoire)
│   ├── second_cerveau.py         Sync + recherche SÉMANTIQUE (embeddings/lancedb, pas mots-clés)
│   ├── notebooklm_tool.py        CLI notebooklm-py (bug heredoc corrigé, paliers alignés sur le runbook)
│   └── web_tool.py               Recherche web, lecture de page, téléchargement (jamais branché avant)
├── scripts/
│   └── consolidation_nocturne.py Bilan du jour + apprentissage + réindexation sémantique nocturne
├── second-cerveau/                Ton contenu réel (journal, objectifs, clients...), secrets rédigés
├── eval_harness.py                Tests de non-régression, adapté au moteur multi-personas
├── live_dashboard.py              Vue live des traces (ex-dashboard.py, renommé pour éviter la collision)
├── .env.example / .gitignore      Aucun secret en dur, plus de fichiers indésirables committés
└── docs/
    ├── AUDIT_JARVIS.md            L'audit complet
    ├── SECURITY_INCIDENT.md       Ce qu'il faut faire en premier
    ├── TUTORIEL_INSTALLATION.md   Installation pas à pas
    ├── ARCHITECTURE.md            Ce fichier
    └── MIGRATION.md               Ce qui reste à porter depuis l'ancien projet, et comment
```

## Le harness — la vraie source de puissance, pas seulement le modèle

C'est le principe demandé explicitement par {utilisateur} : un modèle même
petit (local, 12B) devient beaucoup plus capable avec une bonne architecture
de pensée autour de lui, plutôt qu'avec un modèle plus gros mais une boucle
naïve. Trois mécanismes dans `core/engine.py`, chacun réservé aux situations
qui en ont besoin (pas de surcoût sur les tâches simples — testé) :

**Plan persistant.** Le même principe que la todo-list de Claude Code : sur
une tâche à plusieurs étapes, le modèle pose un plan au premier tour
(`"plan": [{"id":1,"description":"...","statut":"a_faire"}, ...]`), montré en
ENTIER à chaque tour suivant — jamais compressé, contrairement à
l'historique de conversation. Un agent qui revoit son plan à chaque tour ne
perd pas le fil sur une tâche longue ; un agent qui n'a qu'un raisonnement
jetable par tour, si.

**Approfondissement adaptatif.** Une réponse à confiance "basse" n'est pas
rendue telle quelle : le harness demande explicitement au modèle de
reprendre le problème sous un angle différent, jusqu'à 2 fois par tâche.
Plus de réflexion pour les questions qui la méritent, une seule passe pour
celles qui n'en ont pas besoin.

**Vérification indépendante.** Avant de rendre une réponse qui a mobilisé un
outil (donc consequente) ou dont la confiance n'est pas franche, un appel
modèle SÉPARÉ — contexte neuf, consigne délibérément critique — vérifie
qu'elle répond vraiment à la tâche d'origine. Plus fiable qu'une
auto-critique dans le même souffle que la génération : le modèle qui vient
de produire une réponse a un biais naturel à la trouver correcte, un regard
neuf en trouve davantage. Plafonné à 2 par tâche.

## Comment une décision est prise, maintenant

Avant (`jarvis_main.py`) : le texte de la requête était comparé à des listes
de mots-clés français (`traiter_outils_reels`, `est_demande_complexe`) pour
décider si c'était une question mail, une recherche web, une délégation, une
tâche "complexe" nécessitant la boucle autonome... Fragile aux
reformulations, et un chemin de décision différent selon le persona actif.

Maintenant : **chaque persona suit exactement la même boucle**, définie une
seule fois dans `core/engine.py` :

1. `core.state.AgentState` vérifie l'utilisation de la fenêtre de contexte et
   se compresse si besoin (voir plus bas).
2. `core.engine.obtenir_decision()` interroge le modèle (local d'abord, cloud
   en secours) et valide sa réponse contre `core.schemas.Decision`, avec
   retry + réparation si le JSON est malformé.
3. Si `tool_call` : `core.tools_registry.executer_outil()` applique le palier
   de sécurité de l'outil demandé (exécution directe / confirmation requise /
   jamais automatique), l'exécute, et en cas d'échec injecte une instruction
   de reflexion explicite pour le tour suivant.
4. Si `ask_clarification` : la tâche s'arrête net plutôt que de deviner.
5. Si `final_answer` : la confiance et l'auto-critique sont journalisées, la
   réponse est retournée.

Chaque étape est tracée dans `traces/<persona>.jsonl`, visible en direct dans
`live_dashboard.py` — exactement le même format qu'avant, donc le dashboard
fourni fonctionne sans modification une fois pointé sur `config.TRACE_DIR`.

## Modèle local vs cloud — enfin réellement branché

`core/llm_router.py` essaie d'abord le serveur local (`LLAMA_API_BASE`, API
compatible OpenAI) et n'escalade vers Gemini cloud qu'en cas d'échec (serveur
éteint, erreur, réponse vide) — ou immédiatement si
`JARVIS_MODELE_LOCAL_DABORD=0`. C'est le comportement que le README de
l'ancien projet décrivait déjà en détail, mais qui n'était jamais câblé dans
le code réel (voir `docs/AUDIT_JARVIS.md` §2.5). Le choix entre "tout local"
et "tout cloud" reste une décision produit (coût, latence, confidentialité) —
elle se prend maintenant dans `.env`, explicitement, plutôt que d'être
tranchée implicitement par un import qui n'a jamais existé.

## Paliers de sécurité — la même logique partout, pas juste pour le shell

`config.SecurityTier` (`AUTO` / `CONFIRM` / `NEVER_AUTO`) reprend et
généralise la matrice "safe to run automatically / ask before running" déjà
définie dans `notebooklm-py-agent-runbook.md` — au lieu de la réserver à
NotebookLM, elle s'applique à tous les outils enregistrés dans
`core/tools_registry.py` : shell local, AppleScript, SSH/VNC vers une
machine distante, suppression de carnet NotebookLM, génération d'artefact
longue durée, etc. sont tous en `CONFIRM` — la lecture web
(`tools/web_tool.py`), la recherche dans le Second Cerveau et la suppression
de fichier (réversible, direction `~/Desktop/Supprimer/`) restent en `AUTO`,
sans friction inutile. En mode CLI et Herdr, la confirmation passe par une
question directe dans le terminal ; en mode Telegram, un clavier inline
✅/❌ avec un délai de 120s (voir `run_jarvis.py::mode_telegram`).

Le shell local et l'AppleScript sont volontairement séparés du reste : ce
sont les deux seuls outils réellement à portée ouverte (n'importe quelle
commande, n'importe quel script). `config.COMMANDES_INTERDITES` ajoute une
protection en profondeur sur ces deux-là spécifiquement : dossiers système
macOS protégés (`/System`, `/Library` racine — pas `~/Library`, qui reste
libre), `sudo` bloqué, et toute suppression forcée à passer par l'outil
dédié plutôt que par un `rm` direct qui contournerait le dossier
`~/Desktop/Supprimer/`.

## Ce qui n'a pas changé de philosophie

Les principes qui marchaient déjà bien dans `jarvis_main.py` n'ont pas été
réinventés, seulement re-câblés sur la nouvelle boucle : les 9 personas avec
leur domaine propre, la délégation Herdr réservée à JARVIS (pour éviter les
cascades de délégation), le Second Cerveau en Markdown simple plutôt qu'une
base de données, et le réflexe de rediriger les suppressions vers un dossier
récupérable plutôt que de supprimer pour de vrai.

## Quatre ajouts ultérieurs (après le harness plan/approfondissement/vérification ci-dessus)

**Rigueur factuelle encodée par Pydantic, pas par consigne** (RAY/CLÉO/INDIANA
uniquement — `config.PERSONAS_VERIFICATION_RENFORCEE`) : `Decision` porte
`statut_epistemique`/`sources`/`contradiction_memoire`/`meilleur_contre_argument`
(`core/schemas.py`). Une réponse "fait_verifie" sans ≥2 sources, ou
"confidence: haute" sans contre-argument réel, est rejetée par
`validate_coherence()` et redéclenche le retry existant — pas une nouvelle
boucle, le mécanisme de retry servait déjà à ça. Interrupteur
`config.EXIGENCE_SOURCES_STRICTE` si le modèle local sature sous la contrainte.

**Gravité des traces déclarée, jamais devinée** (`core/engine.py`,
`core/state.py`) : chaque `tracer.log()` porte explicitement
`status="error"` (arrêt réel de la tâche) ou `status="warning"` (accroc que
l'agent gère tout seul — échec d'outil transitoire, plafond de délégations,
vérification indépendante rejetée, alerte de fenêtre de contexte). Avant ce
correctif, `live_dashboard.py` devinait la gravité en lisant le texte du
message — l'alerte de contexte utilisait le même "⚠️" que le plafond de
délégations et se faisait classer pareil, à tort (agent affiché "en
attention" alors qu'il travaillait normalement).

**Bascule automatique entre modèles Gemini** (`core/llm_router.py`) :
`config.MODELE_TEXTE_GEMINI` fige un nom dans le code, et Google retire des
modèles sans préavis (vécu en direct : `gemini-2.0-flash` a répondu 404 un
jour donné). Au premier appel cloud, le router interroge l'API elle-même
(`client.models.list()`) pour savoir ce qui existe VRAIMENT, essaie le
modèle configuré, et bascule sur un autre modèle valide s'il échoue —
principe reprise de `jarvis_main.py::appel_genai_robuste`, en découverte
paresseuse (seulement si un appel cloud a vraiment lieu) plutôt qu'au
démarrage.

**`live_dashboard.py` réécrit** : un onglet par persona, une pastille
d'activité par agent qui bat visuellement pendant qu'il travaille (bande de
vue d'ensemble en haut, cliquable), palette pastel sur fond sombre, timestamp
+ temps d'exécution réel entre étapes (`ts_epoch` dans `core/tracing.py`),
flux non tronqué. La classification d'état (au repos / en cours / attention
/ terminé) lit uniquement le champ `status` des traces, jamais le texte —
voir le point sur la gravité des traces ci-dessus.

**`tools/herdr_bridge.py::assurer_presence`** : cette fonction était
appelée par `run_jarvis.py::mode_herdr` mais n'avait jamais été écrite (seule
sa mention dans `docs/TUTORIEL_INSTALLATION.md` avait survécu). Elle
réutilise `report_state()`, le seul mécanisme Herdr déjà éprouvé dans ce
fichier — si Herdr expose une vraie commande d'inscription séparée, ce
choix reste à corriger avec la référence exacte (`herdr pane --help`).

