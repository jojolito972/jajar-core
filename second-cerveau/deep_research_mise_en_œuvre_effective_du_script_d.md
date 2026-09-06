# Deep Research : Mise en œuvre effective du script d'écoute vocale et du démon de service pour le système vocal mains-libres de Laura Puntillo
*Date : 2026-08-25 02:57*

# RAPPORT TECHNIQUE D'INVESTIGATION : MISE EN ŒUVRE DU SYSTÈME VOCAL MAINS-LIBRES DE LAURA PUNTILLO

**À l'attention de :** Denis  
**De :** Analyste Deep Research, JAJAR  
**Sujet :** Analyse technique, architecture, mise en œuvre du script d'écoute vocale et du démon de service pour le système vocal mains-libres de Laura Puntillo.

---

## 1. INTRODUCTION ET ARCHITECTURE GLOBALE

Le système vocal mains-libres étudié (inspiré des architectures de type `voice-to-claude` et des assistants vocaux embarqués sur Linux) repose sur un paradigme de traitement local (*on-device*), garantissant la confidentialité et réduisant la latence à des seuils critiques (environ 1.8 seconde). 

L'architecture logicielle s'articule autour d'un **démon de service persistant** géré par `systemd` (au niveau utilisateur), orchestrant de concert trois moteurs neuronaux et utilitaires majeurs :
1. **OpenWakeWord** : Un moteur d'écoute permanente (*always-listening*) chargé de détecter le mot-clé d'activation (ex: *"OK Claude"*) ou les commandes directes de soumission (*"Execute"*).
2. **Silero VAD (Voice Activity Detection)** : Un réseau de neurones de détection d'activité vocale qui segmente dynamiquement le flux audio, distinguant la parole humaine du bruit de fond.
3. **Whisper.cpp** : Une implémentation ultra-optimisée en C/C++ du modèle de transcription d'OpenAI (accélérée par GPU/CPU), couplée à un injecteur de texte de type `ydotool` ou `xdotool` pour restituer la dictée dans la fenêtre active de l'OS.

### Schéma architectural de référence :
```text
┌─────────────────────────────────────────────────────────────────┐
│                     Voice Claude Daemon                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ OpenWakeWord (always listening)                           │  │
│  │ - "OK Claude" → start LISTENING state                     │  │
│  │ - "Execute" → press Enter, stay in IDLE                   │  │
│  └─────────────────────────────┬─────────────────────────────┘  │
│                                │                                │
│                                ▼ wake word detected             │  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ VAD (voice activity detection) → Recording                │  │
│  │ → whisper.cpp transcription → ydotool text injection      │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```
> **Source de référence :** *GitHub - Eumaios1212/voice-to-claude: Hands-free voice input for Claude Code on Linux*.

---

## 2. CONFIGURATION DE L'ENVIRONNEMENT ET DÉPENDANCES SYSTÈMES

La mise en œuvre nécessite un environnement Linux moderne (compatible avec les serveurs audio PipeWire ou PulseAudio, et les environnements graphiques X11 ou Wayland via l'émulation d'input global).

### Installation des dépendances de base
Les dépendances bas niveau incluent les outils de compilation, les bibliothèques de manipulation audio et les utilitaires d'injection d'événements clavier (`ydotool` pour la compatibilité Wayland/libinput) :

```bash
sudo apt update && sudo apt install -y \
    build-essential \
    cmake \
    git \
    python3-pip \
    python3-venv \
    portaudio19-dev \
    ydotool \
    alsa-utils
```

### Clonage et compilation du moteur d'inférence (Whisper.cpp)
Le cœur de la transcription repose sur `whisper.cpp`, configuré avec les modèles quantifiés (ex: `tiny` ou `base` en format `.bin`) pour garantir des performances temps réel :

```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
bash models/download.sh -t tiny
make
```
> **Source de référence :** *Industrial Monitor Direct - Building a Voice-Activated Data Entry System with Raspberry Pi 5*.

---

## 3. IMPLÉMENTATION DU SCRIPT D'ÉCOUTE VOCALE ET MACHINE À ÉTATS

Le démon principal repose sur une machine à états finis pilotée par des événements (flux audio en continu, interruptions de boutons physiques ou détections logicielles). 

### Structure de la Machine à États :
* **`IDLE` (0)** : Le système écoute en arrière-plan via OpenWakeWord ou attend un raccourci clavier global (ex: `Super+C`).
* **`RECORDING` (1)** : Capture active du flux audio via `arecord` ou `PyAudio` dès que la parole ou le déclencheur est détecté.
* **`PROCESSING` (2)** : Arrêt de la capture, exécution de `whisper.cpp`, nettoyage textuel (gestion de la ponctuation et du vocabulaire personnalisé) et injection de texte.

### Extrait du script de contrôle (Implémentation type) :

