"""Google sign-in and direct Cloud Run IAP use separate issuers, audiences and keys."""

from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
import re
import threading
import time
from urllib.parse import urlencode, urlsplit

import httpx
import jwt

from invitations.policy import address

IAP_ISSUER = "https://cloud.google.com/iap"
IAP_KEYS = "https://www.gstatic.com/iap/verify/public_key-jwk"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
AUTHORIZATION = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_KEYS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_PREFIX = "accounts.google.com:"
KID = re.compile(r"[A-Za-z0-9_.-]{1,128}")
STAGING_AUDIENCE = re.compile(
    r"/projects/[1-9][0-9]*/locations/[a-z]+(?:-[a-z]+)+[1-9][0-9]*"
    r"/services/[a-z][a-z0-9-]{0,54}-staging"
)


class Denied(Exception):
    """Safe to map to a generic denial without exposing assertion contents."""


class Unavailable(Exception):
    """The identity provider or its keys could not be verified."""


def principal_key(namespaced_subject):
    # Same opaque key contract as week2.iap.Principal, without importing the workspace.
    return "iap:" + hashlib.sha256((IAP_ISSUER + "\0" + namespaced_subject).encode()).hexdigest()


@dataclass(frozen=True)
class Settings:
    origin: str
    audience: str
    client_id: str
    client_secret: str = field(repr=False)
    owner_email: str = field(repr=False)
    mode: str
    owner_pin: str | None = field(default=None, repr=False)

    def __post_init__(self):
        if not re.fullmatch(r"https://[a-z0-9.-]+(?::[0-9]{1,5})?", self.origin):
            raise ValueError("Configure an exact HTTPS staging origin")
        urlsplit(self.origin).port  # also validate an explicit port
        if not STAGING_AUDIENCE.fullmatch(self.audience):
            raise ValueError("Configure the exact IAP audience of a service ending in -staging")
        if (
            not re.fullmatch(r"[A-Za-z0-9-]+\.apps\.googleusercontent\.com", self.client_id)
            or not self.client_secret.strip()
        ):
            raise ValueError("Configure the staging web OAuth client")
        object.__setattr__(self, "owner_email", address(self.owner_email))
        if self.mode == "enrolled":
            if not re.fullmatch(r"iap:[0-9a-f]{64}", self.owner_pin or ""):
                raise ValueError("Enrolled mode requires an explicit owner pin")
        elif self.mode != "verify-only" or self.owner_pin is not None:
            raise ValueError("Select verify-only or configure the enrolled owner")

    @classmethod
    def from_env(cls):
        prefix = "INVITATION_STAGE_"
        return cls(
            origin=os.environ[prefix + "ORIGIN"],
            audience=os.environ[prefix + "IAP_AUDIENCE"],
            client_id=os.environ[prefix + "CLIENT_ID"],
            client_secret=os.environ[prefix + "CLIENT_SECRET"],
            owner_email=os.environ[prefix + "OWNER_EMAIL"],
            mode=os.environ[prefix + "MODE"],
            owner_pin=os.environ.get(prefix + "OWNER_PIN"),
        )

    @property
    def callback(self):
        return self.origin + "/auth/callback"

    @property
    def scope_key(self):
        # A fresh login is mandatory after enrollment, owner transfer, or client change.
        fields = (
            self.origin,
            self.audience,
            self.client_id,
            self.owner_email,
            self.mode,
            self.owner_pin,
        )
        return hashlib.sha256(json.dumps(fields).encode()).hexdigest()


def read_json(client, method, url, **kwargs):
    try:
        with client.stream(method, url, timeout=5, follow_redirects=False, **kwargs) as response:
            if method == "POST" and response.status_code == 400:
                raise Denied()
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes(chunk_size=8192):
                body.extend(chunk)
                if len(body) > 65536:
                    raise Unavailable()
            doc = json.loads(body)
            if not isinstance(doc, dict):
                raise Unavailable()
            return doc, response.headers
    except (httpx.HTTPError, ValueError, RecursionError):
        raise Unavailable() from None


