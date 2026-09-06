# Audit JARVIS — état des lieux, faisabilité, plan d'action

Audit réalisé sur le contenu réel de `JARVIS_MARDI.zip` (pas seulement lu — chaque
bug listé ci-dessous a été **reproduit** : import réel des modules, `ast.parse`,
`grep` sur tout l'arbre, comparaison des deux `jarvis_main.py`, etc.)

**Verdict global :** l'architecture et les idées sont bonnes (personas spécialisés,
second cerveau en Markdown, boucle self-healing, skills comportementales, intégration
Herdr déjà largement correcte). Le problème n'est pas la conception, ce sont des
**bugs mécaniques concrets** (fichiers cassés, imports fantômes, doublons) plus
**une fuite de secret active** qui expliquent le "ça fonctionne mal". Rien de tout
ça ne nécessite de tout jeter — mais certains points sont urgents.

---

## 🔴 1. Urgent — sécurité

### 1.1 Jeton Telegram exposé en clair, dans **15 fichiers**, y compris dans Git

```
grep -rn "8906725051:AAG..." .   →  15 occurrences
```

Le jeton du bot `@Bilbokeybot` est codé en dur (pas juste en `.env`) dans :
`src/telegram_bot_listener.py`, `jarvis_main.py`, `tools/jarvis_telegram_hub.py`,
`tools/test_audio_fix.py`, 8 fichiers de `bac_a_sable/`, et **dans le contenu
Markdown du Second Cerveau** (`second-cerveau/02_Journal/2026-08-17.md` et
`2026-08-18.md`, 6 fois). Le dépôt contient un `.git/` mais **aucun `.gitignore`** :
si un `.env` réel a un jour été ajouté, il est probablement toujours dans
l'historique Git même s'il a été supprimé depuis.

**Impact réel :** n'importe qui en possession de ce zip (ou de l'historique Git)
peut piloter le bot Telegram — qui a accès au shell, aux fichiers et aux mails.

**Action immédiate, avant toute autre chose :**
1. Sur Telegram, parler à `@BotFather` → `/mybots` → `Bilbokeybot` → `API Token`
   → **Revoke current token** (un nouveau jeton est généré, l'ancien meurt
   instantanément, y compris partout où il traîne).
2. Mettre le nouveau jeton **uniquement** dans `.env` (jamais de fallback codé en
   dur dans le code — voir 1.2).
3. Si ce dossier a déjà été poussé sur un Git distant (GitHub...), traiter le
   jeton comme compromis même après rotation : nettoyer l'historique
   (`git filter-repo` ou recommencer un dépôt propre — recommandé ici, voir §5).
4. Passer `TELEGRAM_ALLOWED_USER_IDS` en obligatoire au démarrage (aujourd'hui
   c'est juste "fortement recommandé" dans `.env.example` — un bot avec accès
   shell ne devrait jamais pouvoir démarrer sans liste blanche).

### 1.2 Fallback de jeton codé en dur dans la logique elle-même

Ce n'est pas qu'un `.env` mal protégé — le code a une vraie valeur de secours :

```python
token = env_vars.get("TELEGRAM_TOKEN") or ... or "8906725051:AAGOqCcl-..."
```

(`jarvis_main.py`, `tools/jarvis_telegram_hub.py`). Même en corrigeant le `.env`,
tant que cette ligne existe, le secret reste diffusé avec le code source. Un
`os.environ["TELEGRAM_TOKEN"]` qui lève une erreur claire si absent est nettement
plus sûr qu'un `or "valeur-en-dur"` qui masque l'oubli. Idem pour le chat_id
`776819401` en dur (moins critique, mais même logique à appliquer).

### 1.3 Vérification TLS désactivée pour les appels à l'API Telegram

```python
SSL_CTX_PERMISSIF = ssl.create_default_context()
SSL_CTX_PERMISSIF.check_hostname = False
SSL_CTX_PERMISSIF.verify_mode = ssl.CERT_NONE
```