```python
#!/usr/bin/env python3
import subprocess
import time
import os

# Configuration des états
IDLE = 0
RECORDING = 1
PROCESSING = 2
state = IDLE

WHISPER_BINARY = "./whisper.cpp/main"
MODEL_PATH = "whisper.cpp/models/ggml-tiny.bin"
AUDIO_OUTPUT = "/tmp/voice_input.wav"

def start_recording():
    """Lance la capture audio en arrière-plan (16kHz, mono, S16LE)"""
    cmd = ["arecord", "-f", "S16LE", "-r", "16000", "-c", "1", AUDIO_OUTPUT]
    return subprocess.Popen(cmd)

def stop_and_transcribe(arecord_process):
    """Arrête l'enregistrement et traite le fichier audio via whisper.cpp"""
    arecord_process.terminate()
    arecord_process.wait()
    
    # Exécution de l'inférence Whisper
    result = subprocess.run(
        [WHISPER_BINARY, "-m", MODEL_PATH, "-f", AUDIO_OUTPUT, "-l", "fr", "--no-timestamps"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    transcribed_text = result.stdout.strip()
    return transcribed_text

def inject_text(text):
    """Injecte le texte transcrit dans la fenêtre active via ydotool"""
    if text:
        subprocess.run(["ydotool", "type", "--", text])

# Exemple de boucle principale du démon
if __name__ == "__main__":
    print("[DAEMON] Système vocal opérationnel. En attente d'activation...")
```
> **Source de référence :** *GitHub - Eumaios1212/voice-to-claude* & *Industrial Monitor Direct*.

---

## 4. CONFIGURATION DU DÉMON DE SERVICE SYSTEMD

Pour garantir la persistance du système vocal de Laura Puntillo (démarrage automatique à la session utilisateur, redémarrage en cas de plantage et gestion des logs), une configuration `systemd` au niveau utilisateur (*user space*) est requise.

### 1. Création du fichier de service
Créer le fichier de configuration dans le répertoire utilisateur :
```bash
mkdir -p ~/.config/systemd/user/
nano ~/.config/systemd/user/voice-claude.service
```

### 2. Contenu du fichier `voice-claude.service` :
```ini
[Unit]
Description=Voice-to-Claude Hands-Free Voice Input Daemon
After=network.target sound.target

[Service]
Type=simple
WorkingDirectory=/home/laura/voice-to-claude
ExecStart=/home/laura/voice-to-claude/venv/bin/python3 bin/daemon.py
Restart=on-failure
RestartSec=5
# Assure la restauration automatique du volume du micro pour éviter les bugs de mute d'Ubuntu/Linux
ExecStartPre=/usr/bin/amixer -q set Capture unmuted
ExecStartPre=/usr/bin/amixer -q set Capture 100%

[Install]
WantedBy=default.target
```

### 3. Activation et gestion du service
Exécuter les commandes suivantes pour activer et démarrer le démon :
```bash
# Recharger le daemon systemd pour l'utilisateur
systemctl --user daemon-reload

# Activer le service au démarrage de la session
systemctl --user enable voice-claude

# Démarrer le service immédiatement
systemctl --user start voice-claude

# Vérifier l'état en temps réel et consulter les logs
systemctl --user status voice-claude
journalctl --user -u voice-claude -f
```
> **Source de référence :** *GitHub - Eumaios1212/voice-to-claude (Architecture & systemd user service)*.

---

## 5. CONTRÔLES MANUELS, RACCOURCIS ET CONFIDENTIALITÉ

Le système intègre des mécanismes de contrôle granulaire permettant à l'utilisatrice de reprendre le contrôle à tout moment :

* **Activation par Hotkey (`Super + C`)** : Permet de déclencher l'écoute instantanément sans prononcer le mot-clé (*wake word*), contournant l'état `IDLE` pour passer directement en mode `RECORDING`.
* **Confidentialité & Mute (`Super + M`)** : Permet de basculer instantanément en état `Muted`. Contrairement à une coupure audio logicielle classique, le démon désactive le traitement du flux audio au niveau applicatif (*true privacy*, aucun échantillon audio n'est analysé par le VAD).
* **Commandes textuelles intégrées** : Prononcer *"Execute"* simule l'appui sur la touche `Entrée` de la fenêtre active pour soumettre directement la commande dictée.

Commandes CLI utilitaires associées :
```bash
voice-claude-toggle  # Bascule l'état Mute / Unmute
voice-claude-stop    # Arrête complètement le démon
voice-claude-start   # Redémarre le démon
```
> **Source de référence :** *GitHub - Eumaios1212/voice-to-claude (Privacy Toggle & Manual Control)*.

---

## 6. SYNTHÈSE DES RECOMMANDATIONS POUR LAURA PUNTILLO

1. **Isolation Environnementale :** Toujours exécuter le démon au sein d'un environnement virtuel Python (`venv`) pour éviter les conflits de dépendances avec les bibliothèques du système d'exploitation.
2. **Gestion Audio :** S'assurer que le serveur audio sous-jacent (PipeWire/PulseAudio) attribue correctement le périphérique de capture par défaut, la commande `ExecStartPre` dans systemd garantissant le rétablissement du gain du microphone à 100% au lancement.
3. **Optimisation du Vocabulaire :** Configurer le dictionnaire de correction de Whisper (`custom vocabulary`) pour injecter les termes techniques spécifiques et acronymes propres aux projets de Laura, réduisant ainsi le taux d'erreur de transcription.