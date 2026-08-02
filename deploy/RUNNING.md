# Running ChatLink

Everything here assumes the repo root and an active venv:

```bash
cd /path/to/ChatLink
source venv/bin/activate
```

---

## Autostart

Installs systemd **user** services so the bot and dashboard come up on their
own. User services (not system services) because they need your `.env`, your
venv, and your home directory — running them as root would be more privilege
for no benefit.

```bash
./deploy/install.sh
```

Then:

```bash
./deploy/install.sh --status      # what's running
./deploy/install.sh --remove      # uninstall everything
```

Day to day:

```bash
systemctl --user restart chatlink-bot
systemctl --user stop chatlink-dashboard
journalctl --user -u chatlink-bot -f          # live logs
journalctl --user -u chatlink-bot --since today
```

### Adding a service later

Add a line to `deploy/services.conf` and re-run the installer. No unit files to
write by hand.

```
name | description | command
```

For example:

```
scraper | Nightly PDF scraper | python3 tools/scrape.py
```

Scheduled jobs go in `deploy/backup.conf` instead, with a fifth field:

```
name | description | command | oncalendar
```

`oncalendar` uses systemd syntax — `daily`, `hourly`, `*-*-* 03:00:00`,
`Mon *-*-* 09:00`.

### Two things the installer handles

**The drive.** The repo lives on a secondary drive. systemd will happily start a
service before that drive mounts, and it will fail. The installer detects the
mount point and adds `RequiresMountsFor=`, so systemd waits.

**Logout.** User services normally die when you log out. `loginctl enable-linger`
keeps them alive, which is what you want for something that captures messages.
The installer enables it; if it can't, it tells you the sudo command.

### If a service won't start

```bash
systemctl --user status chatlink-bot
journalctl --user -u chatlink-bot -n 50
```

Most common causes: venv missing or moved, `.env` missing `DISCORD_TOKEN`, or the
drive not mounted.

---

## Backups

```bash
python3 tools/backup.py                    # write one now
python3 tools/backup.py --list
python3 tools/backup.py --restore backups/learning-20260802-0300.tar.gz
```

Runs automatically at 3am once the installer is in place. `Persistent=true` means
that if the laptop was off at 3am, it runs shortly after next boot instead of
skipping.

Keeps the last 14, prunes older. Change with `LEARNING_BACKUP_KEEP` in `.env`.

### What actually needs backing up

Most of the database is reproducible — delete it, run `tools/backfill.py`, and
messages, labels and topics all come back, because Discord still holds every
message and classification is deterministic.

Three things are not reproducible:

- **your `!learn fix` corrections** (`label_source='human'`) — the training
  signal for any future classifier
- `data/learning/channels.json` — the channel id mapping
- `data/syllabus.json` — if you've edited it

All three go into every backup.

Backups use SQLite's online backup API, not a file copy. A plain `cp` of a WAL
database while the bot is writing can produce a corrupt archive that looks fine
until you need it.

---

## Backfill

Replays Discord history into the database.

```bash
python3 tools/backfill.py --all --dry-run     # count first
python3 tools/backfill.py --all
python3 tools/backfill.py --channel 123456789
```

Safe to run repeatedly — ingestion is idempotent on `(source, external_id)`, so
an existing message is updated rather than duplicated.

This is also the recovery path when there's no backup: delete `learning.db`,
start the bot once to recreate the schema, run backfill. You get everything back
except manual corrections.

---

## Dashboard on your phone

The dashboard binds to `127.0.0.1` deliberately — this is your data and it
should not be listening on your network. Tailscale gives your phone access
without opening a port to the internet.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Install Tailscale on your phone, sign in with the same account, and both devices
join a private network.

Then bind the dashboard to the Tailscale interface. In `.env`:

```
LEARNING_API_HOST=0.0.0.0
```

```bash
systemctl --user restart chatlink-dashboard
tailscale ip -4        # e.g. 100.x.y.z
```

On your phone: `http://100.x.y.z:8787`

Only devices on your tailnet can reach it. Nothing is exposed publicly, and
there's no port forwarding — which matters because Jio's CGNAT makes port
forwarding impossible anyway.

**The laptop has to be awake.** Tailscale doesn't change that. If you want the
dashboard reachable while the lid is shut, you'd need to disable suspend, which
is a battery tradeoff rather than a config problem.

---

## Environment variables

All optional; defaults in brackets.

| Variable | Purpose |
|---|---|
| `DISCORD_TOKEN` | required |
| `LEARNING_DB_PATH` | database location [`data/learning/learning.db`] |
| `LEARNING_SYLLABUS` | syllabus file [`data/syllabus.json`] |
| `LEARNING_CLASSIFIER` | which classifier to use [`rules`] |
| `LEARNING_API_HOST` | dashboard bind address [`127.0.0.1`] |
| `LEARNING_API_PORT` | dashboard port [`8787`] |
| `LEARNING_BACKUP_KEEP` | backups to retain [`14`] |
| `LEARNING_TZ_OFFSET_MINUTES` | local timezone offset [`330`, IST] |
| `LOG_LEVEL` | `DEBUG` for verbose output [`INFO`] |
