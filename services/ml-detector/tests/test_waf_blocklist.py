import os
import stat
import sys

import pytest
from ml_app.waf.blocklist import MANAGED_MARK, Blocklist, candidate_token, check_token
from waf_support import BROWSER

HEADER = "# Edge blocklist\nua:Existing  # hand-written\n"


@pytest.fixture
def blocklist_file(tmp_path):
    path = tmp_path / "blocklist.txt"
    path.write_text(HEADER)
    path.chmod(0o644)
    return path


@pytest.mark.parametrize(
    "ua,token",
    [("ResilienceAttack/1.0", "ResilienceAttack"), ("  curl/8.4.0", "curl"), ("python-httpx/0.28.1", "python-httpx"),
     ("(weird)", None), ("", None), ("Foo\nua:Chrome", "Foo")],
)
def test_token_is_the_leading_product(ua, token):
    assert candidate_token(ua) == token


@pytest.mark.parametrize("token", ["Mozilla", "Chrome", "Safari", "Windows", "AppleWebKit", "gecko", "win64"])
def test_browser_tokens_are_refused_like_the_waf_does(token):
    assert check_token(token) == "REFUSED_BROWSER"


@pytest.mark.parametrize("token", [None, "", "abc", "a" * 65, "bad token", "ua:X", "x;rm"])
def test_format_is_enforced(token):
    assert check_token(token) == "REFUSED_BAD_TOKEN"


def test_user_agents_seen_in_normal_traffic_and_protected_ones_are_refused():
    assert check_token("Postman", normal_user_agents=["PostmanRuntime/7.0"]) == "REFUSED_SEEN_NORMAL"
    assert check_token("python-httpx", never_block=["httpx"]) == "REFUSED_PROTECTED"
    assert check_token("ResilienceAttack", normal_user_agents=[BROWSER], never_block=["httpx"]) is None


def test_default_is_a_dry_run_and_never_writes(blocklist_file):
    result = Blocklist(blocklist_file).block("ResilienceAttack/1.0", score=-0.2)
    assert (result.status, result.token) == ("DRY_RUN", "ResilienceAttack")
    assert blocklist_file.read_text() == HEADER


def test_apply_appends_atomically_keeps_existing_lines_and_mode(blocklist_file):
    result = Blocklist(blocklist_file, apply=True).block("ResilienceAttack/1.0", score=-0.2)
    assert result.status == "WRITTEN"
    text = blocklist_file.read_text()
    assert text.startswith(HEADER) and "ua:ResilienceAttack  " + MANAGED_MARK in text and text.endswith("\n")
    assert stat.S_IMODE(blocklist_file.stat().st_mode) == 0o644 or sys.platform == "win32"
    assert [p.name for p in blocklist_file.parent.iterdir()] == ["blocklist.txt"]  # pas de fichier temporaire


def test_apply_is_idempotent_and_case_insensitive(blocklist_file):
    bl = Blocklist(blocklist_file, apply=True)
    assert bl.block("ResilienceAttack/1.0", score=-0.2).status == "WRITTEN"
    before = blocklist_file.read_text()
    assert bl.block("resilienceattack/2.0", score=-0.3).status == "ALREADY"
    assert bl.block("Existing/1", score=-0.3).status == "ALREADY"  # entrée écrite à la main
    assert blocklist_file.read_text() == before


def test_cap_on_entries_written_by_the_detector(blocklist_file):
    bl = Blocklist(blocklist_file, apply=True, max_managed=2)
    assert [bl.block(f"Flooder{i}/1", score=-0.2).status for i in range(3)] == ["WRITTEN", "WRITTEN", "CAP_REACHED"]
    assert blocklist_file.read_text().count(MANAGED_MARK) == 2


def test_a_hostile_user_agent_cannot_inject_lines_or_comments(blocklist_file):
    bl = Blocklist(blocklist_file, apply=True)
    hostile = "Evil/1.0\nua:Mozilla\n1.2.3.4 # x"
    assert bl.block(hostile, score=-0.2).status == "WRITTEN"
    lines = blocklist_file.read_text().splitlines()
    assert lines[-1].startswith("ua:Evil  ") and "Mozilla" not in "\n".join(lines[2:]) and "1.2.3.4" not in "\n".join(lines)
    assert len(lines) == 3


def test_refused_tokens_never_touch_the_file(blocklist_file):
    bl = Blocklist(blocklist_file, apply=True, normal_user_agents=[BROWSER])
    assert bl.block(BROWSER, score=-0.5).status == "REFUSED_BROWSER"
    assert bl.block("", score=-0.5).status == "REFUSED_BAD_TOKEN"
    assert blocklist_file.read_text() == HEADER


def test_missing_file_is_created_with_a_readable_mode(tmp_path):
    path = tmp_path / "blocklist.txt"
    assert Blocklist(path, apply=True).block("Flooder/1", score=-0.1).status == "WRITTEN"
    assert path.read_text().startswith("ua:Flooder  ")
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o644
