"""Évaluation sur jeu de test gelé : matrice de confusion, P/R/F1, faux positifs/h, latence."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .gate import AlertGate
from .model import LoadedModel, frame_to_matrix, score

STEP = 5.0


def _ratio(num: float, den: float):
    return None if den == 0 else num / den  # indéfini explicitement si dénominateur nul


def _episodes(labels: np.ndarray) -> list[tuple[int, int]]:
    out, start = [], None
    for i, flag in enumerate(labels):
        if flag and start is None:
            start = i
        if not flag and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(labels) - 1))
    return out


def evaluate(model: LoadedModel, frame: pd.DataFrame, consecutive: int = 2) -> dict:
    """Évalue par session (run_id) pour ne jamais enchaîner des fenêtres de sessions différentes."""
    tp = fp = fn = tn = 0
    false_alerts = hours_normal = 0.0
    latencies: list[float] = []
    missed = episodes_total = 0
    all_scores: list[float] = []
    for _, run in frame.groupby("run_id", sort=True):
        run = run.sort_values("timestamp")
        scores = score(model.pipeline, frame_to_matrix(run))
        all_scores.extend(scores.tolist())
        labels = run["label_degraded"].to_numpy(dtype=int)
        times = run["timestamp"].to_numpy(dtype=float)
        raw = scores < model.threshold
        tp += int(((raw == 1) & (labels == 1)).sum())
        fp += int(((raw == 1) & (labels == 0)).sum())
        fn += int(((raw == 0) & (labels == 1)).sum())
        tn += int(((raw == 0) & (labels == 0)).sum())
        gate = AlertGate(consecutive=consecutive)
        alerts = [i for i, flag in enumerate(raw) if gate.update(bool(flag), float(times[i]))]
        for start, end in _episodes(labels):
            episodes_total += 1
            hit = [i for i in alerts if start <= i <= end]
            if hit:
                latencies.append(float(times[hit[0]] - times[start]) + STEP)
            else:
                missed += 1
        false_alerts += sum(1 for i in alerts if labels[i] == 0)
        hours_normal += float((labels == 0).sum()) * STEP / 3600.0
    precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
    f1 = (
        None
        if precision is None or recall is None or precision + recall == 0
        else 2 * precision * recall / (precision + recall)
    )
    return {
        "n_windows": int(len(frame)),
        "n_degraded": int(tp + fn),
        "threshold": model.threshold,
        "confusion": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_alerts": int(false_alerts),
        "false_alerts_per_hour": _ratio(false_alerts, hours_normal),
        "episodes": episodes_total,
        "episodes_missed": missed,
        "detection_latency_s": {
            "n": len(latencies),
            "p50": float(np.percentile(latencies, 50)) if latencies else None,
            "p95": float(np.percentile(latencies, 95)) if latencies else None,
        },
        "score_min": float(min(all_scores)) if all_scores else None,
        "score_max": float(max(all_scores)) if all_scores else None,
        "targets": {"recall>=0.8": None, "precision>=0.8": None, "latency<=15s": None},
    }


def check_targets(result: dict) -> dict:
    """Compare aux cibles expérimentales de ML_DESIGN ; None = non évaluable (échantillon vide)."""
    p95 = result["detection_latency_s"]["p95"]
    return {
        "recall>=0.8": None if result["recall"] is None else result["recall"] >= 0.8,
        "precision>=0.8": None if result["precision"] is None else result["precision"] >= 0.8,
        "latency<=15s": None if p95 is None else p95 <= 15.0,
    }


def render_markdown(title: str, manifest: dict, validation: dict, test: dict, notes: str) -> str:
    def fmt(value):
        return (
            "indéfini" if value is None else (f"{value:.3f}" if isinstance(value, float) else value)
        )

    lines = [f"# {title}", "", notes, ""]
    lines += ["## Modèle", ""]
    for key in ("model_version", "artifact_sha256", "dataset_sha256", "threshold", "sklearn"):
        lines.append(f"- {key} : `{manifest.get(key)}`")
    lines.append(
        f"- données d'entraînement synthétiques : **{manifest['synthetic_training_data']}**"
    )
    for label, res in (("Validation", validation), ("Test gelé", test)):
        c = res["confusion"]
        lines += [
            "",
            f"## {label}",
            "",
            f"Fenêtres : {res['n_windows']} (dégradées : {res['n_degraded']})",
            "",
        ]
        lines += ["| | Prédit anormal | Prédit normal |", "|---|---|---|"]
        lines += [
            f"| Dégradé | {c['TP']} (TP) | {c['FN']} (FN) |",
            f"| Normal | {c['FP']} (FP) | {c['TN']} (TN) |",
            "",
        ]
        lines += [
            f"- precision {fmt(res['precision'])}, recall {fmt(res['recall'])}, F1 {fmt(res['f1'])}",
            f"- fausses alertes (après 2 scores consécutifs) : {res['false_alerts']} "
            f"({fmt(res['false_alerts_per_hour'])} /h)",
            f"- épisodes : {res['episodes']} dont {res['episodes_missed']} manqués ; "
            f"latence de détection p50 {fmt(res['detection_latency_s']['p50'])} s, "
            f"p95 {fmt(res['detection_latency_s']['p95'])} s (n={res['detection_latency_s']['n']})",
        ]
    lines += ["", "## Cibles expérimentales (ML_DESIGN)", ""]
    for key, value in check_targets(test).items():
        lines.append(
            f"- {key} : {'atteinte' if value else 'NON atteinte' if value is False else 'non évaluable'}"
        )
    return "\n".join(lines) + "\n"
