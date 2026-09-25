#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/mnt/shared4/LLAMACPP/models/wisperalternative/whisper.cpp/voice-project"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
RUN_FILE="$PROJECT_DIR/run.py"
BIN_DIR="$HOME/.local/bin"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/speech-typing.service"

echo "=== Speech Typing setup ==="

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: Python virtual environment not found:"
    echo "  $VENV_PYTHON"
    echo
    echo "Create/fix the venv first, then run this installer again."
    exit 1
fi

if [[ ! -f "$RUN_FILE" ]]; then
    echo "ERROR: run.py not found:"
    echo "  $RUN_FILE"
    exit 1
fi

mkdir -p "$BIN_DIR" "$SERVICE_DIR"

# One-command launcher: type 'voice' in any new terminal.
cat > "$BIN_DIR/voice" <<'EOF'
#!/usr/bin/env bash
exec "/mnt/shared4/LLAMACPP/models/wisperalternative/whisper.cpp/voice-project/.venv/bin/python" "/mnt/shared4/LLAMACPP/models/wisperalternative/whisper.cpp/voice-project/run.py" "$@"
EOF
chmod +x "$BIN_DIR/voice"

# User systemd service: starts automatically when the KDE user session starts.
cat > "$SERVICE_FILE" <<'EOF'
[Unit]
Description=Local Speech Typing Voice Input
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
WorkingDirectory=/mnt/shared4/LLAMACPP/models/wisperalternative/whisper.cpp/voice-project
ExecStart=/mnt/shared4/LLAMACPP/models/wisperalternative/whisper.cpp/voice-project/.venv/bin/python /mnt/shared4/LLAMACPP/models/wisperalternative/whisper.cpp/voice-project/run.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "speech-typing.service"

# Make the launcher immediately available in this shell too.
export PATH="$BIN_DIR:$PATH"

echo
echo "=== Setup complete ==="
echo
echo "Terminal command:"
echo "  voice"
echo
echo "Autostart:"
echo "  ENABLED — Speech Typing starts automatically with your KDE session."
echo
echo "Service status:"
systemctl --user --no-pager --full status "speech-typing.service" || true
echo
echo "If 'voice' is not found in a future terminal, add ~/.local/bin to PATH:"
echo '  echo '''export PATH="$HOME/.local/bin:$PATH"''' >> ~/.bashrc'
echo "  source ~/.bashrc"
echo
echo "Useful commands:"
echo "  systemctl --user status speech-typing.service"
echo "  systemctl --user restart speech-typing.service"
echo "  systemctl --user stop speech-typing.service"
echo "  systemctl --user disable speech-typing.service"
echo "  journalctl --user -u speech-typing.service -f"
