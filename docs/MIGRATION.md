# Migration — ce qui est fait, ce qui reste, dans quel ordre

## Ce qui a été entièrement réécrit et est prêt à l'usage

| Fichier | Rôle |
|---|---|
| `config.py` | Source unique de config — remplace `jarvis_config.py` |
| `core/schemas.py`, `state.py`, `llm_router.py`, `tools_registry.py`, `engine.py`, `tracing.py` | Le nouveau moteur (voir `docs/ARCHITECTURE.md`) |
| `tools/herdr_bridge.py` | Délégation inter-agents — repris quasi tel quel (déjà solide) |
| `tools/system_tools.py` | Shell, AppleScript, image, rangement, suppression sécurisée — remplace `jarvis_tools.py`, enfin branché |
| `tools/network_tool.py` | SSH/VNC/SMB — injection shell corrigée, confirmation obligatoire |
| `tools/second_cerveau.py` | Sync + recherche **sémantique** (embeddings/lancedb) — les deux bugs indépendants qui la cassaient sont corrigés |
| `tools/notebooklm_tool.py` | CLI notebooklm-py — bug heredoc corrigé, paliers alignés sur le runbook |
| `tools/web_tool.py` | Recherche web, lecture de page, téléchargement — jamais branché dans l'ancien projet, 2 failles corrigées (traversée de chemin, taille illimitée) |
| `scripts/consolidation_nocturne.py` | Bilan nocturne — bug heredoc + bug de dossier manquant corrigés |
| `run_jarvis.py` | Point d'entrée unique (cli / herdr / telegram) |
| `eval_harness.py`, `live_dashboard.py` | Adaptés au nouveau moteur, sinon inchangés (déjà bien conçus) |

Ces fichiers ont chacun une explication de ce qui a changé et pourquoi dans
leur propre docstring — pas la peine de la dupliquer ici.

## Ce qui a été migré mécaniquement, PAS encore relu

`scripts/migrer_outils_restants.py` a copié 40 fichiers de l'ancien projet
vers `tools_legacy/`, `scripts_legacy/`, `interface_legacy/` et
`automation_legacy/`, avec seulement des correctifs mécaniques déjà vérifiés
ailleurs dans le projet (bug heredoc, jetons en dur rédigés, import de
`jarvis_config` renommé en `config`). **Aucune logique métier n'a été
modifiée ni revue ligne à ligne dans cette passe** — les réécrire tous à la
main sans pouvoir les tester sur la vraie machine (macOS, Herdr, Kokoro,
llama.cpp) aurait un risque de régression plus élevé que de les garder tels
quels avec un correctif ciblé pendant que la nouvelle base est prise en main.

### Priorité haute — à relire avant tout usage réel

| Fichier | Pourquoi c'est prioritaire |
|---|---|
| `tools_legacy/jarvis_telegram_hub.py` | Contenait le jeton compromis (rédigé). C'est le vrai point d'entrée Telegram actuel d'après `session_active_jarvis.json` — fait doublon avec le mode `telegram` de `run_jarvis.py` (texte seul pour l'instant). À arbitrer : migrer sa gestion vocale/documents vers `run_jarvis.py`, ou l'abandonner au profit du nouveau. |
| `scripts_legacy/launch_herdr_studio.py` | C'est probablement ce qui lance les 9 panes Herdr au quotidien — sans lui, le mode `herdr` de `run_jarvis.py` doit être lancé manuellement persona par persona. |
| `scripts_legacy/backup_gdrive.py` | Dépendance directe de `scripts/consolidation_nocturne.py` (déjà réécrit) — sans lui, la sauvegarde de fin de job nocturne échoue silencieusement (repli déjà prévu dans le fichier réécrit, mais autant le brancher). |
| `interface_legacy/webapp.py` | Le centre de contrôle web + widget "Parler à Jarvis" — fonctionnalité utilisateur documentée en détail dans l'ancien README, probablement très utilisée au quotidien. |
| `tools_legacy/filesystem_tool.py`, `install_app.py` | Accès fichiers larges / installation d'applications — à classer explicitement dans les paliers de sécurité (`core.tools_registry.SecurityTier`) avant tout branchement, surtout `install_app.py`. |
| `tools_legacy/gmail_tool.py`, `trier_mails.py` | Accès mails — vérifier que le comportement "brouillon par défaut" documenté dans l'ancien README est bien celui du code, pas juste de la doc. |

### Priorité moyenne

`calendar_tool.py`, `mac_control_tool.py` (déjà audité comme raisonnable, a
des protections de chemins), `jarvis_document_processor.py`,
`jarvis_sentinel.py` (monitoring système simple, faible risque),
`jarvis_startup_notify.py`, `kdp_asset_pipeline.py` (heredoc corrigé, logique
non relue), `weather_tool.py`, `web_browser_tool.py`, `pense_bete.py`,
`meta_tool.py`, `agent_status_tool.py` / `agent_status_widget.py`,
`backup_manager.py`, `security_backup.py`, `culture_tool.py`, `file_injector.py`.

`scripts_legacy/ecoute_voix.py` + `tools_legacy/kokoro_engine.py` : les deux
fichiers nécessaires pour porter la boucle voix mains-libres de l'ancien
`jarvis_main.py` (non portée dans cette passe, voir plus bas).

