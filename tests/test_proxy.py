"""Proxy parsing, pool rotation, mullvad list building and the routes."""

from tgai.proxy import ProxyManager, build_mullvad_urls, parse_proxy

from .conftest import FakeResp

# parsing


def test_parse_full_url():
    p = parse_proxy("socks5://user:pass@1.2.3.4:1080")
    assert p is not None
    assert p.scheme == "socks5"
    assert p.host == "1.2.3.4"
    assert p.port == 1080
    assert p.username == "user"
    assert p.password == "pass"
    assert p.masked() == "socks5://user:***@1.2.3.4:1080"


def test_parse_bare_host_defaults_socks5():
    p = parse_proxy("1.2.3.4:1080")
    assert p is not None
    assert p.scheme == "socks5"
    assert p.username == ""


def test_parse_rejects_junk():
    assert parse_proxy("") is None
    assert parse_proxy("not a proxy") is None
    assert parse_proxy("ftp://host:21") is None
    assert parse_proxy("socks5://host") is None  # no port


def test_telethon_dict():
    p = parse_proxy("socks5://u:p@h:1080")
    d = p.telethon()
    assert d["proxy_type"] == "socks5"
    assert d["addr"] == "h"
    assert d["port"] == 1080
    assert d["username"] == "u"


# mullvad


def test_build_mullvad_urls_filters_and_formats():
    relays = [
        {"active": True, "type": "wireguard", "socks_name": "se-got-wg-socks5-001.relays.mullvad.net",
         "socks_port": 1080, "country_code": "se"},
        {"active": True, "type": "wireguard", "socks_name": "us-nyc-wg-socks5-001.relays.mullvad.net",
         "socks_port": 1080, "country_code": "us"},
        {"active": False, "type": "wireguard", "socks_name": "de-off.relays.mullvad.net",
         "socks_port": 1080, "country_code": "de"},  # inactive, dropped
        {"active": True, "type": "openvpn", "socks_name": "x", "country_code": "se"},  # not wireguard
    ]
    all_urls = build_mullvad_urls(relays)
    assert len(all_urls) == 2
    assert "socks5://se-got-wg-socks5-001.relays.mullvad.net:1080" in all_urls

    se_only = build_mullvad_urls(relays, "se")
    assert se_only == ["socks5://se-got-wg-socks5-001.relays.mullvad.net:1080"]


# manager rotation


def test_manager_disabled_returns_none(cfg):
    cfg.set("proxy.manual", ["socks5://h:1"])
    pm = ProxyManager(cfg)
    assert pm.active() is None  # enabled is false
    assert pm.next_for_request() is None


def test_manager_off_keeps_same(cfg):
    cfg.set("proxy.enabled", True)
    cfg.set("proxy.rotation", "off")
    cfg.set("proxy.manual", ["socks5://a:1", "socks5://b:2"])
    pm = ProxyManager(cfg)
    first = pm.next_for_request()
    second = pm.next_for_request()
    assert first.host == second.host == "a"


def test_manager_per_request_rotates(cfg):
    cfg.set("proxy.enabled", True)
    cfg.set("proxy.rotation", "per_request")
    cfg.set("proxy.manual", ["socks5://a:1", "socks5://b:2"])
    pm = ProxyManager(cfg)
    hosts = [pm.next_for_request().host for _ in range(4)]
    assert hosts == ["b", "a", "b", "a"]


def test_manager_per_n_rotates_every_n(cfg):
    cfg.set("proxy.enabled", True)
    cfg.set("proxy.rotation", "per_n")
    cfg.set("proxy.rotate_every", 2)
    cfg.set("proxy.manual", ["socks5://a:1", "socks5://b:2"])
    pm = ProxyManager(cfg)
    hosts = [pm.next_for_request().host for _ in range(4)]
    assert hosts == ["a", "b", "b", "a"]


def test_mullvad_mode_uses_loaded_pool(cfg):
    cfg.set("proxy.enabled", True)
    cfg.set("proxy.mode", "mullvad")
    cfg.set("proxy.mullvad.loaded", ["socks5://se.relays.mullvad.net:1080"])
    pm = ProxyManager(cfg)
    assert pm.active().host == "se.relays.mullvad.net"


def test_telegram_proxy_needs_opt_in(cfg):
    cfg.set("proxy.enabled", True)
    cfg.set("proxy.manual", ["socks5://a:1"])
    pm = ProxyManager(cfg)
    assert pm.telegram_proxy() is None  # apply_to_telegram false
    cfg.set("proxy.apply_to_telegram", True)
    assert pm.telegram_proxy()["addr"] == "a"


# routes


async def test_proxy_status_and_patch(client, state):
    r = await client.get("/api/proxy")
    assert r.json()["enabled"] is False

    r = await client.patch("/api/proxy", json={"enabled": True, "rotation": "per_request"})
    assert r.status_code == 200
    assert state.cfg.get("proxy.enabled") is True
    assert state.cfg.get("proxy.rotation") == "per_request"

    r = await client.patch("/api/proxy", json={"rotation": "nonsense"})
    assert r.status_code == 422


async def test_manual_add_remove(client, state):
    r = await client.post("/api/proxy/manual", json={"url": "garbage"})
    assert r.status_code == 422

    r = await client.post("/api/proxy/manual", json={"url": "socks5://1.2.3.4:1080"})
    assert r.status_code == 200
    assert "socks5://1.2.3.4:1080" in state.cfg.get("proxy.manual")

    r = await client.post("/api/proxy/manual", json={"url": "socks5://1.2.3.4:1080"})
    assert r.status_code == 409

    r = await client.delete("/api/proxy/manual", params={"index": 0})
    assert r.status_code == 200
    assert state.cfg.get("proxy.manual") == []


async def test_manual_masks_credentials_in_list(client, state):
    state.cfg.set("proxy.manual", ["socks5://user:secretpw@h:1080"])
    r = await client.get("/api/proxy/list")
    assert "secretpw" not in r.text
    assert r.json()["manual"][0]["masked"] == "socks5://user:***@h:1080"


async def test_mullvad_refresh(client, state):
    state.fake_session._responses = [
        FakeResp(200, [
            {"active": True, "type": "wireguard", "country_code": "se",
             "socks_name": "se.relays.mullvad.net", "socks_port": 1080},
        ]),
    ]
    r = await client.post("/api/proxy/mullvad/refresh", json={"country": "se"})
    assert r.status_code == 200
    assert r.json()["count"] == 1
    assert state.cfg.get("proxy.mullvad.loaded") == ["socks5://se.relays.mullvad.net:1080"]


async def test_rotate_endpoint(client, state):
    state.cfg.set("proxy.enabled", True)
    state.cfg.set("proxy.manual", ["socks5://a:1", "socks5://b:2"])
    r = await client.post("/api/proxy/rotate")
    assert r.json()["active"] == "socks5://b:2"
