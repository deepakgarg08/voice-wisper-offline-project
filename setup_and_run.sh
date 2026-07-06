#!/usr/bin/env bash
# One-shot setup + run for speech_typing.
#
# - Creates the Python venv and installs dependencies if missing.
# - Checks/fixes the two system prerequisites (ydotoold socket permissions,
#   'input' group membership). Anything needing your admin password is
#   announced explicitly before it runs.
# - Then runs the app.
#
# Safe to re-run any time -- every step is a no-op if already satisfied.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
YDOTOOL_SOCKET="/tmp/.ydotool_socket"

log()  { echo "[setup] $*"; }
warn() { echo "[setup] WARNING: $*" >&2; }

# --- 1. ydotool + ydotoold installed? ---
if ! command -v ydotool >/dev/null 2>&1 || ! command -v ydotoold >/dev/null 2>&1; then
    cat >&2 <<EOF

[setup] ydotool/ydotoold is not installed. This requires your admin password.
[setup] Please run the following yourself, then re-run this script:

    sudo dnf install ydotool

EOF
    exit 1
fi
log "ydotool and ydotoold are installed."

# --- 2. ydotoold running, with a group-accessible socket? ---
NEEDS_SERVICE_FIX=0
if ! systemctl is-active --quiet ydotool.service; then
    NEEDS_SERVICE_FIX=1
elif [ -S "$YDOTOOL_SOCKET" ]; then
    # Socket must be group 'input' (or otherwise not root-only) to be usable.
    SOCK_GROUP="$(stat -c '%G' "$YDOTOOL_SOCKET")"
    SOCK_PERM="$(stat -c '%a' "$YDOTOOL_SOCKET")"
    if [ "$SOCK_GROUP" != "input" ] || [ "${SOCK_PERM: -1}" -lt 6 ]; then
        NEEDS_SERVICE_FIX=1
    fi
fi

if [ "$NEEDS_SERVICE_FIX" -eq 1 ]; then
    cat >&2 <<EOF

[setup] ydotoold needs to be (re)configured so your user can reach its
[setup] socket. This requires your admin password. About to run:

    sudo mkdir -p /etc/systemd/system/ydotool.service.d
    sudo tee /etc/systemd/system/ydotool.service.d/override.conf
    sudo systemctl daemon-reload
    sudo systemctl enable --now ydotool.service

EOF
    read -r -p "[setup] Continue? [y/N] " reply
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        log "Aborted by user."
        exit 1
    fi

    sudo mkdir -p /etc/systemd/system/ydotool.service.d
    sudo tee /etc/systemd/system/ydotool.service.d/override.conf >/dev/null <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/ydotoold --socket-perm=0660 --socket-own=root:input
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable --now ydotool.service
    log "ydotool.service reconfigured and restarted."
else
    log "ydotoold is running with a usable socket."
fi

# --- 3. user in 'input' group? ---
# Two things can be true independently: whether /etc/group has been updated
# (id -nG "$USER"), and whether *this* shell session's live credentials
# reflect it (id -nG with no args) -- group changes only apply to new
# sessions, so a shell open from before the usermod won't see it yet either
# way.
if ! id -nG "$USER" | grep -qw input; then
    cat >&2 <<EOF

[setup] Your user is not in the 'input' group, which is required to read
[setup] keyboard events (for the push-to-talk hotkey). This requires your
[setup] admin password. About to run:

    sudo usermod -aG input "$USER"

EOF
    read -r -p "[setup] Continue? [y/N] " reply
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        log "Aborted by user."
        exit 1
    fi

    sudo usermod -aG input "$USER"
    log "Added '$USER' to the 'input' group."
fi

if id -nG | grep -qw input; then
    IN_INPUT_GROUP=1
else
    log "'input' group is granted but not active in this shell session yet."
    IN_INPUT_GROUP=0
fi

# --- 4. Python venv + dependencies ---
if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtualenv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
log "Installing/updating Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# --- 5. Run ---
# A freshly-added group membership only applies to new login sessions. `sg`
# re-executes the given command as if that group were already active, so we
# don't have to make you log out and back in just to test this.
if [ "${IN_INPUT_GROUP:-1}" -eq 0 ]; then
    log "Group membership was just added -- running under 'sg input' so it's active immediately."
    log "(A full logout/login will make this permanent for future sessions.)"
    exec sg input -c "'$VENV_DIR/bin/python3' '$SCRIPT_DIR/run.py'"
else
    log "Starting speech_typing..."
    exec python3 run.py
fi