class SigningKeys:
    """Each provider has a fixed endpoint and algorithm, a bounded cache and refresh cooldown."""

    def __init__(self, client, url, algorithm, clock):
        self.client = client
        self.url = url
        self.algorithm = algorithm
        self.clock = clock
        self.lock = threading.Lock()
        self.keys = {}
        self.expires = self.next_refresh = float("-inf")

    def get(self, kid):
        if not isinstance(kid, str) or not KID.fullmatch(kid):
            raise Denied()
        with self.lock:
            now = self.clock()
            if now < self.expires and kid in self.keys:
                return self.keys[kid]
            if now < self.next_refresh:
                if now >= self.expires:
                    raise Unavailable()
                raise Denied()
            self.next_refresh = now + 10
            doc, headers = read_json(self.client, "GET", self.url)
            rows = doc.get("keys")
            if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
                raise Unavailable()
            keys = {}
            for row in rows:
                if not isinstance(row, dict):
                    raise Unavailable()
                ident = row.get("kid")
                if (
                    not isinstance(ident, str)
                    or not KID.fullmatch(ident)
                    or ident in keys
                    or row.get("use", "sig") != "sig"
                    or row.get("alg", self.algorithm) != self.algorithm
                    or "d" in row
                ):
                    raise Unavailable()
                if self.algorithm == "ES256":
                    if (row.get("kty"), row.get("crv")) != ("EC", "P-256"):
                        raise Unavailable()
                elif row.get("kty") != "RSA":
                    raise Unavailable()
                try:
                    keys[ident] = jwt.PyJWK.from_dict(row, algorithm=self.algorithm).key
                except (jwt.PyJWTError, ValueError, TypeError, KeyError, OverflowError):
                    raise Unavailable() from None
            match = re.search(
                r"(?:^|,)\s*max-age=(\d{1,9})(?:\s*(?:,|$))", headers.get("cache-control", "")
            )
            self.expires = now + (min(int(match[1]), 3600) if match else 300)
            self.keys = keys
            if kid not in keys:
                raise Denied()
            return keys[kid]

    def verified(self, token, issuer, audience, required):
        if not isinstance(token, str) or not 0 < len(token) <= 16384 or not token.isascii():
            raise Denied()
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != self.algorithm or {"jku", "x5u", "crit", "jwk"} & header.keys():
                raise Denied()
            claims = jwt.decode(
                token,
                self.get(header.get("kid")),
                algorithms=[self.algorithm],
                issuer=issuer,
                audience=audience,
                leeway=30,
                options={
                    "require": ["iss", "sub", "aud", "iat", "exp", "email", *required],
                    "strict_aud": True,
                },
            )
            if (
                type(claims["iat"]) is not int
                or type(claims["exp"]) is not int
                or claims["iat"] >= claims["exp"]
                or not isinstance(claims["sub"], str)
                or not re.fullmatch(r"[!-~]{1,275}", claims["sub"])
            ):
                raise Denied()
            return claims
        except (jwt.PyJWTError, ValueError, TypeError, OverflowError, RecursionError, KeyError):
            raise Denied() from None


class GoogleIdentity:
    def __init__(self, settings, client, *, clock=time.monotonic):
        self.settings = settings
        self.client = client
        self.iap_keys = SigningKeys(client, IAP_KEYS, "ES256", clock)
        self.oidc_keys = SigningKeys(client, GOOGLE_KEYS, "RS256", clock)

    def iap(self, assertion):
        claims = self.iap_keys.verified(assertion, IAP_ISSUER, self.settings.audience, [])
        subject = claims["sub"]
        if (
            not subject.startswith(GOOGLE_PREFIX)
            or not 0 < len(subject) - len(GOOGLE_PREFIX) <= 255
            or claims.get("identity_source", "GOOGLE") != "GOOGLE"
            or "gcip" in claims
            or "workforce_identity" in claims
            or claims["email"] != self.settings.owner_email
            or claims["exp"] - claims["iat"] > 660
        ):
            raise Denied()
        key = principal_key(subject)
        if self.settings.owner_pin and not hmac.compare_digest(key, self.settings.owner_pin):
            raise Denied()
        return key

    def authorization_url(self, state, nonce, challenge):
        return (
            AUTHORIZATION
            + "?"
            + urlencode(
                {
                    "client_id": self.settings.client_id,
                    "redirect_uri": self.settings.callback,
                    "response_type": "code",
                    "scope": "openid email",
                    "state": state,
                    "nonce": nonce,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
        )

    def bind_code(self, code, verifier, nonce, iap_key):
        response, _ = read_json(
            self.client,
            "POST",
            TOKEN_ENDPOINT,
            data={
                "grant_type": "authorization_code",
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "code": code,
                "redirect_uri": self.settings.callback,
                "code_verifier": verifier,
            },
        )
        claims = self.oidc_keys.verified(
            response.get("id_token"),
            GOOGLE_ISSUERS,
            self.settings.client_id,
            ["nonce", "email_verified"],
        )
        if (
            claims["email_verified"] is not True
            or claims["email"] != self.settings.owner_email
            or claims.get("azp", self.settings.client_id) != self.settings.client_id
            or claims["nonce"] != nonce
            or len(claims["sub"]) > 255
            or not hmac.compare_digest(principal_key(GOOGLE_PREFIX + claims["sub"]), iap_key)
        ):
            raise Denied()
