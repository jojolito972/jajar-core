# Tutoriel — installer et lancer la nouvelle base JARVIS

Ce tutoriel part du principe que tu viens de télécharger `JARVIS_v2.zip` et
`AUDIT_JARVIS.md`. Il reprend en détail les 3 étapes déjà données, dans
l'ordre où les faire, avec ce qui peut coincer à chaque étape.

---

## En bref : ce qui a été fait avant ce tutoriel

- **Audit complet** de `JARVIS_MARDI.zip` : chaque bug listé a été reproduit
  réellement (import, exécution), pas juste repéré à la lecture. Le plus
  grave : un jeton Telegram exposé en clair dans 15 fichiers. Le plus
  structurant : le modèle local (Gemma via llama.cpp) documenté dans
  l'ancien README n'était en réalité jamais appelé, tout partait sur Gemini
  cloud. Détail complet : `AUDIT_JARVIS.md`.
- **Fusion des deux `main.py`** : le moteur de décision structuré (JSON
  validé, retry, reflexion sur échec) du fichier fourni à part remplace le
  routage par mots-clés de l'ancien `jarvis_main.py`, pour les 9 personas.
  Pourquoi ce choix : `jarvis2/docs/ARCHITECTURE.md`.
- **4 fichiers cassés réparés** (Second Cerveau, consolidation nocturne,
  NotebookLM, pipeline KDP), **le modèle local réellement branché** (avec
  bascule automatique vers le cloud s'il est indisponible), **tous les
  secrets en dur retirés**, **un point d'entrée unique** (`run_jarvis.py`)
  à la place des scripts épars et divergents de l'ancien projet.
- **~40 fichiers restants** (mail, Kokoro, réseau, calendrier...) migrés
  mécaniquement (bug heredoc corrigé, secrets rédigés) dans des dossiers
  `*_legacy/`, pas encore relus un par un — priorités dans
  `jarvis2/docs/MIGRATION.md`.
- **Ajouté après un premier passage, sur retour direct de {utilisateur}** :
  un vrai outil pour aller sur le web (recherche, lecture de page,
  téléchargement — `tools/web_tool.py`, absent avant), une recherche
  **sémantique** réelle dans le Second Cerveau (embeddings, plus seulement
  des mots-clés), une protection système renforcée (dossiers macOS
  protégés, `sudo` bloqué, toute suppression forcée à passer par
  `~/Desktop/Supprimer/`), et la confirmation par bouton qui fonctionne
  vraiment en mode Telegram (avant : refusée automatiquement).

Tout ce qui suit t'amène à un premier lancement fonctionnel, puis à la suite
à faire progressivement.

---

## Avant de commencer

- macOS, avec Python 3.10 ou plus (`python3 --version` pour vérifier — si
  c'est en dessous, `brew install python@3.12`).
- Un compte Google pour obtenir une clé Gemini (gratuite).
- Optionnel pour la suite, pas pour le premier lancement : Herdr installé
  (si tu utilises le mode multi-panes), un compte Telegram, le CLI
  `notebooklm-py`.

---

## Étape 0 — Révoquer le jeton Telegram compromis (avant toute autre chose)

Même si tu ne comptes pas relancer le bot tout de suite, fais ça maintenant
— ça prend 10 secondes et ça neutralise la fuite immédiatement, y compris
dans l'historique Git si le dossier a déjà été poussé quelque part :

1. Ouvre Telegram, cherche **@BotFather**, démarre une conversation si ce
   n'est pas déjà fait.
2. Envoie `/mybots`.
3. Sélectionne **Bilbokeybot** dans la liste.
4. Tape **API Token**.
5. Tape **Revoke current token**. BotFather te donne immédiatement un
   nouveau jeton — garde-le de côté, tu en auras besoin à l'étape 4.

L'ancien jeton meurt à l'instant où tu fais ça, où qu'il traîne encore.
Détail complet si besoin : `jarvis2/docs/SECURITY_INCIDENT.md`.

---

## Étape 1 — Récupérer le nouveau projet

Dézippe `JARVIS_v2.zip` là où tu veux garder le projet, par exemple :

```bash
cd ~/Assistant_IA   # ou l'endroit de ton choix
unzip ~/Downloads/JARVIS_v2.zip
cd jarvis2
```

Tu devrais voir `config.py`, `run_jarvis.py`, `core/`, `tools/`, `docs/` à la
racine. Si tu veux comparer avec l'ancien projet, garde
`JARVIS_MARDI.zip` dézippé à côté (pas dans le même dossier) pour aller
piocher dans `tools_legacy/` au fur et à mesure — voir `docs/MIGRATION.md`.

---

## Étape 2 — Environnement Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Si `pip install` refuse avec une erreur `externally-managed-environment` :
c'est Homebrew/macOS qui protège le Python système, pas un problème du
projet — le `venv` créé juste avant règle ça automatiquement. Si tu vois
quand même l'erreur, vérifie que `source venv/bin/activate` a bien été
exécuté juste avant (l'invite du terminal doit commencer par `(venv)`).

À chaque nouvelle session de terminal, il faut refaire `source venv/bin/activate`
avant de lancer `run_jarvis.py` — sinon `ModuleNotFoundError` sur `pydantic`,
`openai`, etc.

---

## Étape 3 — Dépendances système (facultatif pour le premier lancement)

Seulement si tu comptes utiliser les fonctions vocales/médias plus tard —
pas bloquant pour la suite de ce tutoriel :

```bash
brew install ffmpeg      # notes vocales Telegram
brew install espeak-ng   # Kokoro (français)
brew install chafa       # visionner une image dans le terminal
```

---

## Étape 4 — Configurer `.env`

```bash
cp .env.example .env
```

Ouvre `.env` dans un éditeur de texte et remplis au minimum :

- **`GEMINI_API_KEY`** : va sur https://aistudio.google.com/apikey, connecte-
  toi avec ton compte Google, crée une clé, colle-la ici. Gratuit avec des
  quotas larges pour un usage personnel.
- **`TELEGRAM_TOKEN`** : colle le nouveau jeton donné par BotFather à
  l'étape 0 — seulement si tu comptes utiliser le mode Telegram.
- **`TELEGRAM_ALLOWED_USER_IDS`** : laisse vide pour l'instant si tu ne
  connais pas encore ton identifiant Telegram — voir l'étape 9 pour comment
  l'obtenir. Le mode `telegram` refusera de démarrer tant que ce n'est pas
  rempli (voulu : un bot avec accès shell ne doit jamais être ouvert à
  n'importe qui).

Le reste (`LLAMA_API_BASE`, `KOKORO_*`...) peut rester tel quel pour le
premier lancement — ce sont des réglages pour les étapes optionnelles plus
bas.

---

## Étape 5 — Premier lancement, en CLI

```bash
python run_jarvis.py cli jarvis
```

Tu devrais voir :

```
🤖 JARVIS — Superviseur Suprême & Coordination Générale
(Ctrl+C ou 'exit' pour quitter, '/agent <nom>' pour changer de persona)

Denis >
```

Essaie une première question simple, par exemple `Combien font 12 x 8 ?` —
tu dois voir une réponse cohérente. Essaie ensuite `/agent leo` pour changer
de persona et vérifier que le changement de contexte fonctionne.

**Si tu demandes une action shell ou AppleScript** (ex. « liste les fichiers
de mon Bureau »), JARVIS te demande confirmation dans le terminal avant de
l'exécuter — c'est voulu (voir `jarvis2/docs/AUDIT_JARVIS.md` §6, point 8) :
tape `o` pour confirmer, autre chose pour annuler. La recherche web, la
lecture de page et le téléchargement, eux, s'exécutent directement, sans
confirmation.

**Si ça plante avec une erreur liée à `GEMINI_API_KEY`** : vérifie que `.env`
est bien rempli et que tu es dans le dossier `jarvis2/` quand tu lances la
commande (le fichier `.env` est lu depuis le dossier courant).

**Sur la vitesse de réponse :** `JARVIS_MODELE_LOCAL_DABORD=0` par défaut
dans `.env.example` — d'après ce qu'on s'est dit, tu démarres directement sur
Gemini cloud, donc pas de délai d'attente vers un serveur local à ce stade.
Repasse-le à `1` seulement une fois le serveur local lancé (étape 7).

---

## Étape 6 — Vérifier avec le harnais de tests

Une fois le premier échange concluant, lance :

```bash
python eval_harness.py
```

Ça rejoue une poignée de cas de test (calcul simple, détection de demande
ambiguë, refus d'inventer un résultat...) et affiche un score. C'est le bon
réflexe à prendre **après chaque modification** d'un prompt ou d'un outil,
pour repérer une régression avant qu'elle ne se voie en usage réel — voir
les commentaires en tête de `eval_harness.py` pour ajouter tes propres cas
au fil de l'eau, dès qu'un agent se plante sur quelque chose en usage réel.

---

## Étape 7 (optionnel) — Brancher le modèle local

Seulement si tu veux vraiment utiliser Gemma en local (vie privée, pas de
coût API, fonctionne hors-ligne) plutôt que tout envoyer sur Gemini cloud :

1. Récupère le binaire `llama-server` (pas inclus dans le zip — c'est un
   exécutable compilé spécifique à ta machine) : soit
   `brew install llama.cpp`, soit un binaire précompilé depuis
   https://github.com/ggml-org/llama.cpp/releases correspondant à ton Mac
   (Apple Silicon ou Intel).
2. Télécharge un modèle GGUF (par exemple une version quantisée de
   Gemma 4 12B) et note son chemin.
3. Dans `.env`, ajoute (ou adapte si les noms diffèrent déjà) :
   ```
   JARVIS_MODEL_PATH=/chemin/vers/ton-modele.gguf
   ```
4. Dans un premier terminal, à part, laissé ouvert :
   ```bash
   ./scripts/start_llama_server.sh
   ```
   Tu dois voir `🚀 Démarrage du serveur local sur http://localhost:8080`.
5. Dans un second terminal, relance `python run_jarvis.py cli jarvis` — les
   réponses passent maintenant par le modèle local en premier (bascule
   automatique vers le cloud seulement si le serveur local répond mal ou
   pas du tout).

---

## Étape 8 (optionnel) — Mode Herdr

Seulement si Herdr est déjà installé et que tu veux retrouver la
configuration multi-panes (un persona par pane). Herdr injecte lui-même
`HERDR_ENV=1` et `HERDR_PANE_ID` dans chaque pane qu'il lance — rien à
ajouter dans `.env` pour ça. Dans un pane Herdr :

```bash
python run_jarvis.py herdr leo
```

(remplace `leo` par le persona voulu dans ce pane). Vérifie ensuite
`herdr agent list` depuis un autre terminal : le persona doit apparaître
avec le statut `idle`. Pour relancer facilement les 9 panes d'un coup, voir
`jarvis2/scripts_legacy/launch_herdr_studio.py` — pas encore relu ni
adapté à la nouvelle arborescence, à vérifier avant usage (voir
`docs/MIGRATION.md`).

---

## Étape 9 (optionnel) — Mode Telegram

Une fois `TELEGRAM_TOKEN` rempli à l'étape 4 :

```bash
python run_jarvis.py telegram
```

Si `TELEGRAM_ALLOWED_USER_IDS` est encore vide, ça refuse de démarrer avec
un message explicite — c'est voulu. Pour connaître ton identifiant :

1. Laisse `TELEGRAM_ALLOWED_USER_IDS` vide pour l'instant, mais commente
   temporairement la ligne `config.exiger_config_telegram_ou_lever()` dans
   `run_jarvis.py::mode_telegram` — ou plus simple, mets une valeur
   provisoire bidon (ex. `0`) juste pour ce premier lancement.
2. Lance le bot, envoie-lui `/whoami` depuis ton propre compte Telegram —
   il te répond ton identifiant numérique.
3. Colle cet identifiant dans `TELEGRAM_ALLOWED_USER_IDS` (remets la ligne
   de vérification si tu l'avais commentée), relance.

**Note :** dans cette version, le mode Telegram ne gère que le texte — pas
encore les notes vocales ni les documents (voir `docs/MIGRATION.md`,
`tools_legacy/jarvis_telegram_hub.py` contient cette logique dans l'ancien
projet, à reporter). Les actions nécessitant confirmation (shell, AppleScript,
SSH distant...) affichent deux boutons **✅ Confirmer** / **❌ Annuler**
directement dans Telegram — tu as 2 minutes pour répondre, sinon l'action est
annulée par sécurité.

---

## Étape 10 (optionnel) — Suivre l'activité en direct

Pendant que tu utilises JARVIS dans un terminal (CLI, Herdr ou Telegram),
ouvre un second terminal :

```bash
source venv/bin/activate
python live_dashboard.py
```

Un onglet apparaît par persona actif, avec le détail de chaque étape de
raisonnement (💭 réflexion, 🔧 appel d'outil, 📥 résultat, ❌ erreur,
✅ réponse finale) — utile pour comprendre pourquoi un agent a pris telle
décision, sans avoir à fouiller les logs.

---

## Étape 11 (optionnel) — Automatiser au démarrage (launchd)

Pour que le centre de contrôle web et la consolidation nocturne se relancent
tout seuls (voir `jarvis2/automation_legacy/`) :

1. Ouvre `automation_legacy/com.denis.jarvis.nightly.plist` et
   `com.denis.jarvis.webapp.plist`, remplace les chemins
   `/Users/TON_UTILISATEUR/Assistant_IA/...` par tes vrais chemins (là où
   tu as dézippé `jarvis2/` et créé le `venv`).
2. **Ces deux fichiers dépendent de `interface_legacy/webapp.py` et
   `automation_legacy/nightly_reflection.py`, pas encore relus** (voir
   `docs/MIGRATION.md`, priorité haute) — teste-les manuellement
   (`python -m interface_legacy.webapp`) avant de les automatiser, pour ne
   pas découvrir un problème seulement à 6h du matin.
3. Une fois testés :
   ```bash
   cp automation_legacy/com.denis.jarvis.nightly.plist ~/Library/LaunchAgents/
   cp automation_legacy/com.denis.jarvis.webapp.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.denis.jarvis.nightly.plist
   launchctl load ~/Library/LaunchAgents/com.denis.jarvis.webapp.plist
   ```

---

## Et ensuite

- `jarvis2/docs/MIGRATION.md` liste les fichiers `*_legacy/` par ordre de
  priorité (mail, fichiers, installation d'applications en premier — accès
  large ou destructeur) pour les relire et les rebrancher un par un via
  `@outil(...)` dans `core/tools_registry.py`, en suivant le même modèle que
  `tools/system_tools.py` ou `tools/network_tool.py`.
- `jarvis2/docs/AUDIT_JARVIS.md` reste la référence complète de ce qui a été
  trouvé et pourquoi — utile à relire si un comportement te semble étrange
  et que tu veux vérifier si c'était déjà documenté.
- Après chaque outil rebranché : relance `eval_harness.py`, ajoute un cas de
  test dédié à ce que tu viens de brancher.

## Dépannage rapide

| Symptôme | Cause probable | Solution |
|---|---|---|
| `ModuleNotFoundError` | Le `venv` n'est pas activé | `source venv/bin/activate` |
| `RuntimeError: GEMINI_API_KEY absent` | `.env` pas rempli ou pas au bon endroit | Vérifie que tu es dans `jarvis2/` et que `.env` (pas `.env.example`) contient une vraie clé |
| Le mode `telegram` refuse de démarrer | `TELEGRAM_ALLOWED_USER_IDS` vide | Voir étape 9 |
| Réponse lente sans erreur, `JARVIS_MODELE_LOCAL_DABORD=1` | Tentative modèle local (non lancé) avant bascule cloud | Normal si le serveur local (étape 7) n'est pas encore lancé, sinon repasse à `0` |
| JARVIS refuse d'exécuter une commande shell légitime | Motif bloqué par `config.COMMANDES_INTERDITES` (`rm`, `sudo`, chemin système...) | Voulu (voir étape 5) — passe par `supprimer_fichier_en_securite` pour un effacement, ou fais l'action toi-même si c'est un vrai besoin système |
| `herdr agent list` ne montre pas le persona | `assurer_presence()` pas encore appelée (le pane vient d'être lancé) | Attends le tout premier tour de boucle, ou vérifie `HERDR_ENV=1` bien injecté par Herdr |
