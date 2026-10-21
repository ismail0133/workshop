"""Entraînement, calibrage et évaluation du détecteur WAF sur un journal réel.

Méthode (voir docs/ml/ML_REPORT.md) :
  - partition TEMPORELLE par intervalles déclarés dans un fichier de séparation, jamais aléatoire ;
  - une fenêtre n'appartient à un jeu que si elle est ENTIÈREMENT dans un de ses intervalles ;
  - intervalles de jeux différents séparés d'au moins une fenêtre (purge) ;
  - entraînement sur du trafic normal uniquement (le jeu `train` ne doit contenir aucune requête du marqueur d'attaque) ;
  - seuil calibré sur la VALIDATION seule : le plus sensible (<= 0) qui ne produit aucun blocage à tort sur
    le trafic normal de validation ; le jeu de test n'est lu qu'après gel du modèle ;
  - vérité terrain : marqueur d'attaque dans le User-Agent (valable en laboratoire, le modèle ne voit jamais le UA).
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime
from pathlib import Path

import numpy as np

from . import STEP_S, WINDOW_S
from .engine import GateParams, replay, run_gate, score_steps
from .features import FEATURE_NAMES, build_steps
from .logs import Request, read_requests
from .model import LoadedWafModel, build_pipeline, save_model

MIN_TRAIN_WINDOWS = 30
THIN_RATES = (1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01)
THIN_SEEDS = (1, 2, 3)


def _epoch(text: str) -> float:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def load_splits(path: Path) -> dict:
    spec = json.loads(Path(path).read_text())
    window_s = float(spec.get("window_s", WINDOW_S))
    intervals = {
        name: [(_epoch(a), _epoch(b)) for a, b in spec["splits"][name]] for name in ("train", "validation", "test")
    }
    for name, items in intervals.items():
        if not items or any(b <= a for a, b in items):
            raise ValueError(f"SPLIT_INVALID:{name}")
    flat = sorted((a, b, name) for name, items in intervals.items() for a, b in items)
    for (_a1, b1, n1), (a2, _b2, n2) in zip(flat, flat[1:], strict=False):
        if a2 < b1 or (n1 != n2 and a2 - b1 < window_s):
            raise ValueError(f"LEAKAGE_OVERLAP:{n1}/{n2}")
    return {
        "intervals": intervals,
        "window_s": window_s,
        "step_s": float(spec.get("step_s", STEP_S)),
        "marker": str(spec["attack_marker"]),
        "dataset_sha256": spec.get("dataset_sha256"),
        "params": GateParams(
            consecutive=int(spec.get("consecutive", 3)), min_requests=int(spec.get("min_requests", 5))
        ),
    }


def _slice(requests: list[Request], a: float, b: float) -> list[Request]:
    return [r for r in requests if a <= r.ts < b]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _prepare(requests, intervals, window_s, step_s):
    """Pour chaque intervalle : requêtes, fenêtres entièrement incluses, toutes les fenêtres."""
    out = []
    for a, b in intervals:
        reqs = _slice(requests, a, b)
        out.append(
            {
                "interval": (a, b),
                "requests": reqs,
                "inside": build_steps(reqs, window_s, step_s, inside_only=(a, b)),
                "all": build_steps(reqs, window_s, step_s),
            }
        )
    return out


def _calibrate(parts, scorer, params: GateParams, is_attack) -> float:
    scored = [(p["all"], score_steps(scorer, p["all"])) for p in parts]
    normal_scores = sorted(
        {
            r.score
            for _, steps in scored
            for rows in steps
            for r in rows
            if not is_attack(r.ua) and r.n >= params.min_requests and r.score < 0
        },
        reverse=True,
    )

    def false_triggers(threshold: float) -> int:
        return sum(
            not is_attack(t.ua) for steps, sc in scored for t in run_gate(sc, steps, threshold, params)
        )

    for threshold in [0.0, *normal_scores]:
        if false_triggers(threshold) == 0:
            return float(threshold)
    return float(normal_scores[-1]) if normal_scores else 0.0


def _window_metrics(parts, model, params, is_attack) -> dict:
    tp = fp = fn = tn = 0
    for part in parts:
        for rows in score_steps(model, part["inside"]):
            for r in rows:
                predicted = r.n >= params.min_requests and r.score < model.threshold
                actual = is_attack(r.ua)
                tp += predicted and actual
                fp += predicted and not actual
                fn += (not predicted) and actual
                tn += (not predicted) and not actual
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall}


def _gate_outcome(requests, model, params, is_attack) -> dict:
    triggers, _ = replay(requests, model, params)
    attack_ts = [r.ts for r in requests if is_attack(r.ua)]
    start = min(attack_ts) if attack_ts else None
    good = [t for t in triggers if is_attack(t.ua)]
    return {
        "attack_requests": len(attack_ts),
        "attack_start": start,
        "attack_rate_req_s": (len(attack_ts) / max(1.0, max(attack_ts) - start)) if attack_ts else 0.0,
        "detected": bool(good),
        "latency_s": (good[0].ts - start) if good and start is not None else None,
        "false_blocks": [t.ua for t in triggers if not is_attack(t.ua)],
        "triggers": len(triggers),
    }


def _baselines(train_parts, val_parts, test_parts, params, is_attack) -> dict:
    """Une règle à seuil sur UNE caractéristique suffit-elle ? Calibrée sur train+validation, évaluée sur le test."""

    def collect(parts):
        values = []
        for p in parts:
            for step in p["inside"]:
                for ua, (n, vec) in step.entities.items():
                    values.append((is_attack(ua), n, vec))
        return values

    base_norm = [v for att, n, v in collect(train_parts) + collect(val_parts) if not att]
    base_att = [v for att, n, v in collect(val_parts) if att and n >= params.min_requests]
    test_rows = [(att, n, v) for att, n, v in collect(test_parts) if n >= params.min_requests or att]
    out = {}
    for i, name in enumerate(FEATURE_NAMES):
        nv, av = [v[i] for v in base_norm], [v[i] for v in base_att]
        if not nv or not av:
            out[name] = {"separable": False}
            continue
        if min(av) > max(nv):
            threshold, high = (min(av) + max(nv)) / 2, True
        elif max(av) < min(nv):
            threshold, high = (max(av) + min(nv)) / 2, False
        else:
            out[name] = {"separable": False}
            continue
        errors = sum(((v[i] > threshold) if high else (v[i] < threshold)) != att for att, _, v in test_rows)
        out[name] = {"separable": True, "threshold": round(threshold, 4), "test_errors": errors, "test_windows": len(test_rows)}
    return out


def _thin(requests, is_attack, rate, seed):
    rng = random.Random(seed)
    return [r for r in requests if not is_attack(r.ua) or rng.random() < rate]


def _sensitivity(test_parts, model, params, is_attack) -> list[dict]:
    rows = []
    for rate in THIN_RATES:
        detected = false_blocks = 0
        latencies, rates = [], []
        for seed in THIN_SEEDS:
            for part in test_parts:
                if not any(is_attack(r.ua) for r in part["requests"]):
                    continue
                outcome = _gate_outcome(_thin(part["requests"], is_attack, rate, seed), model, params, is_attack)
                detected += outcome["detected"]
                false_blocks += len(outcome["false_blocks"])
                rates.append(outcome["attack_rate_req_s"])
                if outcome["latency_s"] is not None:
                    latencies.append(outcome["latency_s"])
        runs = len(THIN_SEEDS) * sum(any(is_attack(r.ua) for r in p["requests"]) for p in test_parts)
        rows.append(
            {
                "keep_rate": rate,
                "attack_req_s": round(float(np.mean(rates)), 2) if rates else 0.0,
                "detected": f"{detected}/{runs}",
                "median_latency_s": float(np.median(latencies)) if latencies else None,
                "false_blocks": false_blocks,
            }
        )
    return rows


def _eligible_counts(parts, params, is_attack) -> dict:
    """Fenêtres (entité x fenêtre) entièrement incluses et assez fournies pour pouvoir déclencher."""
    counts = {"normal": 0, "attack": 0}
    for part in parts:
        for step in part["inside"]:
            for ua, (n, _vec) in step.entities.items():
                if n >= params.min_requests:
                    counts["attack" if is_attack(ua) else "normal"] += 1
    return counts


def _normal_false_alarm_check(requests, model, params, window_s, step_s, is_attack) -> dict:
    """Rejoue TOUT le trafic normal du journal (train compris : résultat favorable) pour compter les fausses alertes."""
    normal = [r for r in requests if not is_attack(r.ua)]
    steps = build_steps(normal, window_s, step_s)
    scored = score_steps(model, steps)
    eligible = [row for rows in scored for row in rows if row.n >= params.min_requests]
    triggers, _ = replay(normal, model, params)
    return {
        "normal_windows": sum(len(rows) for rows in scored),
        "eligible_windows": len(eligible),
        "flagged_windows": sum(row.score < model.threshold for row in eligible),
        "gate_triggers_on_normal": len(triggers),
    }


def _warnings(result, attack_user_agents) -> list[str]:
    out = []
    if result["test"]["eligible"]["normal"] < 30:
        out.append(
            f"TEST_NORMAL_ELIGIBLE_TOO_FEW : {result['test']['eligible']['normal']} fenêtres normales assez fournies dans le test "
            "(< 30) : le taux de faux positifs n'est pas mesurable, la précision est NON PROBANTE."
        )
    check = result["normal_false_alarm_check"]
    if check["eligible_windows"] and check["flagged_windows"] / check["eligible_windows"] > 0.1:
        out.append(
            f"NORMAL_BURSTS_FLAGGED : {check['flagged_windows']}/{check['eligible_windows']} fenêtres normales de plus de "
            f"{result['params']['min_requests']} requêtes sont jugées atypiques ; {check['gate_triggers_on_normal']} déclenchement(s) "
            "sur le seul trafic normal. Le modèle sépare mal une rafale normale d'une attaque : trop peu de pics normaux à l'entraînement."
        )
    if len(attack_user_agents) < 2:
        out.append("SINGLE_ATTACK_TOOL : un seul outil d'attaque (un User-Agent, une URI) : la généralisation n'est pas démontrée.")
    return out


def train_and_evaluate(log_path: Path, splits_path: Path, out_dir: Path, version: str, seed: int = 42) -> dict:
    spec = load_splits(splits_path)
    if spec["dataset_sha256"] and spec["dataset_sha256"] != _sha256(log_path):
        raise ValueError("DATASET_SHA_MISMATCH")  # les intervalles ne valent que pour le journal décrit
    requests, read_stats = read_requests(log_path)
    window_s, step_s, marker, params = spec["window_s"], spec["step_s"], spec["marker"].lower(), spec["params"]

    def is_attack(ua: str) -> bool:
        return marker in ua.lower()

    parts = {name: _prepare(requests, items, window_s, step_s) for name, items in spec["intervals"].items()}

    # --- entraînement : trafic normal uniquement ---
    train_requests = [r for p in parts["train"] for r in p["requests"]]
    if any(is_attack(r.ua) for r in train_requests):
        raise ValueError("ATTACK_IN_TRAIN")
    matrix = np.asarray(
        [vec for p in parts["train"] for step in p["inside"] for (_, vec) in step.entities.values()], dtype=float
    )
    if len(matrix) < MIN_TRAIN_WINDOWS:
        raise ValueError(f"TRAIN_TOO_SMALL:{len(matrix)}<{MIN_TRAIN_WINDOWS}")
    pipeline = build_pipeline(len(matrix), seed)
    pipeline.fit(matrix)
    scorer = LoadedWafModel(pipeline, {"model_version": version, "threshold": 0.0}, "")

    # --- seuil : validation seule ---
    threshold = _calibrate(parts["validation"], scorer, params, is_attack)
    normal_uas = sorted({r.ua for r in train_requests})[:50]
    manifest = save_model(
        pipeline,
        Path(out_dir),
        model_version=version,
        threshold=threshold,
        dataset_sha256=_sha256(log_path),
        normal_user_agents=normal_uas,
        gate={"consecutive": params.consecutive, "min_requests": params.min_requests,
              "rearm_normal": params.rearm_normal, "cooldown_s": params.cooldown_s},
        extra={"synthetic_training_data": False, "attack_marker_for_ground_truth": spec["marker"],
               "train_windows": int(len(matrix))},
    )
    model = LoadedWafModel(pipeline, manifest, manifest["artifact_sha256"])

    # --- évaluation : validation (diagnostic) puis test gelé ---
    result = {
        "model_version": version,
        "dataset": {"sha256": manifest["dataset_sha256"], "read": read_stats,
                    "first_ts": requests[0].ts if requests else None, "last_ts": requests[-1].ts if requests else None},
        "params": {"window_s": window_s, "step_s": step_s, "threshold": threshold, **manifest["gate"]},
        "train": {"windows": int(len(matrix)), "requests": len(train_requests), "user_agents": normal_uas},
    }
    for name in ("validation", "test"):
        result[name] = {
            "eligible": _eligible_counts(parts[name], params, is_attack),
            "windows": _window_metrics(parts[name], model, params, is_attack),
            "intervals": [
                {k: v for k, v in _gate_outcome(p["requests"], model, params, is_attack).items() if k != "triggers"}
                for p in parts[name]
            ],
        }
    result["normal_false_alarm_check"] = _normal_false_alarm_check(requests, model, params, window_s, step_s, is_attack)
    result["baselines"] = _baselines(parts["train"], parts["validation"], parts["test"], params, is_attack)
    result["sensitivity_test_thinning"] = _sensitivity(parts["test"], model, params, is_attack)
    result["warnings"] = _warnings(result, {r.ua for r in requests if is_attack(r.ua)})
    return result


def render_markdown(result: dict) -> str:
    def pct(value):
        return "n/a" if value is None else f"{value:.3f}"

    lines = [
        f"# Résultats — détecteur WAF par User-Agent (`{result['model_version']}`)",
        "",
        f"Données : `access.jsonl` (SHA-256 `{result['dataset']['sha256'][:16]}…`), "
        f"{result['dataset']['read']['accepted']} requêtes lues, rejets : {result['dataset']['read']['rejected'] or 'aucun'}.",
        f"Fenêtre {result['params']['window_s']:g} s, pas {result['params']['step_s']:g} s, seuil {result['params']['threshold']:.4f}, "
        f"alerte après {result['params']['consecutive']} fenêtres, ≥ {result['params']['min_requests']} requêtes.",
        f"Entraînement : {result['train']['windows']} fenêtres normales ({result['train']['requests']} requêtes).",
        "",
    ]
    if result.get("warnings"):
        lines += ["**Mises en garde (générées par l'évaluation)**", ""] + [f"- {w}" for w in result["warnings"]] + [""]
    check = result["normal_false_alarm_check"]
    lines += [
        f"Contrôle de fausses alertes sur TOUT le trafic normal du journal (entraînement inclus) : {check['flagged_windows']}/{check['eligible_windows']} "
        f"fenêtres assez fournies jugées atypiques, {check['gate_triggers_on_normal']} déclenchement(s) de la règle d'alerte.",
        "",
        "| Jeu | Fenêtres normales exploitables | Fenêtres d'attaque | TP | FP | FN | TN | Précision | Rappel |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name in ("validation", "test"):
        w = result[name]["windows"]
        e = result[name]["eligible"]
        lines.append(f"| {name} | {e['normal']} | {e['attack']} | {w['tp']} | {w['fp']} | {w['fn']} | {w['tn']} | {pct(w['precision'])} | {pct(w['recall'])} |")
    lines += ["", "Rafales (blocage de bout en bout, rejeu du moteur) :", "",
              "| Jeu | Requêtes d'attaque | Débit (req/s) | Détectée | Latence (s) | Blocages à tort |", "|---|---|---|---|---|---|"]
    for name in ("validation", "test"):
        for it in result[name]["intervals"]:
            if it["attack_requests"]:
                lat = "n/a" if it["latency_s"] is None else f"{it['latency_s']:.0f}"
                lines.append(f"| {name} | {it['attack_requests']} | {it['attack_rate_req_s']:.1f} | {'oui' if it['detected'] else 'NON'} | {lat} | {len(it['false_blocks'])} |")
    lines += ["", "Une règle à seuil sur une seule caractéristique suffit-elle ?", "",
              "| Caractéristique | Séparable (train+validation) | Erreurs sur le test |", "|---|---|---|"]
    for name, b in result["baselines"].items():
        lines.append(f"| {name} | {'oui' if b['separable'] else 'non'} | {b.get('test_errors', '—')} |")
    lines += ["", "Sensibilité : le flood réel du jeu de test est sous-échantillonné (simulation d'une attaque plus lente) :", "",
              "| Part conservée | Débit (req/s) | Détectée | Latence médiane (s) | Blocages à tort |", "|---|---|---|---|---|"]
    for s in result["sensitivity_test_thinning"]:
        lat = "n/a" if s["median_latency_s"] is None else f"{s['median_latency_s']:.0f}"
        lines.append(f"| {s['keep_rate']:g} | {s['attack_req_s']} | {s['detected']} | {lat} | {s['false_blocks']} |")
    return "\n".join(lines) + "\n"