Utilisé pour parler à `api.telegram.org`. Ça désactive complètement la
vérification de certificat — n'importe quelle interception réseau (Wi-Fi public,
proxy compromis) peut se faire passer pour Telegram et lire/modifier les échanges,
y compris le jeton du bot lui-même envoyé dans l'URL. C'était probablement un
correctif rapide contre une erreur de certificat locale (chemin `SSL_CERT_FILE`
mal configuré côté Python/macOS) — la vraie solution est de corriger la config
`certifi`, pas de désactiver la vérification. J'ai retiré ce pattern dans la
nouvelle base (voir §6).

### 1.4 Exécution shell/SSH pilotée par le LLM, avec liste noire seulement

`executer_commande_shell` (et son équivalent qui tourne aussi via SSH vers
`ios@192.168.1.33` d'après `session_active.json`) bloque une poignée de motifs
regex (`rm -rf /`, `mkfs`, `dd`...) mais autorise tout le reste. Une liste noire
ne couvre jamais tous les cas (ex : rien n'empêche `curl | sh` vers un script
arbitraire, ou une suppression ciblée hors du dossier `Supprimer/`). Pas la peine
de virer cette capacité — c'est le cœur de l'automatisation voulue — mais il faut
un **filet de sécurité en plus**, pas à la place : confirmation obligatoire pour
toute commande touchant un hôte distant, `dry_run` par défaut pour les suppressions
(déjà fait pour `organiser_dossier`, à généraliser), journalisation systématique
(déjà fait, bien).

### 1.5 Injection shell dans `network_tool.py`

```python
def executer_commande_ssh(nom_hote, utilisateur, commande):
    cmd_complete = f"ssh {utilisateur}@{nom_hote} '{commande}'"
    subprocess.run(cmd_complete, shell=True, ...)
```

Si `commande` contient un guillemet simple, on sort de la citation shell et on
injecte des arguments SSH arbitraires. Comme `commande` est composée par le LLM
(donc indirectement influençable par du texte externe — page web lue, mail...),
c'est une vraie surface d'injection, pas juste théorique. Correction simple :
`subprocess.run(["ssh", f"{utilisateur}@{nom_hote}", commande], shell=False)`
ou `shlex.quote(commande)`.

---

## 🔴 2. Bugs fonctionnels confirmés (testés, pas supposés)

### 2.1 Quatre fichiers cassés par un copier-coller de commande shell

`importer_second_cerveau.py`, `scripts/consolidation_nocturne.py`,
`tools/notebooklm_tool.py`, `tools/kdp_asset_pipeline.py` commencent tous par :

```
cat << 'EOF' > nom_du_fichier.py
```

...et finissent par `EOF` — c'est-à-dire que le bloc `cat <<EOF > fichier ... EOF`
utilisé pour **créer** le fichier a été collé **dans** le fichier lui-même, au lieu
d'y coller seulement ce qu'il y a entre les deux lignes.

C'est un bug sournois : un simple `python -m py_compile` ou une relecture rapide
ne le voient pas forcément, parce que **c'est syntaxiquement valide en Python**
(`cat << 'EOF' > tools/x.py` se parse comme une expression — comparaison entre
deux opérations binaires — qui ne plante qu'à l'exécution). Testé en réel :

```
NameError: name 'cat' is not defined
```

sur les 4 fichiers, dès la première ligne exécutée. Résultat concret :
- **Le Second Cerveau ne peut pas être synchronisé** — la fonctionnalité phare
  documentée en détail dans le `README.md` ("resynchronise mon second cerveau")
  est cassée dans ses deux implémentations (voir 2.2).
- **La consolidation nocturne (bilan du jour + apprentissage des erreurs, l'équivalent
  exact de ce que Franck L. décrit dans la réunion) ne tourne jamais.**
- **L'intégration NotebookLM ne peut pas s'initialiser.**
- Le pipeline KDP est cassé.

→ Correctif : trivial (retirer la 1ère et la dernière ligne), déjà fait dans la
nouvelle base fournie. Mais ça montre qu'aucun de ces 4 fichiers n'a été exécuté
ne serait-ce qu'une fois depuis sa création.

### 2.2 La synchronisation du Second Cerveau est cassée d'une **deuxième façon**,
indépendante de la précédente

Le `README.md` documente `python -m scripts.importer_second_cerveau` comme LA
méthode officielle (pas la version à la racine, cassée par le bug 2.1). Ce fichier-là
n'a pas le bug heredoc, mais :

```python
from jarvis_tools import _synchroniser_second_cerveau_impl
```

Cette fonction **n'existe nulle part dans le dépôt** — ni dans `jarvis_tools.py`
(racine), ni dans `interface/jarvis_tools.py`, ni dans `tools/jarvis_tools.py`
(vérifié par `grep` exhaustif). Résultat : `ImportError` garanti à chaque exécution.

**Conclusion : il n'existe aujourd'hui aucun chemin fonctionnel pour synchroniser
le Second Cerveau.** C'est indépendant du bug 2.1, donc corriger l'un sans l'autre
ne suffit pas.

### 2.3 Trois fichiers différents nommés `jarvis_tools.py`

| Fichier | Contenu réel |
|---|---|
| `jarvis_tools.py` (racine) | Outils `@tool` smolagents : image, shell, AppleScript, rangement dossier |
| `interface/jarvis_tools.py` | 2 lignes, une fonction non implémentée (`interroger_memoire_locale`) |
| `tools/jarvis_tools.py` | Un seul outil, sans rapport : `interroger_bibliotheque_pdfs` |

Trois responsabilités différentes, même nom de fichier, dans trois dossiers.
N'importe quel `import jarvis_tools` est ambigu selon le `sys.path` au moment de
l'exécution — c'est très probablement la cause du bug 2.2 (le développeur qui a
écrit `scripts/importer_second_cerveau.py` pensait sans doute à une fonction qui
existait dans une version antérieure d'un des trois fichiers, remplacée depuis).

### 2.4 `jarvis_tools.py` (racine) n'est importé nulle part dans `jarvis_main.py`

Confirmé par `grep` : aucune des fonctions `generer_image_ansel`,
`executer_commande_shell`, `organiser_dossier`, `executer_applescript` n'est
appelée depuis le point d'entrée réel. Ce sont des outils morts — écrits,
fonctionnels isolément, mais jamais branchés à l'agent qui tourne réellement.
(Ce constat était déjà dans `herdr-integration-jarvis.md`, §11.3 — confirmé ici.)

### 2.5 Le modèle local (Gemma-4 12B via llama.cpp) n'est jamais appelé

Le `README.md` consacre une section entière au serveur local (`llama-server`,
`LLAMA_API_BASE=http://localhost:8080/v1`, ~7,4 Go de modèle chargés en RAM) comme
pierre angulaire de l'architecture (vie privée, coût, hors-ligne). **Mais `grep`
sur tout le dépôt : zéro référence à `LLAMA_API_BASE` dans du code Python.** Le
package `openai` est dans `requirements.txt` (pour parler au serveur local en
API compatible OpenAI) mais n'est importé nulle part non plus.

En réalité, `jarvis_main.py` appelle exclusivement le **cloud Gemini**
(`client.models.generate_content`, `google-genai`) pour absolument tout : les 9
personas, chaque message, chaque délégation. Ce qui veut dire concrètement :
- Le serveur local que le README demande de laisser tourner en permanence
  (terminal 1) ne sert à rien dans le flux réel — RAM/CPU gaspillés pour rien.
- Chaque conversation avec chaque agent — y compris celui qui a accès au shell,
  aux mails, aux fichiers financiers du Second Cerveau — part sur le réseau vers
  l'API Google, alors que la promesse du README est "hors-ligne, vie privée".
- Soit c'est un pivot voulu et le README est juste périmé, soit c'est un oubli de
  branchement — dans les deux cas, il faut trancher explicitement (voir §4).

### 2.6 Point d'entrée introuvable

Le `README.md` dit `python app.py` pour lancer le bot Telegram (étape 3a). Aucun
`app.py` n'existe à la racine — seul `__pycache__/app.cpython-311.pyc` en garde la
trace, preuve qu'il existait et a été supprimé sans mise à jour de la doc.
D'après `session_active_jarvis.json`, le vrai point d'entrée Telegram actuel est
`tools/jarvis_telegram_hub.py`. Documentation et code ont divergé.

### 2.7 `scripts/consolidation_nocturne.py` : bug latent en plus du heredoc

Une fois le heredoc retiré, une deuxième erreur reste : si Gemini renvoie des
`erreurs`, le code fait `open(fichier_erreurs, "a")` sur
`second-cerveau/03_Erreurs_Et_Apprentissages/registre_erreurs.md` **sans créer le
dossier parent** — qui n'existe pas dans l'arborescence actuelle du Second
Cerveau. `FileNotFoundError` au premier jour où il y a effectivement une erreur
à consigner (donc probablement invisible en test, visible en usage réel).
Corrigé dans la nouvelle base (`.parent.mkdir(parents=True, exist_ok=True)`).

### 2.8 Deux `dashboard.py` sans rapport, même nom

`automation/dashboard.py` = génération du brief matinal (résumé, calendrier,
mails, météo) rendu en HTML. `dashboard.py` (celui fourni à part, en pièce jointe)
= visualiseur `textual` en direct des traces `.jsonl` de tous les agents. Ce sont
deux outils légitimes et complémentaires, mais le nom identique est trompeur —
renommés distinctement dans la nouvelle base (`morning_brief.py` /
`live_dashboard.py`).

---

## 🟡 3. Dette technique (pas bloquant, mais coûte du temps au quotidien)

- **`bac_a_sable/`** : 28 fichiers, 1,4 Mo, essentiellement des scripts de test
  ponctuels sur Kokoro/Telegram (`test_kokoro_siwis.py`, `fix_telegram_ssl.py`,
  `test_telegram_force.py`...) qui contiennent eux aussi le jeton en dur. Utile
  pendant le débogage, dangereux et confusant une fois committé durablement.
- **`backups/`** committé dans le dépôt** (`jarvis_main_20260817_222842.bak`,
  `jarvis_main_backup_20260817_223231.py`) : c'est le rôle de Git de garder
  l'historique, pas d'un dossier `backups/` à côté du code source.
- **`__pycache__/` et `.DS_Store`** committés (visibles dans le zip) — signe
  qu'il n'y a **aucun `.gitignore`** à la racine. Root cause probable du point 1.1
  (rien n'empêche un `.env` réel de finir committé par erreur).
- **Pas de tests automatisés** en dehors de `eval_harness.py` (bien pensé,
  mais actuellement débranché — voir §4).
- **Logique de routage par mots-clés fragile** : `traiter_outils_reels()` et
  `est_demande_complexe()` détectent l'intention via des listes de mots français
  (`"github"`, `"actualité"`, `"envoie sur telegram"`...). Ça rate les
  reformulations, les fautes de frappe, et l'anglais — et ça peut mal aiguiller
  (`"le devis Franklin va coûter cher, cherche l'écolabel"` contient "cher" mais
  pas "cherche"... etc., le risque de faux positif/négatif est réel). L'approche
  du `main.py` fourni à part (le LLM décide lui-même de l'action via un schéma
  JSON validé) est nettement plus robuste et s'étend mieux à 9 agents — c'est
  celle retenue dans la fusion (§6).

---

## ✅ 4. Ce qui est déjà bien conçu (à garder, pas à jeter)

- **Le système de personas** (9 experts avec domaine, couleur, rôle) est clair et
  bien pensé pour un studio multi-métiers.
- **Le Second Cerveau en Markdown simple** (pas une base de données) est le bon
  choix pour un usage personnel — éditable en 30 secondes, versionnable, lisible
  sans outil.
- **Les skills comportementales** (`skills/*.md` chargées dans le prompt système)
  sont une bonne pratique, conforme à ce que fait par ailleurs Claude Code.
- **La boucle self-healing** (ré-essaie une commande échouée avec un diagnostic
  plutôt que de répéter l'échec) est un bon réflexe anti-hallucination.
- **`herdr_bridge.py` est solide** et l'intégration Herdr décrite dans
  `herdr-integration-jarvis.md` est **déjà largement appliquée** dans
  `jarvis_main.py` — les bugs 11.1 et 11.2 qu'il documentait sont corrigés dans
  la version actuelle (vérifié ligne à ligne). Bonne nouvelle : ce chantier-là est
  presque terminé, pas à refaire.
- **Confirmation avant action irréversible** (mails en brouillon par défaut,
  suppression de fichier redirigée vers `Desktop/Supprimer/` plutôt qu'effacée) —
  exactement le bon réflexe, à généraliser à toutes les actions destructrices ou
  distantes (§1.4).
- **`automation/nightly_reflection.py` + `automation/dashboard.py`** (brief du
  matin) sont propres, défensifs (`try/except` partout), et fonctionnels tels
  quels — aucun bug trouvé dans ce binôme de fichiers.

---

## 5. Faisabilité des intégrations demandées

### 5.1 Herdr — ✅ Faisable, déjà fait à ~90 %

Le document `herdr-integration-jarvis.md` fourni est un vrai plan d'intégration
technique, pas une idée vague — il a manifestement déjà été appliqué : la fonction
`deleguer_a_agent` existe, est bien restreinte à JARVIS seul (`tools=[deleguer_a_agent]`
uniquement `if persona == "jarvis"`), avec le cap `maximum_remote_calls=4` recommandé.
Il ne reste que des points de vigilance mineurs (§10.6 du doc : le texte lu depuis
un autre pane contient les bordures ASCII de Rich, à filtrer si ça pollue le
contexte transmis à Gemini) et un prérequis d'environnement : **le CLI `herdr` doit
être installé et lancé** (`herdr.dev`) — rien dans le zip ne permet de vérifier
s'il l'est réellement sur la machine cible, c'est un test à faire manuellement
(`herdr agent list` doit lister les 9 agents après un premier lancement de chacun).

### 5.2 NotebookLM (`notebooklm-py`) — ✅ Faisable, un fichier à réparer + une règle à appliquer

Le runbook fourni est cohérent avec `tools/notebooklm_tool.py` (les commandes CLI
utilisées correspondent). Deux conditions pour que ce soit réellement opérationnel :
1. Réparer le bug heredoc (§2.1) — sinon `import tools.notebooklm_tool` plante.
2. Respecter la matrice **"sans confirmation" vs "demander confirmation"** que le
   runbook définit lui-même (§4 du runbook : `generate`, `download`, `delete` et
   les commandes `*_wait` en conversation principale doivent demander confirmation).
   Le code actuel de `notebooklm_tool.py` ne fait aucune distinction — chaque
   fonction s'exécute directement. Ajouté dans la nouvelle base (§6) via le
   registre à paliers de sécurité.
3. Point d'attention du runbook lui-même à ne pas oublier : `notebooklm login`
   exige un navigateur — impossible à automatiser à 100 %, la toute première
   authentification reste manuelle.

### 5.3 Idées issues de la réunion avec Franck L. — faisabilité au cas par cas

| Idée de Franck L. | État actuel dans JARVIS | Faisable ? |
|---|---|---|
| Révision nocturne des mémoires de session | `consolidation_nocturne.py` existe, cassé (§2.1, §2.7) | ✅ Oui, juste à réparer — déjà fait dans la nouvelle base |
| Binôme d'agents qui se surveillent, résument à 35 % de contexte | Rien d'équivalent trouvé dans le code | ✅ Faisable, à construire — squelette fourni (`core/state.py`, seuil `SEUIL_CONTEXTE_ALERT=0.35` déjà présent dans `jarvis_config.py` mais **jamais lu par aucun fichier** — encore un scaffold jamais branché) |
| Monitoring de fenêtre de contexte à 50 %, alerte toutes les 10 s | Rien d'équivalent | ✅ Faisable en local (compter les tokens de l'historique), pas besoin d'outil externe |
| Système de vérification à 3 couches (sémantique / graphe / NotebookLM la nuit) | `lancedb`/`kuzu` déclarés dans `requirements.txt`, `DB_PATH`/`GRAPHE_DB_PATH` définis dans `jarvis_config.py`, **mais aucun fichier du dépôt n'importe `lancedb` ni `kuzu`** — recherche exhaustive, zéro résultat en dehors des définitions de config | 🟡 Partiellement faisable : la brique NotebookLM est prête (5.2), la brique graphe/sémantique est à construire entièrement — c'est un chantier en soi, pas un simple branchement |
| Stratégie multi-comptes/multi-modèles pour lisser les coûts | Escalade Gemini existe (`tools/escalate_tool.py`, `MODELE_ESCALADE_GEMINI`), mais le "modèle local" qui devrait absorber le gros du volume n'est jamais appelé (§2.5) | 🟡 L'architecture le permet, mais tant que 100 % du trafic part sur Gemini cloud, il n'y a pas de "lissage" réel — c'est la même conclusion que 2.5 |
| Tailscale + VPS pour isoler la machine principale | Rien trouvé dans le zip à ce sujet (mentionné en réunion, pas dans le code) | Hors périmètre de cet audit — infra réseau, pas du code Python |
| Résilience au redémarrage (relance auto en 45s-1min) | `automation/*.plist` (launchd) gèrent `RunAtLoad`/`KeepAlive` pour le centre de contrôle web et le job nocturne — pas pour `jarvis_main.py` lui-même | 🟡 Partiel — à étendre si le mode voix/CLI doit aussi survivre à un redémarrage |

**En résumé sur la réunion Franck L. :** les idées les plus proches d'être
utilisables tout de suite sont la révision nocturne (juste cassée) et le
monitoring de contexte (jamais branché mais trivial à faire). Le système de
vérification à 3 couches est le plus ambitieux et le seul qui demande un vrai
chantier de développement plutôt qu'une réparation.

---

## 6. Ce qui a été fait dans la nouvelle base fournie

Voir `ARCHITECTURE.md` et `MIGRATION.md` pour le détail. En bref :

1. **Fusion des deux `main.py`** (voir demande initiale) : le moteur de décision
   du `main.py` fourni à part (schéma JSON validé par Pydantic, retry avec
   réparation automatique du JSON malformé, reflexion explicite sur échec d'outil,
   séparation stricte raisonnement/action) remplace le routage par mots-clés de
   `jarvis_main.py`, **sans perdre** ce qui marche déjà bien côté JARVIS : les 9
   personas, la délégation Herdr, la boucle self-healing sur commande shell, le
   Second Cerveau en contexte, les gardes-fous de confirmation.
2. Les 4 fichiers cassés par le bug heredoc sont réparés.
3. Le jeton codé en dur est retiré partout — plus aucun fallback en dur nulle
   part, `os.environ["TELEGRAM_TOKEN"]` lève une erreur explicite si absent.
4. `SSL_CTX_PERMISSIF` est retiré (vérification TLS normale rétablie).
5. Le paliers de sécurité (auto / confirmation requise / jamais automatique) est
   généralisé à tous les outils, pas seulement au shell — conforme à la logique
   déjà présente dans le runbook NotebookLM.
6. Un seul point d'entrée clair (`run_jarvis.py`), qui remplace le `app.py`
   manquant et clarifie CLI / Telegram / voix / Herdr comme des modes d'un même
   programme plutôt que des fichiers séparés qui divergent.
7. Un seul nom pour chaque module (fin des trois `jarvis_tools.py`).
8. **Ajouté après cet audit, sur demande explicite de {utilisateur}** (voir
   l'historique de la session pour le détail complet de chaque vérification) :
   - `tools/web_tool.py` : recherche, lecture de page, téléchargement —
     jamais branché dans l'ancien projet (même défaut que jarvis_tools.py,
     §2.4). Deux failles corrigées au passage (traversée de chemin, taille de
     téléchargement illimitée).
   - `tools/second_cerveau.py` repassé en recherche **sémantique** réelle
     (embeddings + lancedb, découpage en passages) plutôt que par mots-clés —
     avec un garde-fou anti-incohérence si l'index et la requête utilisent
     deux moteurs d'embedding différents (résultats sinon silencieusement
     faux). Le contenu réel du Second Cerveau (oublié dans la première
     version de cette base) a aussi été restauré, secrets rédigés.
   - `executer_commande_shell` et `executer_applescript` repassés de AUTO à
     CONFIRM (décision explicite de {utilisateur} : un shell/AppleScript
     local reste plus risqué qu'un outil à portée limitée comme la lecture
     web). En contrepartie, `config.COMMANDES_INTERDITES` protège maintenant
     explicitement les dossiers système macOS (`/System`, `/Library`
     racine — pas `~/Library` — `/usr`, `/etc`...), bloque `sudo`, et force
     toute suppression à passer par `supprimer_fichier_en_securite`
     (`~/Desktop/Supprimer/`) plutôt que par un `rm` direct qui contournerait
     ce garde-fou.
   - Le mode `telegram` de `run_jarvis.py` gère maintenant réellement la
     confirmation (clavier ✅/❌ inline, 120s, exécution dans un thread pour
     ne pas geler le bot) — ce n'était qu'un refus automatique juste avant.

Le reste des ~40 fichiers d'outils (mail, calendrier, Kokoro, météo, culture,
sauvegardes...) n'a pas été ré-écrit intégralement à la main dans cette passe —
ils sont copiés dans la nouvelle arborescence avec les correctifs de sécurité
automatiques appliqués (jeton, injection shell, `.gitignore`), documentés comme
"à relire" dans `MIGRATION.md`. Les réécrire tous en une seule fois, sans pouvoir
les tester sur la vraie machine (macOS, Kokoro, llama.cpp, Herdr), aurait un
risque de régression plus élevé que de les garder tels quels avec un correctif
ciblé.

## 6bis. Harness renforcé — pourquoi et comment (ajouté sur demande explicite)

{utilisateur} a demandé un système "digne de Claude Code" en réflexion, en
insistant sur le fait qu'un bon *harness* (l'architecture qui entoure le
modèle — planification, boucle, vérification) peut démultiplier un modèle
même petit sans le changer. Trois mécanismes ajoutés à `core/engine.py`,
chacun testé isolément avant livraison (voir l'historique de session pour le
détail complet de chaque test, pas seulement l'affirmation) :

1. **Plan persistant** (`core/schemas.py::EtapePlan`, `core/state.py::plan`) :
   une todo-list que le modèle peut créer et mettre à jour à chaque tour,
   montrée en ENTIER dans le prompt, jamais compressée (contrairement à
   l'historique). Testé : le statut d'une étape posé au tour 1 est bien vu,
   inchangé, au tour 2, puis correctement mis à jour au tour 3.
2. **Approfondissement adaptatif** : une réponse à confiance "basse" n'est
   PAS rendue telle quelle — le harness redemande explicitement un second
   passage de réflexion sous un angle différent, jusqu'à 2 fois par tâche.
   Testé : une réponse à confiance basse déclenche bien un second appel
   avant de conclure ; le plafond est respecté même si la confiance reste
   basse indéfiniment (pas de blocage).
3. **Vérification indépendante** : avant de rendre une réponse qui a mobilisé
   un outil (ou dont la confiance n'est pas "haute"), un appel modèle
   SÉPARÉ — contexte neuf, consigne délibérément critique — vérifie
   qu'elle répond vraiment à la tâche. Testé : un verdict "rejete" simulé
   fait bien reboucler l'agent (pas de réponse rendue), un "approuve"
   la laisse passer.

Testé aussi, dans l'autre sens : une tâche simple, sans outil, à confiance
haute dès le premier tour, ne déclenche NI approfondissement NI
vérification — un seul appel modèle au total. Le harness ajoute de la
rigueur là où le modèle doute ou agit, pas partout uniformément — sinon
chaque interaction, même triviale, coûterait plus cher et répondrait plus
lentement pour rien.

---

## 7. Plan d'action priorisé

1. **Aujourd'hui, avant de relancer quoi que ce soit :** révoquer le jeton
   Telegram via BotFather (§1.1).
2. **Avant de recommiter quoi que ce soit :** ajouter le `.gitignore` fourni,
   vérifier qu'aucun `.env` réel ne traîne dans l'historique Git existant.
3. **Cette semaine :** basculer sur la nouvelle base (`jarvis2/`), réparer/tester
   le Second Cerveau et la consolidation nocturne (les deux fonctionnalités les
   plus documentées et les plus cassées).
4. **Décision à trancher, pas juste technique :** modèle local ou cloud pour le
   trafic principal ? Ça change le coût, la latence et la confidentialité — tant
   que ce n'est pas explicitement choisi, le code ne peut pas être cohérent avec
   le README (§2.5).
5. **Ensuite, dans l'ordre de valeur/effort :** monitoring de contexte (trivial),
   paliers de sécurité sur NotebookLM (fait dans la base fournie), puis seulement
   si le besoin se confirme à l'usage, le système de vérification à 3 couches
   (le plus gros chantier).
