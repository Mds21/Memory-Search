"""Sign-up / sign-in with email, phone or username; linking; forgot password; password changes; owner tools."""
import pytest

from app import accounts

from .conftest import API


def _h(r):
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture
def outbox(monkeypatch):
    """Capture reset codes instead of sending real email/SMS."""
    from app.config import get_settings
    sent = []
    monkeypatch.setattr(get_settings(), "password_reset_enabled", True)
    monkeypatch.setattr(accounts, "email_ready", lambda: True)
    monkeypatch.setattr(accounts, "send_email", lambda to, subj, body: sent.append(("email", to, body)) or True)
    return sent


def _code(sent):
    import re
    return re.search(r"\b(\d{6})\b", sent[-1][2]).group(1)


def test_phone_normalisation():
    assert accounts.normalize_phone("98765 43210") == "+919876543210"
    assert accounts.normalize_phone("+44 7700 900123") == "+447700900123"
    assert accounts.normalize_phone("09876543210") == "+919876543210"
    assert accounts.normalize_phone("12345") is None


def test_register_and_sign_in_by_phone_email_or_username(client):
    r = client.post(f"{API}/auth/register", json={"phone": "98111 22333", "password": "phone-pass-1", "display_name": "Priya"})
    assert r.status_code == 201 and r.json()["user"]["phone"] == "+919811122333" and r.json()["user"]["email"] is None
    h = _h(r)
    assert client.post(f"{API}/auth/login", json={"identifier": "+91 98111 22333", "password": "phone-pass-1"}).status_code == 200
    # link an email and a username to the same account: all three now sign in
    u = client.patch(f"{API}/me/contact", headers=h, json={"email": "priya@example.com", "username": "priya", "current_password": "phone-pass-1"}).json()
    assert u["email"] == "priya@example.com" and u["username"] == "priya"
    for ident in ("priya@example.com", "PRIYA", "9811122333"):
        assert client.post(f"{API}/auth/login", json={"identifier": ident, "password": "phone-pass-1"}).status_code == 200, ident
    # the same number or email can't be used twice
    assert client.post(f"{API}/auth/register", json={"phone": "+919811122333", "password": "x-pass-123"}).status_code == 409
    assert client.post(f"{API}/auth/register", json={"email": "Priya@Example.com", "password": "x-pass-123"}).status_code == 409
    # changing contact details needs the current password
    assert client.patch(f"{API}/me/contact", headers=h, json={"phone": "98111 99999"}).status_code == 400


def test_register_validation(client):
    assert client.post(f"{API}/auth/register", json={"password": "abcdefgh1"}).status_code == 422  # neither email nor phone
    assert client.post(f"{API}/auth/register", json={"email": "bad", "password": "abcdefgh1"}).status_code == 422
    assert client.post(f"{API}/auth/register", json={"email": "z@example.com", "password": "short"}).status_code == 422
    assert client.post(f"{API}/auth/register", json={"email": "z@example.com", "password": "12345678"}).status_code == 422


def test_forgot_and_reset_password_signs_out_old_sessions(client, outbox):
    old = _h(client.post(f"{API}/auth/register", json={"email": "ravi@example.com", "phone": "97000 11111", "password": "first-pass-1"}))
    assert client.get(f"{API}/me", headers=old).status_code == 200
    r = client.post(f"{API}/auth/forgot", json={"identifier": "97000 11111"}).json()  # found by mobile, code goes to the email
    assert r["channel"] == "email" and outbox[-1][1] == "ravi@example.com"
    assert client.post(f"{API}/auth/reset", json={"identifier": "ravi@example.com", "code": "000000", "password": "new-pass-22"}).status_code == 400
    r = client.post(f"{API}/auth/reset", json={"identifier": "ravi@example.com", "code": _code(outbox), "password": "new-pass-22"})
    assert r.status_code == 200
    assert client.get(f"{API}/me", headers=old).status_code == 401  # sessions from before the reset are signed out
    assert client.post(f"{API}/auth/login", json={"identifier": "ravi@example.com", "password": "first-pass-1"}).status_code == 401
    assert client.post(f"{API}/auth/login", json={"identifier": "ravi@example.com", "password": "new-pass-22"}).status_code == 200
    # codes are single-use, and unknown accounts get the same neutral answer
    assert client.post(f"{API}/auth/reset", json={"identifier": "ravi@example.com", "code": _code(outbox), "password": "again-pass-3"}).status_code == 400
    assert client.post(f"{API}/auth/forgot", json={"identifier": "nobody@example.com"}).json()["ok"] is True


def test_change_password(client):
    r = client.post(f"{API}/auth/register", json={"email": "meena@example.com", "password": "meena-pass-1"})
    h = _h(r)
    assert client.post(f"{API}/me/password", headers=h, json={"current_password": "wrong", "new_password": "meena-pass-2"}).status_code == 400
    r2 = client.post(f"{API}/me/password", headers=h, json={"current_password": "meena-pass-1", "new_password": "meena-pass-2"})
    assert r2.status_code == 200 and client.get(f"{API}/me", headers=_h(r2)).status_code == 200


def test_owner_account_and_user_tools(client, admin):
    me = client.get(f"{API}/me", headers=admin).json()
    assert me["username"] == "admin" and me["is_admin"] and not me["must_change_password"]
    users = client.get(f"{API}/admin/users", headers=admin).json()["items"]
    target = next(u for u in users if u["email"] == "meena@example.com")
    temp = client.post(f"{API}/admin/users/{target['id']}/reset-password", headers=admin).json()["temporary_password"]
    r = client.post(f"{API}/auth/login", json={"identifier": "meena@example.com", "password": temp})
    assert r.status_code == 200 and r.json()["user"]["must_change_password"]
    # the last administrator can't be removed
    assert client.patch(f"{API}/admin/users/{me['id']}", headers=admin, json={"is_admin": False}).status_code == 409


def test_sign_in_is_rate_limited(client):
    for _ in range(12):
        client.post(f"{API}/auth/login", json={"identifier": "target@example.com", "password": "guess"})
    assert client.post(f"{API}/auth/login", json={"identifier": "target@example.com", "password": "guess"}).status_code == 429


def test_admin_can_add_email_and_phone(client, admin):
    u = client.patch(f"{API}/me/contact", headers=admin, json={"email": "", "phone": "98222 33444", "username": "admin", "current_password": "owner-pass-123"})
    assert u.status_code == 200 and u.json()["phone"] == "+919822233444"
    u = client.patch(f"{API}/me/contact", headers=admin, json={"email": "owner@example.com", "phone": "+919822233444", "username": "admin", "current_password": "owner-pass-123"}).json()
    assert u["email"] == "owner@example.com"
    for ident in ("admin", "owner@example.com", "98222 33444"):
        assert client.post(f"{API}/auth/login", json={"identifier": ident, "password": "owner-pass-123"}).status_code == 200


def test_forgot_password_is_off_by_default(client):
    assert client.post(f"{API}/auth/forgot", json={"identifier": "someone@example.com"}).status_code == 404
    assert client.get(f"{API}/auth/providers").json()["password_reset"] is False
