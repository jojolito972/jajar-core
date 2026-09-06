# ⚠️ Incident de sécurité — jeton Telegram exposé

**À traiter avant toute autre chose, avant même de relancer JARVIS.**

## Ce qui a été trouvé

Le jeton du bot Telegram `@Bilbokeybot` est codé en clair dans **15 fichiers**
de `JARVIS_MARDI.zip`, dont du code destiné à tourner en production
(`jarvis_main.py`, `tools/jarvis_telegram_hub.py`), des scripts de test dans
`bac_a_sable/`, et le contenu Markdown du Second Cerveau
(`second-cerveau/02_Journal/2026-08-17.md` et `2026-08-18.md`). Le dossier
contient un historique Git (`.git/`) sans aucun `.gitignore` — si un `.env`
réel a un jour été ajouté, il est probablement toujours dans cet historique
même s'il a été supprimé depuis en apparence.

Un chat_id personnel (`776819401`) apparaît aussi en dur à plusieurs endroits
— moins critique qu'un jeton d'API, mais à traiter avec la même hygiène.

## Ce que ça permet à quelqu'un de mal intentionné

Ce bot a accès, via JARVIS, à l'exécution de commandes shell, à la lecture/
écriture de fichiers, et potentiellement aux mails — un jeton volé donne un
accès direct à tout ça, pas juste à la conversation Telegram.

## Actions à faire, dans cet ordre

1. **Révoquer le jeton maintenant.** Sur Telegram : `@BotFather` → `/mybots`
   → sélectionner `Bilbokeybot` → `API Token` → **Revoke current token**.
   L'ancien jeton meurt instantanément, y compris partout où il traîne — plus
   besoin de le retrouver et le supprimer manuellement dans chaque fichier
   avant d'être protégé.
2. **Ne coller le nouveau jeton que dans `.env`** (jamais dans un fichier
   `.py` ou `.md`, jamais commité). Le `.env.example` fourni dans la nouvelle
   base explique où.
3. **Si ce dossier a déjà été poussé sur un dépôt Git distant** (GitHub,
   GitLab...), considérer que l'ancien jeton était public dès ce moment-là,
   même après rotation côté Telegram — l'historique Git garde une copie
   consultable de toute donnée déjà poussée. Deux options :
   - Le plus simple et le plus sûr : **repartir d'un historique Git propre**
     avec la nouvelle base fournie (`git init` dans le nouveau dossier plutôt
     que de réutiliser l'ancien `.git/`).
   - Si l'historique doit être conservé pour une autre raison : nettoyer avec
     `git filter-repo` (ou BFG Repo-Cleaner) pour purger le jeton de tous les
     commits, puis forcer la mise à jour de tout remote existant.
4. **Configurer `TELEGRAM_ALLOWED_USER_IDS` avant tout usage réel.** La
   nouvelle base refuse de démarrer le mode Telegram sans ça (voir
   `config.exiger_config_telegram_ou_lever()`), pour ne plus dépendre d'y
   penser à chaque fois.
5. **Vérifier `bac_a_sable/`** avant de le versionner à nouveau (ou l'exclure
   entièrement — déjà fait dans `.gitignore`).

## Ce qui a été corrigé structurellement dans la nouvelle base

Pour que ça ne se reproduise pas de la même façon : plus aucune variable
secrète n'a de valeur de repli codée en dur nulle part dans le code (voir
`config.py`, fonction `_require_env`) — une variable d'environnement absente
fait planter le démarrage avec un message clair, plutôt que de continuer
silencieusement avec une valeur fantôme.

Voir `docs/AUDIT_JARVIS.md` §1 pour le détail complet des constats de sécurité.
