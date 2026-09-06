# Journal des décisions

> Log **append-only** (on ajoute, on ne réécrit jamais l'historique) des
> décisions stratégiques importantes : changement de positionnement, refus
> d'un client, nouvelle offre lancée, pivot d'outil, etc. Jarvis le
> consulte pour ne pas te re-suggérer une piste déjà écartée et pour
> comprendre le « pourquoi » derrière tes choix actuels.

## Format d'une entrée

```
### AAAA-MM-JJ — [Titre court de la décision]
- Contexte :
- Décision prise :
- Pourquoi :
- Ce que ça change concrètement :
```

---

## Historique

<!-- Ajouter les nouvelles entrées en haut, les plus récentes en premier. -->

### 2026-08-12 — Deuxième installation, dédiée à Laura (`jarvis-laura/`)
- Contexte : Laura n'a pas de Mac ; besoin d'un assistant à elle
  (rappels, emails, factures, suivi clients) accessible depuis son
  téléphone, sans lui donner accès à mes propres fichiers, mails ou
  conversations, ni à mon Mac en tant que tel.
- Décision prise : dossier séparé `jarvis-laura/`, même code de base que
  `jarvis/` mais avec sa propre configuration — mémoire et Second Cerveau
  100 % séparés (`~/Assistant_IA_Laura/`), son propre bot Telegram, son
  propre compte Gmail, un seul agent généraliste (pas les 9 personas), et
  aucun outil shell/fichiers/calendrier. Seule ressource partagée entre
  les deux installations : le serveur du modèle local (llama-server, port
  8080) — les deux bots tournent en parallèle sur le même Mac et
  interrogent le même Gemma 4, chacun avec sa mémoire et ses identifiants.
- Pourquoi : <!-- à compléter par Denis -->
- Ce que ça change concrètement : deux process `python app.py` à lancer
  en parallèle (un par dossier) en plus de `start_llama_server.sh` (lancé
  une seule fois, depuis `jarvis/`, partagé par les deux). Le calendrier
  n'est volontairement pas branché pour Laura pour l'instant : l'outil
  actuel lit tous les comptes du Calendrier.app local sans distinction,
  ce qui mélangerait nos événements si on l'activait tel quel — à
  reprendre si besoin (voir `jarvis-laura/README.md`).

### 2026-08-11 — Modèle local : Gemma 4 12B remplace Hermes-4-14B, vision consolidée dans le même serveur
- Contexte : Hermes-4-14B (texte pur) tournait avec un second serveur de
  vision séparé (Qwen3-VL-2B, port 8081, géré par `tools/vision_manager.py`)
  démarré/arrêté à la demande pour `decrire_image` — deux modèles, deux
  process à surveiller pendant une analyse d'image, et de la RAM réservée
  en double sur les 16 Go du Mac.
- Décision prise : bascule vers `gemma-4-12b-it-UD-Q4_K_XL.gguf` (Unsloth,
  licence Apache 2.0), multimodal nativement (texte + image + audio,
  architecture "encoder-free"). La vision tourne maintenant sur le même
  serveur llama.cpp que la conversation (port 8080), via un simple mmproj
  (~175 Mo) chargé avec le modèle principal — plus de deuxième serveur.
  `tools/vision_manager.py` et `scripts/start_vision_server.sh` supprimés.
  Le mode "thinking" de Gemma 4 est désactivé au démarrage du serveur
  (`--chat-template-kwargs '{"enable_thinking":false}'`) pour éviter que
  CodeAgent (smolagents) ne reçoive une réponse vide (le texte partirait
  sinon dans un canal de raisonnement séparé plutôt que dans la réponse).
- Pourquoi : Hermes + Qwen3-VL en simultané pendant une analyse d'image
  s'approchait de la limite des 16 Go de RAM. Gemma 4 12B pèse à peu près
  autant que Hermes seul (~7,4 Go contre ~7,1 Go) tout en intégrant la
  vision — l'architecture devient plus simple (un seul serveur, un seul
  modèle à surveiller) sans perdre de RAM disponible pour le reste
  (navigation, etc. pendant l'usage de Jarvis). Quant Q5_K_XL testé pour
  voir si la qualité valait le Go de RAM en plus ; gardé en Q4_K_XL au
  final pour garder de la marge plutôt que de flirter avec la limite.
- Ce que ça change concrètement : `./scripts/start_vision_server.sh`
  n'existe plus, un terminal en moins à ouvrir au démarrage (voir README,
  section Démarrage rapide) ; l'outil `liberer_ram_vision` supprimé (plus
  de process séparé à libérer) ; `.env` simplifié — `JARVIS_VISION_MODEL_PATH`
  et `JARVIS_VISION_MMPROJ_PATH` remplacés par un seul `JARVIS_MMPROJ_PATH`.

### 2026-08-09 — Assistant personnel sur smolagents (Hermes 4 14B local + Gemini gratuit en secours)
- Contexte : exploration précédente d'une pile plus lourde (Docker, Ollama,
  Open WebUI, Qdrant, SearXNG) sous le nom ANUNNAKI, elle-même issue d'un
  premier projet nommé SOVEREIGN.
- Décision prise : assistant personnel construit directement en Python
  (smolagents CodeAgent), toujours sur Hermes 4 14B en local pour le texte
  quotidien, avec escalade automatique et gratuite vers Gemini Cloud
  (palier Flash, sans carte bancaire) pour les tâches trop lourdes pour les
  16 Go de RAM du Mac. Neuf agents nommés simplement (Jarvis, Alfred, Ray,
  Cléo, Leo, Franklin, Tesla, Ansel, Indiana) plutôt que d'après le
  panthéon sumérien, tous branchés sur les mêmes outils (recherche web,
  mémoire LanceDB, fichiers, email, contrôle du Mac). Second Cerveau
  (ces 6 fichiers) synchronisé directement dans cette mémoire plutôt que
  dans une base de connaissances Open WebUI séparée.
- Pourquoi : <!-- à compléter par Denis -->
- Ce que ça change concrètement : plus besoin de Docker Desktop ni
  d'Ollama qui tournent en permanence ; un seul process serveur (llama.cpp)
  ; le Second Cerveau et la mémoire à long terme partagent maintenant la
  même base (LanceDB) au lieu de deux systèmes séparés ; accessible depuis
  Telegram (avec liste blanche d'identifiants), la voix sur le Mac, et la
  ligne de commande.

---
*Rituel recommandé : ajouter une entrée dès qu'une décision engage plus
d'une semaine de travail ou change un prix / un positionnement.*