`scripts_legacy/indexer_pdfs.py` : indexation des PDFs (persona Indiana) —
à brancher une fois `tools/second_cerveau.py` étendu ou une vraie base
vectorielle mise en place (voir la note de migration en bas de ce fichier).

`automation_legacy/morning_brief.py` + `nightly_reflection.py` : déjà audités
comme propres et fonctionnels (voir `docs/AUDIT_JARVIS.md` §4) — seul
changement mécanique appliqué (`jarvis_config` → `config`). Utilisables tels
quels après un test rapide, pas besoin d'une relecture complète comme les
autres.

### Priorité basse / à trancher plutôt qu'à migrer

- `interface_legacy/jarvis_cli.py` : superseded par `python run_jarvis.py cli`
  — probablement à supprimer plutôt qu'à maintenir en double.
- `interface_legacy/jarvis_tools.py` : le stub à 2 lignes jamais implémenté
  (`interroger_memoire_locale`) — sa fonction est maintenant pleinement
  implémentée dans `tools/second_cerveau.py`. À supprimer.
- `interface_legacy/chainlit_app.py`, `dashboard_app.py` : interfaces
  alternatives — à garder seulement si activement utilisées.
- `tools_legacy/test_audio_fix.py`, `test_tts.py` : scripts de test ponctuels
  — à déplacer dans un vrai dossier `tests/` plutôt que dans `tools/`.
- `interface_legacy/verifier_installation.py` : utilitaire de diagnostic
  d'installation — pratique à garder, faible risque.

## Ce qui n'a pas été porté du tout dans cette passe

**La boucle voix mains-libres** (Kokoro + `speech_recognition`, présente dans
l'ancien `jarvis_main.py`, fonction `mode_dialogue_continu_mains_libres`).
Raison : dépend de matériel et de modèles qui ne peuvent pas être testés
depuis cet environnement (micro, fichiers Kokoro téléchargés, `say` macOS).
Pour la porter : brancher `tools_legacy/kokoro_engine.py` +
`scripts_legacy/ecoute_voix.py` sur `core.engine.run_agent()` (même pattern
que `run_jarvis.py::mode_cli`, en remplaçant `input()`/`print()` par la
reconnaissance vocale et la synthèse Kokoro).

**La confirmation interactive en mode Telegram** — ~~implémentée~~ **faite** :
clavier inline (✅/❌), délai de 120s, exécutée dans un thread pour ne pas
geler le bot pendant l'attente. Testé en isolation (le pont thread ↔ asyncio,
sans dépendre d'un vrai bot Telegram — voir l'historique de la session).

**La recherche sémantique par embeddings** dans le Second Cerveau
(`lancedb`/`kuzu`, déclarés dans l'ancien `requirements.txt` mais jamais
branchés nulle part) — `tools/second_cerveau.py` fait une recherche par
mots-clés, suffisante pour le volume actuel. Le chemin de migration est
documenté directement en commentaire en bas de ce fichier.

**Le système de vérification à 3 couches** décrit par Franck L. en réunion
(sémantique / graphe / NotebookLM nocturne) — c'est le seul point de la
réunion qui est un vrai chantier de développement plutôt qu'une réparation
(voir `docs/AUDIT_JARVIS.md` §5.3). Pas commencé.

## Update — 2 fichiers non-Python complétés après coup

`scripts/migrer_outils_restants.py` ne traite que les fichiers `*.py` — deux
fichiers non-Python utiles avaient été oubliés dans la première passe, ajoutés
manuellement depuis :
- `scripts/start_llama_server.sh` : lance le serveur local llama.cpp (repris
  tel quel, il pointe déjà sur des variables d'environnement plutôt que des
  chemins en dur). Le binaire compilé `llama-server` lui-même n'a PAS été
  copié (exécutable spécifique à une machine/architecture) — voir
  `docs/TUTORIEL_INSTALLATION.md` pour où l'obtenir.
- `automation_legacy/com.denis.jarvis.nightly.plist` et
  `com.denis.jarvis.webapp.plist` : les deux définitions `launchd` pour
  automatiser la consolidation nocturne et le centre de contrôle web. Les
  chemins de module à l'intérieur ont été mis à jour
  (`automation.nightly_reflection` → `automation_legacy.nightly_reflection`,
  `interface.webapp` → `interface_legacy.webapp`) pour correspondre à la
  nouvelle arborescence — mais les chemins `/Users/TON_UTILISATEUR/...` sont
  encore des placeholders à remplacer par tes vrais chemins avant usage.

## Comment continuer

1. Lire `docs/SECURITY_INCIDENT.md` et agir dessus — avant tout le reste.
2. Copier `.env.example` en `.env`, remplir les valeurs, tester
   `python run_jarvis.py cli jarvis` en local.
3. Reprendre les fichiers "priorité haute" ci-dessus un par un : les relire,
   décider de leur palier de sécurité (`core.tools_registry.SecurityTier`),
   les enregistrer avec `@outil(...)`, les importer dans `run_jarvis.py`
   (même pattern que les imports déjà présents en haut du fichier).
4. Rejouer `eval_harness.py` après chaque outil rebranché pour vérifier
   l'absence de régression.
