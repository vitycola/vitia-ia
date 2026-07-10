import jwt
from jwt import PyJWKClient


class AuthError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def verify_jwt(token: str, jwks_url: str) -> dict:
    """Decode and verify an ES256 JWT using JWKS. Raises AuthError on any failure."""
    try:
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(token, signing_key.key, algorithms=["ES256"])
    except jwt.ExpiredSignatureError as err:
        raise AuthError(reason="expired") from err
    except jwt.InvalidSignatureError as err:
        raise AuthError(reason="invalid_signature") from err
    except (jwt.InvalidTokenError, jwt.PyJWTError) as err:
        raise AuthError(reason="malformed") from err
    except Exception as err:
        raise AuthError(reason="jwks_error") from err
