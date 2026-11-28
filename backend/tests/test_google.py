"""Google sign-in: tokens are signed with a local RSA key standing in for Google's, so the real checks run."""
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import google_auth

API = "/api/v1"
CID = "1234567890-abc123.apps.googleusercontent.com"
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(**over):
    now = int(time.time())
    claims = {"iss": "https://accounts.google.com", "aud": CID, "sub": "g-1001", "email": "gina@example.com",
              "email_verified": True, "name": "Gina", "iat": now, "exp": now + 600, **over}
    return jwt.encode(claims, _key, algorithm="RS256")


@pytest.fixture
def google_on(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CID)
    monkeypatch.setattr(google_auth._jwks, "get_signing_key_from_jwt", lambda _t: SimpleNamespace(key=_key.public_key()))


def test_providers_reports_client_id(client, google_on):
    assert client.get(f"{API}/auth/providers").json()["google_client_id"] == CID


def test_google_creates_then_reuses_account(client, alice, google_on):
    r1 = client.post(f"{API}/auth/google", json={"credential": token()})
    assert r1.status_code == 200, r1.text
    u = r1.json()["user"]
    assert u["email"] == "gina@example.com" and u["display_name"] == "Gina" and not u["is_admin"]
    r2 = client.post(f"{API}/auth/google", json={"credential": token(email="gina.new@example.com")})  # same Google account
    assert r2.json()["user"]["id"] == u["id"]


def test_google_links_existing_password_account(client, alice, google_on):
    r = client.post(f"{API}/auth/google", json={"credential": token(sub="g-alice", email="Alice@example.com")})
    assert r.status_code == 200 and r.json()["user"]["display_name"] == "Alice"


@pytest.mark.parametrize("bad", [{"aud": "someone-else.apps.googleusercontent.com"}, {"exp": int(time.time()) - 3600},
                                 {"iss": "evil.example.com"}, {"email_verified": False}])
def test_google_rejects_bad_tokens(client, google_on, bad):
    assert client.post(f"{API}/auth/google", json={"credential": token(**bad)}).status_code == 401


def test_google_off_without_client_id(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    assert client.post(f"{API}/auth/google", json={"credential": token()}).status_code == 400


def test_admin_google_setting(client, alice, bob, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    assert client.put(f"{API}/admin/settings/google", headers=bob, json={"client_id": CID}).status_code == 403
    assert client.put(f"{API}/admin/settings/google", headers=alice, json={"client_id": "nope"}).status_code == 422
    r = client.put(f"{API}/admin/settings/google", headers=alice, json={"client_id": CID})
    assert r.json() == {"client_id": CID, "source": "app", "enabled": True}
    client.put(f"{API}/admin/settings/google", headers=alice, json={"client_id": ""})


def test_admin_can_pause_and_resume_google(client, alice, bob, google_on):
    assert client.get(f"{API}/admin/settings/google", headers=alice).json()["enabled"] is True  # on by default
    assert client.put(f"{API}/admin/settings/google/enabled", headers=bob, json={"enabled": False}).status_code == 403
    r = client.put(f"{API}/admin/settings/google/enabled", headers=alice, json={"enabled": False})
    assert r.status_code == 200 and r.json()["enabled"] is False and r.json()["client_id"] == CID
    p = client.get(f"{API}/auth/providers").json()
    assert p["google_ready"] is False and p["google_client_id"] is None
    assert client.post(f"{API}/auth/google", json={"credential": token(sub="g-2002", email="paused@example.com")}).status_code == 403
    client.put(f"{API}/admin/settings/google/enabled", headers=alice, json={"enabled": True})
    assert client.get(f"{API}/auth/providers").json()["google_ready"] is True
    assert client.post(f"{API}/auth/google", json={"credential": token(sub="g-2002", email="paused@example.com")}).status_code == 200
