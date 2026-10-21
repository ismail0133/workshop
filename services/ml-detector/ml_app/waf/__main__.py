"""CLI : python -m ml_app.waf {profile|train|replay|watch}"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .blocklist import Blocklist
from .engine import GateParams, StreamEngine, replay
from .evaluate import render_markdown, train_and_evaluate
from .logs import parse_line, read_requests
from .model import load_verified


def _model(args):
    return load_verified(Path(args.model), args.pinned_sha256 or None)


def _blocklist(args, model) -> Blocklist:
    return Blocklist(Path(args.blocklist), apply=args.apply, max_managed=args.max_managed,
                     normal_user_agents=model.normal_user_agents, never_block=args.never_block or ())


def _params(model) -> GateParams:
    gate = model.manifest["gate"]
    return GateParams(gate["consecutive"], gate["rearm_normal"], gate["cooldown_s"], gate["min_requests"])


def _act(triggers, blocklist: Blocklist, audit: Path | None) -> None:
    for trig in triggers:
        result = blocklist.block(trig.ua, score=trig.score)
        record = {"ts": datetime.fromtimestamp(trig.ts, timezone.utc).isoformat(), "event": "UA_ANOMALY",
                  "ua_token": result.token, "action": result.status, "n_requests": trig.n_requests,
                  "score": round(trig.score, 4), "ua_preview": trig.ua[:80]}
        line = json.dumps(record, ensure_ascii=True)
        print(line)
        if audit:
            with audit.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def cmd_profile(args) -> int:
    requests, stats = read_requests(Path(args.log))
    uas: dict[str, int] = {}
    for r in requests:
        uas[r.ua] = uas.get(r.ua, 0) + 1
    print(json.dumps({"read": stats, "user_agents": sorted(uas.items(), key=lambda kv: -kv[1])[:20]}, indent=2))
    return 0


def cmd_train(args) -> int:
    result = train_and_evaluate(Path(args.log), Path(args.splits), Path(args.out), args.version)
    report = Path(args.report) if args.report else Path(args.out) / "report"
    report.mkdir(parents=True, exist_ok=True)
    (report / "report.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    (report / "report.md").write_text(render_markdown(result), encoding="utf-8")
    print(render_markdown(result))
    return 0


def cmd_replay(args) -> int:
    model = _model(args)
    requests, stats = read_requests(Path(args.log))
    triggers, engine = replay(requests, model, _params(model))
    print(json.dumps({"read": stats, "windows_scored": len(engine.rows), "triggers": len(triggers)}))
    _act(triggers, _blocklist(args, model), Path(args.audit) if args.audit else None)
    return 0


def read_new_lines(path: Path, offset: int) -> tuple[list[str], int]:
    """Lignes COMPLÈTES ajoutées depuis `offset` ; une ligne partielle est relue au passage suivant ; reprise à 0 si le fichier est tronqué."""
    if not path.exists():
        return [], offset
    if path.stat().st_size < offset:
        offset = 0
    with path.open("rb") as handle:
        handle.seek(offset)
        chunk = handle.read()
    complete = chunk[: chunk.rfind(b"\n") + 1]
    return complete.decode("utf-8", errors="replace").splitlines(), offset + len(complete)


def parse_lines(lines) -> tuple[list, int]:
    fresh, rejected = [], 0
    for line in lines:
        if line.strip():
            try:
                fresh.append(parse_line(line))
            except ValueError:
                rejected += 1
    return fresh, rejected


def _stdin_queue() -> "queue.Queue[str]":
    """Lit stdin dans un thread (les tubes Windows ne se prêtent pas à select) : la boucle principale n'est jamais bloquée."""
    lines: queue.Queue[str] = queue.Queue(maxsize=100_000)

    def pump() -> None:
        for raw in sys.stdin:
            try:
                lines.put_nowait(raw)
            except queue.Full:  # surcharge : on abandonne la ligne plutôt que de bloquer le flux
                pass

    threading.Thread(target=pump, daemon=True).start()
    return lines


def cmd_watch(args) -> int:
    """Suit un fichier (--log chemin) ou un flux (--log -) ; ferme les fenêtres ; bloque si --apply."""
    model = _model(args)
    engine = StreamEngine(model, _params(model))
    blocklist, audit = _blocklist(args, model), (Path(args.audit) if args.audit else None)
    stdin = _stdin_queue() if args.log == "-" else None
    offset, rejected = 0, 0
    print(json.dumps({"event": "WATCH_START", "model": model.version, "apply": args.apply}))
    try:
        while True:
            if stdin is not None:
                lines = []
                while not stdin.empty():
                    lines.append(stdin.get_nowait())
            else:
                lines, offset = read_new_lines(Path(args.log), offset)
            fresh, bad = parse_lines(lines)
            rejected += bad
            engine.feed(fresh)
            _act(engine.advance(time.time()), blocklist, audit)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(json.dumps({"event": "WATCH_STOP", "rejected_lines": rejected}))
        return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ml_app.waf")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("profile", help="résumé d'un access.jsonl")
    p.add_argument("--log", required=True)
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("train", help="entraîne, calibre sur la validation, évalue sur le test")
    p.add_argument("--log", required=True)
    p.add_argument("--splits", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--report")
    p.set_defaults(func=cmd_train)

    for name, func, text in (("replay", cmd_replay, "rejoue un journal (simulation par défaut)"),
                             ("watch", cmd_watch, "suit le journal en continu")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--log", required=True)
        p.add_argument("--model", required=True)
        p.add_argument("--pinned-sha256")
        p.add_argument("--blocklist", required=True)
        p.add_argument("--apply", action="store_true", help="écrit réellement dans blocklist.txt (sinon simulation)")
        p.add_argument("--max-managed", type=int, default=20)
        p.add_argument("--never-block", action="append", help="User-Agent à ne jamais bloquer (répétable)")
        p.add_argument("--audit", help="fichier JSONL d'audit des décisions")
        if name == "watch":
            p.add_argument("--interval", type=float, default=5.0)
        p.set_defaults(func=func)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
