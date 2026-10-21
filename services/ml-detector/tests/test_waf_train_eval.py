import json

import pytest
from ml_app.model import ModelIntegrityError
from ml_app.waf import __main__ as cli
from ml_app.waf.evaluate import load_splits, render_markdown, train_and_evaluate
from ml_app.waf.model import load_verified
from waf_support import BASE, BROWSER, FLOOD, iso, standard_log


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    d = tmp_path_factory.mktemp("waf")
    spec = standard_log(d / "access.jsonl")
    (d / "splits.json").write_text(json.dumps(spec))
    result = train_and_evaluate(d / "access.jsonl", d / "splits.json", d / "model", "waf-test-1")
    return d, spec, result


def test_end_to_end_on_a_synthetic_log_detects_the_flood_without_blaming_the_browser(trained):
    _, _, r = trained
    assert r["train"]["windows"] >= 30 and r["params"]["threshold"] <= 0.0
    for name in ("validation", "test"):
        flood = [i for i in r[name]["intervals"] if i["attack_requests"]]
        assert flood and all(i["detected"] and i["latency_s"] <= 20 for i in flood)
        assert all(i["false_blocks"] == [] for i in r[name]["intervals"])
    assert r["test"]["windows"]["recall"] >= 0.9


def test_report_exposes_data_sufficiency_and_sensitivity(trained):
    _, _, r = trained
    assert set(r["normal_false_alarm_check"]) == {"normal_windows", "eligible_windows", "flagged_windows", "gate_triggers_on_normal"}
    assert any(w.startswith("SINGLE_ATTACK_TOOL") for w in r["warnings"])  # un seul outil d'attaque dans ce journal
    assert [s["keep_rate"] for s in r["sensitivity_test_thinning"]][0] == 1.0
    text = render_markdown(r)
    assert "Mises en garde" in text and "Sensibilité" in text and "Une règle à seuil" in text


def test_the_model_never_sees_the_user_agent_string(trained):
    d, _, _ = trained
    model = load_verified(d / "model")
    assert model.manifest["features"] == ["req_per_s", "share_4xx", "share_5xx", "distinct_uris", "top_uri_share",
                                          "mean_duration_ms", "share_post"]
    assert model.manifest["synthetic_training_data"] is False and BROWSER in model.normal_user_agents
    assert FLOOD not in json.dumps(model.manifest)


def test_tampered_artifact_or_wrong_pin_is_refused(trained, tmp_path):
    d, _, _ = trained
    import shutil

    copy = tmp_path / "m"
    shutil.copytree(d / "model", copy)
    with pytest.raises(ModelIntegrityError, match="PINNED_HASH_MISMATCH"):
        load_verified(copy, "0" * 64)
    (copy / "model.joblib").write_bytes((copy / "model.joblib").read_bytes() + b"x")
    with pytest.raises(ModelIntegrityError, match="MANIFEST_HASH_MISMATCH"):
        load_verified(copy)


def _write_spec(tmp_path, spec, **splits):
    new = json.loads(json.dumps(spec))
    new["splits"].update(splits)
    path = tmp_path / "s.json"
    path.write_text(json.dumps(new))
    return path


def test_leakage_guards_reject_overlap_and_missing_purge(trained, tmp_path):
    _, spec, _ = trained
    train = spec["splits"]["train"][0]
    with pytest.raises(ValueError, match="LEAKAGE_OVERLAP"):
        load_splits(_write_spec(tmp_path, spec, validation=[train]))
    touching = [[train[1], spec["splits"]["validation"][0][1]]]  # démarre exactement à la fin du train : pas de purge
    with pytest.raises(ValueError, match="LEAKAGE_OVERLAP"):
        load_splits(_write_spec(tmp_path, spec, validation=touching))
    with pytest.raises(ValueError, match="SPLIT_INVALID"):
        load_splits(_write_spec(tmp_path, spec, test=[]))


def test_attack_traffic_in_the_training_set_is_refused(trained, tmp_path):
    d, spec, _ = trained
    bad = _write_spec(tmp_path, spec, train=[spec["splits"]["validation"][0]], validation=[spec["splits"]["train"][0]])
    with pytest.raises(ValueError, match="ATTACK_IN_TRAIN"):
        train_and_evaluate(d / "access.jsonl", bad, tmp_path / "m", "x")


def test_too_little_normal_data_is_refused(trained, tmp_path):
    d, spec, _ = trained
    short = [[iso(BASE), iso(BASE + 40)]]
    with pytest.raises(ValueError, match="TRAIN_TOO_SMALL"):
        train_and_evaluate(d / "access.jsonl", _write_spec(tmp_path, spec, train=short), tmp_path / "m", "x")


def _replay(d, tmp_path, *extra):
    bl = tmp_path / "blocklist.txt"
    bl.write_text("# hdr\n")
    code = cli.main(["replay", "--log", str(d / "access.jsonl"), "--model", str(d / "model"), "--blocklist", str(bl), *extra])
    assert code == 0
    return bl


def test_cli_replay_is_a_dry_run_by_default(trained, tmp_path, capsys):
    d, _, _ = trained
    bl = _replay(d, tmp_path)
    out = capsys.readouterr().out
    assert '"action": "DRY_RUN"' in out and '"ua_token": "TestFlood"' in out
    assert bl.read_text() == "# hdr\n"


def test_cli_apply_blocks_the_flood_once_and_audits(trained, tmp_path, capsys):
    d, _, _ = trained
    audit = tmp_path / "audit.jsonl"
    bl = _replay(d, tmp_path, "--apply", "--audit", str(audit))
    assert bl.read_text().count("ua:TestFlood") == 1 and "Mozilla" not in bl.read_text()
    records = [json.loads(x) for x in audit.read_text().splitlines()]
    assert any(r["action"] == "WRITTEN" and r["ua_token"] == "TestFlood" for r in records)
    assert all(r["ua_token"] != "Mozilla" or r["action"].startswith("REFUSED") for r in records)
    capsys.readouterr()
    _replay(d, tmp_path, "--apply")  # nouveau rejeu sur un fichier neuf : toujours un seul blocage
    assert bl.read_text().count("ua:TestFlood") == 1


def test_file_follower_reads_only_complete_lines_and_survives_truncation(tmp_path):
    path = tmp_path / "access.jsonl"
    assert cli.read_new_lines(path, 0) == ([], 0)  # fichier absent
    path.write_bytes(b"one\ntwo\nthr")
    lines, offset = cli.read_new_lines(path, 0)
    assert lines == ["one", "two"] and offset == 8  # « thr » est partielle : relue plus tard
    path.write_bytes(b"one\ntwo\nthree\n")
    lines, offset = cli.read_new_lines(path, offset)
    assert lines == ["three"] and offset == 14
    path.write_bytes(b"new\n")  # rotation / troncature
    assert cli.read_new_lines(path, offset) == (["new"], 4)


def test_parse_lines_counts_garbage_without_failing():
    from waf_support import line

    fresh, bad = cli.parse_lines([line(BASE), "garbage", "", line(BASE + 1, status=3)])
    assert len(fresh) == 1 and bad == 2


def test_splits_bound_to_a_dataset_hash_refuse_another_log(trained, tmp_path):
    d, spec, _ = trained
    bound = dict(spec, dataset_sha256="0" * 64)
    path = tmp_path / "bound.json"
    path.write_text(json.dumps(bound))
    with pytest.raises(ValueError, match="DATASET_SHA_MISMATCH"):
        train_and_evaluate(d / "access.jsonl", path, tmp_path / "m", "x")
