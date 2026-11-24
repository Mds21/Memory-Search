"""Verifies Google Identity Services ID tokens locally against Google's published signing keys.

The browser gets a signed JWT from Google; we check the signature (RS256, keys from Google's JWKS, cached),
the audience (our client id), the issuer, expiry and that Google has verified the email.
"""
from __future__ import annotations

import jwt
from fastapi import HTTPException

JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("accounts.google.com", "https://accounts.google.com")
_jwks = jwt.PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600)


def verify(credential: str, client_id: str) -> dict:
    try:
        key = _jwks.get_signing_key_from_jwt(credential).key
        claims = jwt.decode(credential, key, algorithms=["RS256"], audience=client_id, leeway=60,
                            options={"require": ["exp", "iat", "sub", "aud", "iss"]})
    except jwt.PyJWKClientError:
        raise HTTPException(503, "Could not reach Google to check the sign-in. Try again in a moment.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Google sign-in could not be verified. Try again.")
    if claims.get("iss") not in ISSUERS:
        raise HTTPException(401, "Google sign-in could not be verified. Try again.")
    if not claims.get("email") or not claims.get("email_verified"):
        raise HTTPException(401, "Your Google account has no verified email address")
    return claims
