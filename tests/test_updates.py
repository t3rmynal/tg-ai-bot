"""Update check: version comparison and the endpoint."""

import asyncio

from tgai import __version__
from tgai.updates import UpdateChecker, is_newer, parse_version

from .conftest import FakeResp, FakeSession


def test_parse_version():
    assert parse_version("v3.1.0") == (3, 1, 0)
    assert parse_version("3.1.0") == (3, 1, 0)
    assert parse_version("garbage") is None
    assert parse_version("") is None


def test_is_newer():
    assert is_newer("3.0.1", "3.0.0") is True
    assert is_newer("4.0.0", "3.9.9") is True
    assert is_newer("3.0.0", "3.0.0") is False
    assert is_newer("2.9.9", "3.0.0") is False
    assert is_newer("not-a-version", "3.0.0") is False


def test_checker_reports_newer_release():
    checker = UpdateChecker("example/repo")
    session = FakeSession([
        FakeResp(200, {"tag_name": "v99.0.0", "html_url": "https://github.com/example/repo/releases/v99.0.0"}),
    ])
    out = asyncio.run(checker.check(session))
    assert out["current"] == __version__
    assert out["latest"] == "99.0.0"
    assert out["update_available"] is True

    # cached: no second request happens
    out2 = asyncio.run(checker.check(session))
    assert out2 == out
    assert len(session.requests) == 1


def test_checker_handles_failure_gracefully():
    checker = UpdateChecker("example/repo")
    session = FakeSession([FakeResp(500)])
    out = asyncio.run(checker.check(session))
    assert out["update_available"] is False
    assert out["latest"] is None
    assert "error" in out


async def test_updates_endpoint(client, state):
    state.fake_session._responses = [
        FakeResp(200, {"tag_name": "v0.0.1", "html_url": "https://example"}),
    ]
    r = await client.get("/api/updates")
    body = r.json()
    assert r.status_code == 200
    assert body["current"] == __version__
    assert body["update_available"] is False  # 0.0.1 is older than current
