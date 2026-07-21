from functools import lru_cache

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from src.config import get_settings

JWKS_TIMEOUT = 5  # seconds


class AuthError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@lru_cache(maxsize=1)
def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    """Return a cached PyJWKClient instance for the given JWKS URL."""
    return PyJWKClient(jwks_url, timeout=JWKS_TIMEOUT, cache_keys=True)


def verify_jwt(token: str, jwks_url: str) -> dict:
    """Decode and verify an ES256 JWT using JWKS. Raises AuthError on any failure."""
    try:
        settings = get_settings()
        issuer = f"{settings.supabase_url}/auth/v1"
        jwks_client = _get_jwks_client(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
            issuer=issuer,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as err:
        raise AuthError(reason="expired") from err
    except jwt.InvalidSignatureError as err:
        raise AuthError(reason="invalid_signature") from err
    except jwt.InvalidAudienceError as err:
        raise AuthError(reason="invalid_audience") from err
    except jwt.InvalidIssuerError as err:
        raise AuthError(reason="invalid_issuer") from err
    except jwt.DecodeError as err:
        raise AuthError(reason="decode_error") from err
    except PyJWKClientConnectionError as err:
        raise AuthError(reason="jwks_unreachable") from err
    except PyJWKClientError as err:
        raise AuthError(reason=f"jwks_error:{type(err).__name__}") from err
    except (jwt.InvalidTokenError, jwt.PyJWTError) as err:
        raise AuthError(reason=f"invalid_token:{type(err).__name__}") from err
    except Exception as err:
        raise AuthError(reason=f"unexpected:{type(err).__name__}") from err
