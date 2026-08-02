"""
Backfill the Learning Engine from existing Discord history.

Discord is the write-ahead log; the SQLite file is a projection of it. This
script is what makes that literally true — everything you have ever posted in a
mapped channel can be replayed into the database at any time.

    python3 tools/backfill.py --all              every mapped channel
    python3 tools/backfill.py --channel 12345    one channel
    python3 tools/backfill.py --all --dry-run    show what would happen

Safe to run repeatedly: ingestion is idempotent on (source, external_id), so a
message already stored is updated rather than duplicated. That means this is
also the disaster recovery path — delete learning.db, run this, and you are back
to where you were apart from any manual !learn fix corrections.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import discord
from dotenv import load_dotenv

from learning import Attachment, IncomingMessage, get_engine

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("backfill")


class Backfiller(discord.Client):
    def __init__(self, channel_ids, limit, dry_run):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)
        self.channel_ids = channel_ids
        self.limit = limit
        self.dry_run = dry_run
        self.engine = get_engine()

    async def on_ready(self):
        log.info("connected as %s", self.user)
        total_seen = total_stored = 0

        try:
            for cid in self.channel_ids:
                try:
                    channel = self.get_channel(cid) or await self.fetch_channel(cid)
                except (discord.NotFound, discord.Forbidden):
                    log.warning("channel %s unreachable — skipping", cid)
                    continue

                name = getattr(channel, "name", str(cid))
                category = channel.category.name if getattr(channel, "category", None) else ""
                ctx = self.engine.channels.resolve(channel.id, name, category)

                if ctx is None:
                    log.info("  #%s is not mapped — skipping", name)
                    continue
                if not ctx.captured:
                    log.info("  #%s is a reference channel — skipping", name)
                    continue

                seen = stored = 0
                log.info("reading #%s …", name)

                async for m in channel.history(limit=self.limit, oldest_first=True):
                    if m.author.bot:
                        continue
                    seen += 1

                    incoming = IncomingMessage(
                        content=m.content or "",
                        source="discord",
                        external_id=str(m.id),
                        author_id=str(m.author.id),
                        author_name=m.author.display_name,
                        reply_to=str(m.reference.message_id) if m.reference else None,
                        channel=ctx,
                        attachments=[
                            Attachment(a.filename or "", a.url or "",
                                       a.content_type or "", a.size or 0)
                            for a in m.attachments
                        ],
                        created_at=m.created_at,
                        metadata={"channel_name": name, "jump_url": m.jump_url,
                                  "backfilled": True},
                    )

                    if self.dry_run:
                        if self.engine.should_capture(incoming):
                            stored += 1
                        continue

                    if await asyncio.to_thread(self.engine.capture, incoming):
                        stored += 1
                        if stored % 200 == 0:
                            log.info("    %d stored…", stored)

                log.info("  #%-24s %4d read, %4d captured", name, seen, stored)
                total_seen += seen
                total_stored += stored

        finally:
            verb = "would capture" if self.dry_run else "captured"
            log.info("done — %d read, %d %s", total_seen, total_stored, verb)
            if not self.dry_run:
                s = self.engine.repo.summary()
                log.info("database now holds %d messages across %d day(s)",
                         s["messages"], s["active_days"])
            await self.close()


def main() -> int:
    p = argparse.ArgumentParser(description="Replay Discord history into the Learning Engine")
    p.add_argument("--channel", type=int, action="append", default=[],
                   help="channel id (repeatable)")
    p.add_argument("--all", action="store_true", help="every mapped channel")
    p.add_argument("--limit", type=int, default=None,
                   help="max messages per channel (default: no limit)")
    p.add_argument("--dry-run", action="store_true", help="count without writing")
    args = p.parse_args()

    if not args.channel and not args.all:
        p.error("give --channel <id> or --all")

    engine = get_engine()
    if args.all:
        ids = [int(c.external_id) for c in engine.channels.all()
               if c.captured and c.external_id.isdigit()]
        if not ids:
            print("No channels mapped yet. Run !learn setup in Discord first.")
            return 1
    else:
        ids = args.channel

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("DISCORD_TOKEN is not set in .env")
        return 1

    if args.dry_run:
        log.info("DRY RUN — nothing will be written")

    Backfiller(ids, args.limit, args.dry_run).run(token, log_handler=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
