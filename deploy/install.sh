#!/usr/bin/env bash
#
# Install ChatLink as systemd user services, so everything starts on login.
#
#   ./deploy/install.sh          install / update every service
#   ./deploy/install.sh --status show what's running
#   ./deploy/install.sh --remove uninstall everything
#
# Services are generated from deploy/services.conf and deploy/backup.conf.
# Adding something new later means adding a line there and re-running this —
# no editing of unit files by hand.
#
# Two things this handles that a naive unit file does not:
#
#   1. The repo lives on a secondary drive. systemd will happily start the bot
#      before that drive is mounted, and it will fail. RequiresMountsFor= makes
#      systemd wait for the mount instead.
#   2. User services normally stop when you log out. `loginctl enable-linger`
#      keeps them running, which is what you want for something that captures
#      messages.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
VENV="$REPO/venv"
PREFIX="chatlink"

c_ok=$'\033[32m'; c_warn=$'\033[33m'; c_err=$'\033[31m'; c_off=$'\033[0m'

# Trim leading/trailing whitespace without xargs, which treats quotes specially
# and would mangle any description containing an apostrophe.
trim() { local v="$1"; v="${v#"${v%%[![:space:]]*}"}"; v="${v%"${v##*[![:space:]]}"}"; printf '%s' "$v"; }

# ---------------------------------------------------------------- preflight
if [ ! -f "$REPO/main.py" ]; then
  echo "${c_err}ERROR${c_off} main.py not found in $REPO"
  exit 1
fi

if [ ! -x "$VENV/bin/python3" ]; then
  echo "${c_err}ERROR${c_off} no virtualenv at $VENV"
  echo "  create one first:  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if ! command -v systemctl >/dev/null; then
  echo "${c_err}ERROR${c_off} systemd not found — this script is for systemd Linux only."
  exit 1
fi

# ------------------------------------------------------------------ actions
list_units() { find "$UNIT_DIR" -name "$PREFIX-*.service" -o -name "$PREFIX-*.timer" 2>/dev/null | sort; }

if [ "${1:-}" = "--status" ]; then
  echo "ChatLink services:"
  echo
  for unit in $(list_units); do
    name="$(basename "$unit")"
    state="$(systemctl --user is-active "$name" 2>/dev/null || echo inactive)"
    enabled="$(systemctl --user is-enabled "$name" 2>/dev/null || echo disabled)"
    case "$state" in
      active)  colour="$c_ok" ;;
      failed)  colour="$c_err" ;;
      *)       colour="$c_warn" ;;
    esac
    printf "  %-30s %s%-10s%s %s\n" "$name" "$colour" "$state" "$c_off" "$enabled"
  done
  echo
  echo "Logs:     journalctl --user -u ${PREFIX}-bot -f"
  echo "Restart:  systemctl --user restart ${PREFIX}-bot"
  exit 0
fi

if [ "${1:-}" = "--remove" ]; then
  for unit in $(list_units); do
    name="$(basename "$unit")"
    systemctl --user disable --now "$name" 2>/dev/null || true
    rm -f "$unit"
    echo "  removed $name"
  done
  systemctl --user daemon-reload
  echo "${c_ok}Done.${c_off} Linger left enabled; disable with: loginctl disable-linger $USER"
  exit 0
fi

# ------------------------------------------------------------------ install
mkdir -p "$UNIT_DIR"
echo "Repo:  $REPO"
echo "Units: $UNIT_DIR"
echo

# The repo is likely on a mounted drive. Find its mount point so systemd can
# wait for it rather than starting into a missing directory.
MOUNT_POINT="$(df --output=target "$REPO" 2>/dev/null | tail -1 || echo /)"
if [ "$MOUNT_POINT" != "/" ]; then
  echo "${c_warn}note${c_off} repo is on $MOUNT_POINT — services will wait for that mount"
  MOUNT_LINE="RequiresMountsFor=$MOUNT_POINT"
else
  MOUNT_LINE=""
fi

installed=0

# ---- long-running services -------------------------------------------------
while IFS='|' read -r name desc cmd; do
  name="$(trim "$name")"; desc="$(trim "$desc")"; cmd="$(trim "$cmd")"
  [ -z "$name" ] && continue
  case "$name" in \#*) continue ;; esac

  unit="$UNIT_DIR/$PREFIX-$name.service"
  cat > "$unit" <<UNIT
[Unit]
Description=$desc
After=network-online.target
Wants=network-online.target
$MOUNT_LINE
# Stop retrying if it fails 5 times in 5 minutes. These directives belong in
# [Unit], not [Service] — systemd ignores them silently in the wrong section.
StartLimitBurst=5
StartLimitIntervalSec=300

[Service]
Type=simple
WorkingDirectory=$REPO
Environment="PATH=$VENV/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=$VENV/bin/$cmd
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$PREFIX-$name

[Install]
WantedBy=default.target
UNIT
  echo "  ${c_ok}service${c_off}  $PREFIX-$name"
  installed=$((installed + 1))
done < "$REPO/deploy/services.conf"

# ---- timers ----------------------------------------------------------------
while IFS='|' read -r name desc cmd schedule; do
  name="$(trim "$name")"; desc="$(trim "$desc")"
  cmd="$(trim "$cmd")"; schedule="$(trim "$schedule")"
  [ -z "$name" ] && continue
  case "$name" in \#*) continue ;; esac

  cat > "$UNIT_DIR/$PREFIX-$name.service" <<UNIT
[Unit]
Description=$desc
$MOUNT_LINE

[Service]
Type=oneshot
WorkingDirectory=$REPO
Environment="PATH=$VENV/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$VENV/bin/$cmd
SyslogIdentifier=$PREFIX-$name
UNIT

  cat > "$UNIT_DIR/$PREFIX-$name.timer" <<UNIT
[Unit]
Description=$desc (scheduled)

[Timer]
OnCalendar=$schedule
# If the laptop was off at the scheduled time, run once it comes back
Persistent=true

[Install]
WantedBy=timers.target
UNIT
  echo "  ${c_ok}timer${c_off}    $PREFIX-$name  ($schedule)"
  installed=$((installed + 1))
done < "$REPO/deploy/backup.conf"

# ---- enable ----------------------------------------------------------------
echo
systemctl --user daemon-reload

for unit in $(list_units); do
  name="$(basename "$unit")"
  systemctl --user enable "$name" >/dev/null 2>&1 || true
  if [[ "$name" == *.timer ]]; then
    systemctl --user restart "$name" >/dev/null 2>&1 || true
  fi
done

# Keep services alive after logout, and start them at boot rather than login.
if ! loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=yes"; then
  echo "Enabling linger (keeps services running when you log out)…"
  loginctl enable-linger "$USER" 2>/dev/null \
    || echo "  ${c_warn}could not enable linger${c_off} — run: sudo loginctl enable-linger $USER"
fi

echo
echo "${c_ok}Installed $installed unit(s).${c_off}"
echo
echo "  Start now:    systemctl --user start ${PREFIX}-bot ${PREFIX}-dashboard"
echo "  Check:        ./deploy/install.sh --status"
echo "  Logs:         journalctl --user -u ${PREFIX}-bot -f"
echo "  Stop:         systemctl --user stop ${PREFIX}-bot"
echo
echo "They will start automatically from now on."
