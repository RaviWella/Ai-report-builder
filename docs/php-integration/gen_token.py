#!/usr/bin/env python3
"""
Generate a Report Builder access_token (JWT) for manual testing.

A JWT is 3 base64url parts joined by dots:  header.payload.signature
  - header    : {"alg":"HS256","typ":"JWT"}
  - payload   : the claims the backend reads (sub, tenant_id, role, iat, exp, iss)
  - signature : HMAC-SHA256(header.payload, SECRET)   <- can't be done by hand

Edit the 4 values below, run `python3 gen_token.py`, copy a URL into the browser.
Zero dependencies (Python stdlib only).
"""
import base64, hashlib, hmac, json, os, time, urllib.parse

# Values come from env vars if set (so the secret never lives in this file),
# otherwise the defaults below.  Override like:
#     JWT_SECRET='...' python3 gen_token.py
# ── DEFAULTS ───────────────────────────────────────────────────────────────
SECRET = os.environ.get("JWT_SECRET", "PUT-THE-PRODUCTION-JWT_SECRET-HERE")  # == backend JWT_SECRET
TENANT = os.environ.get("TENANT", "etsteasuat")        # -> routes to hrm_wh_etsteasuat
ROLE   = os.environ.get("ROLE", "client_hr_admin")     # client_hr_admin | client_end_user | support_admin
USER   = os.environ.get("USER_ID", "u-test")           # any user id (for audit)
# ───────────────────────────────────────────────────────────────────────────

if SECRET.startswith("PUT-"):
    raise SystemExit("Set the real secret:  JWT_SECRET='<deployed JWT_SECRET>' python3 gen_token.py")

BASE = "https://mint-analytics-v2.minchy.ai"
TTL  = 3600  # seconds the token is valid (1 hour — comfortable for a work session)


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def mint() -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": USER, "tenant_id": TENANT, "role": ROLE,
        "iat": now, "exp": now + TTL, "iss": "MintHRM Report Builder",
    }
    seg = [
        b64url(json.dumps(header, separators=(",", ":")).encode()),
        b64url(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    sig = hmac.new(SECRET.encode(), ".".join(seg).encode(), hashlib.sha256).digest()
    seg.append(b64url(sig))
    return ".".join(seg)


token = mint()
print("\nTOKEN:\n" + token)
print("\nBUILDER URL (admin):\n" + BASE + "/#access_token=" + urllib.parse.quote(token))
print("\nVIEWER URL (end user):\n" + BASE + "/viewer#access_token=" + urllib.parse.quote(token))
print("\nTest the API directly:\n  curl -H 'Authorization: Bearer " + token + "' \\\n       "
      + BASE + "/api/v1/semantic/fields\n")
