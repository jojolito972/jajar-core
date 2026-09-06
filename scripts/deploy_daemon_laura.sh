#!/usr/bin/env bash
# scripts/deploy_daemon_laura.sh — Installation du démon macOS launchd pour le bot Laura Puntillo

set -euo pipefail

PLIST_NAME="com.jajar.laura_puntillo.plist"
TARGET_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$TARGET_DIR/$PLIST_NAME"
PROJECT_DIR="/Users/denmac/Assistant_IA/jarvis"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"

mkdir -p "$TARGET_DIR"
mkdir -p "$PROJECT_DIR/logs"

# Déchargement si existant
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Génération du fichier plist launchd
cat << EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jajar.laura_puntillo</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>$PROJECT_DIR/automation/bot_laura_puntillo.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/laura_puntillo.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/laura_puntillo_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF

chmod 644 "$PLIST_PATH"
launchctl load "$PLIST_PATH"

echo "✅ Démon macOS 'com.jajar.laura_puntillo' installé et démarré en tâche de fond 24/7."
echo "📋 Logs disponibles dans : $PROJECT_DIR/logs/laura_puntillo.log"
