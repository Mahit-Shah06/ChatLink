#!/usr/bin/env bash
#
# Install ChatLink autostart as systemd *user* services.
#
#   bash deploy/install-autostart.sh
#
# User services rather than system services on purpose: they run as you, can
# read your .env and your venv without permission games, and never need sudo.
# The one sudo-ish step is enabling linger, which lets them start at boot
# instead of waiting for you to log in — the script asks before doing that.
#
# Everything here is idempotent. Re-run it after changing a unit file.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNITS="$HOME/.config/systemd/user"

echo "Repo: $REPO"

# ----------------------------------------------------------------- checks
if [ ! -f "$REPO/main.py" ]; then
  echo "ERROR: main.py not found in $REPO"
  exit 1
fi

if [ ! -x "$REPO/venv/bin/python3" ]; then
  echo "ERROR: no venv at $REPO/venv"
  echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [ ! -f "$REPO/.env" ]; then
  echo "ERROR: no .env — the bot needs DISCORD_TOKEN"
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "ERROR: systemd not available on this machine."
  exit 1
fi

VENV="$REPO/venv"

# The repo may sit on a removable drive. If it does, the units need
# RequiresMountsFor pointing at the *mount point*, not the repo path, or
# systemd starts them before the drive appears.
MOUNT="$(df --output=target "$REPO" | tail -1)"
echo "Mount point: $MOUNT"
if [ "$MOUNT" != "/" ] && [ "$MOUNT" != "$HOME" ]; then
  echo "  (removable or separate volume — units will wait for it)"
fi

# ------------------------------------------------------------ install units
mkdir -p "$UNITS"

for unit in chatlink.target chatlink-bot.service chatlink-dashboard.service \
            chatlink-backup.service chatlink-backup.timer; do
  sed -e "s|__REPO__|$REPO|g" \
      -e "s|__VENV__|$VENV|g" \
      -e "s|RequiresMountsFor=$REPO|RequiresMountsFor=$MOUNT|g" \
      "$REPO/deploy/$unit" > "$UNITS/$unit"
  echo "  installed $unit"
done

cp "$REPO/deploy/example-myprogram.service.txt" "$UNITS/" 2>/dev/null || true

systemctl --user daemon-reload

# ------------------------------------------------------------- ldb launcher
mkdir -p "$HOME/.local/bin"
install -m 755 "$REPO/deploy/ldb" "$HOME/.local/bin/ldb"
install -m 755 "$REPO/deploy/clhelp" "$HOME/.local/bin/clhelp"
echo "  installed ldb    -> ~/.local/bin/ldb"
echo "  installed clhelp -> ~/.local/bin/clhelp"

if ! echo "$PATH" | tr ':' '\n' | grep -qx "$HOME/.local/bin"; then
  echo "  NOTE: ~/.local/bin is not on your PATH. Add this to ~/.bashrc:"
  echo '        export PATH="$HOME/.local/bin:$PATH"'
fi

# --------------------------------------------------------- friendly hostname
# A hosts entry so the dashboard is http://learning:8787 rather than an IP.
# This is the only step that needs sudo, and it is skipped if declined.
if ! grep -qE "^127\.0\.0\.1[[:space:]]+learning( |$)" /etc/hosts 2>/dev/null; then
  echo
  echo "Add 'learning' as a local hostname? (needs sudo, one line in /etc/hosts)"
  read -rp "  [Y/n] " hosts_reply
  if [[ ! "$hosts_reply" =~ ^[Nn] ]]; then
    echo "127.0.0.1 learning" | sudo tee -a /etc/hosts >/dev/null \
      && echo "  added: http://learning:$(grep -oP 'LEARNING_API_PORT.*?\K[0-9]+' "$REPO/.env" 2>/dev/null || echo 8787)" \
      || echo "  skipped (sudo failed)"
  fi
fi

# ------------------------------------------------------------------ enable
systemctl --user enable chatlink.target >/dev/null
systemctl --user enable chatlink-bot.service >/dev/null
systemctl --user enable chatlink-dashboard.service >/dev/null
systemctl --user enable chatlink-backup.timer >/dev/null

echo
echo "Services enabled."

# -------------------------------------------------------------- boot start
if ! loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=yes"; then
  echo
  echo "To start these at boot without you logging in, linger must be enabled:"
  echo "    sudo loginctl enable-linger $USER"
  echo "Without it they start when you log in, which is usually fine for a laptop."
fi

# ------------------------------------------------------------------- start
echo
read -rp "Start everything now? [Y/n] " reply
if [[ ! "$reply" =~ ^[Nn] ]]; then
  systemctl --user start chatlink.target
  systemctl --user start chatlink-backup.timer
  sleep 2
  echo
  systemctl --user --no-pager --lines=0 status chatlink-bot.service \
    | head -4 || true
  echo
  systemctl --user --no-pager --lines=0 status chatlink-dashboard.service \
    | head -4 || true
fi

cat <<INFO

------------------------------------------------------------------
Everything runs under one target, so this is the whole interface:

  systemctl --user start chatlink.target      start all
  systemctl --user stop chatlink.target       stop all
  systemctl --user restart chatlink-bot       restart just the bot

  journalctl --user -u chatlink-bot -f        live bot logs
  journalctl --user -u chatlink-dashboard -f  live dashboard logs
  systemctl --user list-timers                when the backup next runs

  clhelp                                      every command, grouped
  clhelp check                                live status of everything

  Dashboard: http://127.0.0.1:8787

Adding another program later:
  cp ~/.config/systemd/user/example-myprogram.service.txt \\
     ~/.config/systemd/user/myprogram.service
  edit it, then:
  systemctl --user daemon-reload
  systemctl --user enable --now myprogram.service

It joins chatlink.target automatically, so it starts and stops with
everything else. No existing file needs changing.
------------------------------------------------------------------
INFO
