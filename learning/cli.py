"""
Command line interface. Use and test the engine without Discord.

    python -m learning.cli serve            dashboard on 127.0.0.1:8787
    python -m learning.cli try "text"       classify one message
    python -m learning.cli stats
    python -m learning.cli reclassify       re-run over all history
"""

from __future__ import annotations

import argparse
import json
import sys

from .capture import CaptureEngine
from .models import ChannelContext, IncomingMessage


def cmd_serve(args) -> int:
    from .api.server import serve
    serve(port=args.port or 8787, open_browser=args.open)
    return 0


def cmd_try(args) -> int:
    eng = CaptureEngine()
    ctx = ChannelContext(external_id="cli", label=args.channel or "cli",
                         subject_key=args.subject)
    p = eng.process(IncomingMessage(content=args.text, source="cli", channel=ctx))
    c = p.classification
    print(f"\n  text       {args.text}")
    print(f"  label      {c.label.value}  ({c.confidence:.2f})")
    if c.secondary_label:
        print(f"  runner-up  {c.secondary_label.value}")
    print(f"  topics     {', '.join(f'{t.name}[{t.confidence:.2f}]' for t in p.topics) or '-'}")
    if p.candidate_terms:
        print(f"  unknown    {', '.join(p.candidate_terms)}")
    print(f"  evidence   {', '.join(c.evidence) or '-'}\n")
    return 0


def cmd_stats(args) -> int:
    eng = CaptureEngine()
    st = eng.stats()
    s = st["summary"]
    print(f"\n  messages    {s['messages']}")
    print(f"  active days {s['active_days']}  (streak {st['streak']})")
    print(f"  attachments {s['attachments']}")
    print(f"  classifier  {st['classifier']}")
    print(f"  taxonomy    {st['taxonomy']}\n")
    for row in st["labels"]:
        if row["label"]:
            print(f"    {row['label']:<10} {row['count']:>4}   avg conf {row['avg_confidence']:.2f}")
    weak = eng.repo.weak_topics()
    if weak:
        print("\n  needs attention:")
        for t in weak[:5]:
            print(f"    {t['name']:<28} {t['questions']}q / {t['notes']}n")
    print()
    return 0


def cmd_reclassify(args) -> int:
    eng = CaptureEngine()
    r = eng.reclassify_all(args.classifier)
    print(f"Re-labelled {r['reclassified']} messages with {r['classifier']}@{r['version']}.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="learning", description="ChatLink Learning Engine")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("serve", help="run the local dashboard")
    s.add_argument("--port", type=int)
    s.add_argument("--open", action="store_true")
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("try", help="classify one message without saving")
    s.add_argument("text")
    s.add_argument("--channel")
    s.add_argument("--subject")
    s.set_defaults(func=cmd_try)

    s = sub.add_parser("stats", help="print a summary")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("reclassify", help="re-run classification over history")
    s.add_argument("--classifier")
    s.set_defaults(func=cmd_reclassify)

    return p.parse_args(argv).func(p.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
