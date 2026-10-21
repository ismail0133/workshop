"""Outils en ligne de commande : synth | collect | label | train | evaluate."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

from .dataset import load_dataset, write_bundle
from .features import FEATURE_NAMES
from .prom import Prometheus, PrometheusError


def cmd_synth(args) -> int:
    from .synthetic import generate

    frame, splits = generate(args.seed)
    manifest = write_bundle(
        Path(args.out),
        frame,
        splits,
        {"synthetic": True, "generator": "ml_app.synthetic", "seed": args.seed},
    )
    print(json.dumps(manifest, indent=2))
    return 0


def cmd_collect(args) -> int:
    """Collecte réelle depuis Prometheus (cadence 5 s). Les labels sont appliqués ensuite."""
    prom = Prometheus(args.prometheus)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    skipped: dict[str, int] = {}
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["run_id", "timestamp", *FEATURE_NAMES, "label_degraded"])
        deadline = time.time() + args.duration
        while time.time() < deadline:
            started = time.time()
            try:
                window = prom.extract_window(args.window)
            except PrometheusError as exc:
                skipped[f"PROMETHEUS_{exc}"] = skipped.get(f"PROMETHEUS_{exc}", 0) + 1
            else:
                if window.valid:
                    writer.writerow([args.run_id, f"{window.end:.3f}", *window.vector(), ""])
                    handle.flush()
                else:
                    skipped[window.reason] = skipped.get(window.reason, 0) + 1
            time.sleep(max(0.0, args.step - (time.time() - started)))
    print(json.dumps({"run_id": args.run_id, "out": str(out), "fenetres_invalides": skipped}))
    return 0


def cmd_label(args) -> int:
    """Applique le journal de scénario (intervalles réellement dégradés) — pas la prédiction."""
    import pandas as pd

    frame = pd.read_csv(args.csv)
    journal = json.loads(Path(args.journal).read_text())
    frame["label_degraded"] = 0
    for item in journal["degraded"]:
        mask = (frame["timestamp"] >= item["start"]) & (frame["timestamp"] <= item["end"])
        frame.loc[mask, "label_degraded"] = 1
    frame.to_csv(args.out, index=False)
    print(f"{int(frame['label_degraded'].sum())} fenêtres dégradées sur {len(frame)}")
    return 0


def cmd_train(args) -> int:
    from .train import train

    report = train(Path(args.dataset), Path(args.out), args.version, args.synthetic)
    print(json.dumps({"targets_test": report["targets_test"], "test": report["test"]["confusion"]}))
    return 0


def cmd_evaluate(args) -> int:
    from .dataset import apply_splits
    from .evaluate import check_targets, evaluate
    from .model import load_verified

    model = load_verified(Path(args.model), os.getenv("MODEL_SHA256"))
    frame = load_dataset(Path(args.dataset) / "dataset.csv")
    splits = json.loads((Path(args.dataset) / "splits.json").read_text())
    result = evaluate(model, apply_splits(frame, splits)[args.split])
    result["targets_check"] = check_targets(result)
    print(json.dumps(result, indent=2))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ml_app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("synth", help="jeu SYNTHÉTIQUE de développement (non probant)")
    p.add_argument("--out", default="artifacts/datasets/synthetic")
    p.add_argument("--seed", type=int, default=7)
    p.set_defaults(func=cmd_synth)
    p = sub.add_parser("collect", help="collecte réelle depuis Prometheus")
    p.add_argument("--prometheus", default=os.getenv("PROMETHEUS_URL", "http://prometheus:9090"))
    p.add_argument("--run-id", required=True)
    p.add_argument("--duration", type=int, required=True)
    p.add_argument("--window", type=int, default=15)
    p.add_argument("--step", type=float, default=5.0)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_collect)
    p = sub.add_parser("label", help="étiquette un CSV avec le journal de scénario")
    p.add_argument("--csv", required=True)
    p.add_argument("--journal", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_label)
    p = sub.add_parser("train", help="entraîne, calibre le seuil (validation), évalue (test)")
    p.add_argument("--dataset", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--synthetic", action="store_true")
    p.set_defaults(func=cmd_train)
    p = sub.add_parser("evaluate", help="évalue un modèle vérifié sur un split")
    p.add_argument("--model", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--split", default="test", choices=["train", "validation", "test"])
    p.set_defaults(func=cmd_evaluate)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
