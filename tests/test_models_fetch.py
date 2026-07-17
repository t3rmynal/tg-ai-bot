"""Model discovery: payload parsing and the http wrapper."""

import asyncio

import pytest

from tgai.providers import ModelFetchError, _parse_models_payload, fetch_models

from .conftest import FakeResp, FakeSession


def test_parse_openai_shape():
    data = {"data": [{"id": "b-model"}, {"id": "a-model"}, {"id": "a-model"}]}
    assert _parse_models_payload(data) == ["a-model", "b-model"]  # sorted, deduped


def test_parse_models_key_and_bare_list():
    assert _parse_models_payload({"models": ["x", {"name": "y"}]}) == ["x", "y"]
    assert _parse_models_payload([{"id": "z"}]) == ["z"]


def test_parse_garbage_raises():
    with pytest.raises(ModelFetchError):
        _parse_models_payload({"nope": True})


def test_fetch_models_ok_and_headers():
    session = FakeSession([FakeResp(200, {"data": [{"id": "m1"}]})])
    out = asyncio.run(fetch_models(session, "https://api.example/v1/", "sk-key"))
    assert out == ["m1"]
    method, url, kwargs = session.requests[0]
    assert method == "get"
    assert url == "https://api.example/v1/models"
    assert kwargs["headers"]["Authorization"] == "Bearer sk-key"


def test_fetch_models_no_key_omits_auth_header():
    session = FakeSession([FakeResp(200, {"data": []})])
    asyncio.run(fetch_models(session, "http://localhost:11434/v1", ""))
    _, _, kwargs = session.requests[0]
    assert "Authorization" not in kwargs["headers"]


def test_fetch_models_http_error_raises():
    session = FakeSession([FakeResp(500)])
    with pytest.raises(ModelFetchError):
        asyncio.run(fetch_models(session, "https://api.example/v1", "k"))


def test_fetch_models_empty_base_url_raises():
    with pytest.raises(ModelFetchError):
        asyncio.run(fetch_models(FakeSession(), "", "k"))
