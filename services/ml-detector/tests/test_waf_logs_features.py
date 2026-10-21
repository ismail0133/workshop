import json
import math

import pytest
from ml_app.waf.features import FEATURE_NAMES, MAX_ENTITIES, build_steps, vector
from ml_app.waf.logs import LogRejected, Request, normalise_ua, parse_line, read_requests
from waf_support import BASE, BROWSER, line


def test_parses_a_real_edge_line_and_never_keeps_the_query():
    raw = line(BASE, uri="/api/payments?token=secret", status=201, duration="0.409", method="POST")
    r = parse_line(raw)
    assert (r.method, r.path, r.status, r.ua) == ("POST", "/api/payments", 201, BROWSER)
    assert math.isclose(r.duration_ms, 409.0) and not r.limited and not r.blocked


def test_limit_and_block_flags():
    assert parse_line(line(BASE, status=429, limit_req="LIMITED")).limited
    assert parse_line(line(BASE, status=403, blocked="1")).blocked


@pytest.mark.parametrize(
    "raw,code",
    [
        ("not json", "BAD_JSON"),
        ("[1, 2]", "NOT_AN_OBJECT"),
        (json.dumps({"event": "OTHER"}), "NOT_EDGE_EVENT"),
        (line(BASE).replace("2025", "20xx"), "BAD_TS"),
        (line(BASE, status=99), "BAD_STATUS"),
        (line(BASE, status=True), "BAD_STATUS"),
        (line(BASE, status="200"), "BAD_STATUS"),
        (line(BASE, duration="-1"), "BAD_DURATION"),
        (line(BASE, duration="nan"), "BAD_DURATION"),
        (line(BASE, duration="abc"), "BAD_DURATION"),
        ("x" * 9000, "LINE_TOO_LONG"),
    ],
)
def test_malformed_lines_are_rejected_with_a_stable_code(raw, code):
    with pytest.raises(LogRejected) as info:
        parse_line(raw)
    assert info.value.args[0] == code


def test_user_agent_is_normalised_and_bounded():
    assert normalise_ua("Foo\r\nua:Chrome\t  bar") == "Foo ua:Chrome bar"
    assert len(normalise_ua("A" * 1000)) == 200
    assert normalise_ua("") == "(none)" and normalise_ua("\n\n") == "(none)"


def test_read_requests_counts_rejections_and_sorts(tmp_path):
    path = tmp_path / "access.jsonl"
    path.write_text("\n".join([line(BASE + 5), "garbage", line(BASE), "", line(BASE + 1, status=7)]) + "\n")
    requests, stats = read_requests(path)
    assert [r.ts for r in requests] == sorted(r.ts for r in requests)
    assert stats == {"lines": 4, "accepted": 2, "rejected": {"BAD_JSON": 1, "BAD_STATUS": 1}}


def _req(ts, ua="a", path="/", status=200, ms=10.0, method="GET"):
    return Request(ts, ua, method, path, status, ms, False, False)


def test_vector_values():
    rs = [_req(0, path="/", ms=10), _req(1, path="/", status=404, ms=30), _req(2, path="/x", status=500, ms=20, method="POST")]
    v = dict(zip(FEATURE_NAMES, vector(rs, 10), strict=True))
    assert v["req_per_s"] == pytest.approx(0.3) and v["share_4xx"] == pytest.approx(1 / 3)
    assert v["share_5xx"] == pytest.approx(1 / 3) and v["distinct_uris"] == 2
    assert v["top_uri_share"] == pytest.approx(2 / 3) and v["mean_duration_ms"] == pytest.approx(20)
    assert v["share_post"] == pytest.approx(1 / 3)
    with pytest.raises(ValueError):
        vector([])


def test_windows_are_aligned_and_group_by_user_agent():
    rs = [_req(BASE + 1, "a"), _req(BASE + 2, "b"), _req(BASE + 7, "a")]
    steps = build_steps(rs)
    assert all(s.end % 5 == 0 for s in steps)
    first = steps[0]  # [BASE-5, BASE+5)
    assert set(first.entities) == {"a", "b"} and first.entities["a"][0] == 1
    assert sum(s.entities.get("a", (0,))[0] for s in steps) == 4  # chaque requête compte dans 2 fenêtres de 10 s au pas de 5 s


def test_inside_only_drops_windows_that_straddle_a_boundary():
    rs = [_req(BASE + i) for i in range(0, 60)]
    inside = build_steps(rs, inside_only=(BASE + 10, BASE + 40))
    assert inside and all(s.end - 10 >= BASE + 10 and s.end <= BASE + 40 for s in inside)


def test_entity_cap_bounds_cpu_when_user_agents_explode():
    rs = [_req(BASE + 1, f"ua{i}") for i in range(MAX_ENTITIES + 50)] + [_req(BASE + 1, "busy")] * 3
    step = build_steps(rs)[0]
    assert len(step.entities) == MAX_ENTITIES and step.overflow == 51 and "busy" in step.entities
