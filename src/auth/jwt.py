import jwt


class AuthError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def verify_jwt(token: str, secret: str) -> dict:
    """Decode and verify an HS256 JWT. Raises AuthError on any failure."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as err:
        raise AuthError(reason="expired") from err
    except jwt.InvalidSignatureError as err:
        raise AuthError(reason="invalid_signature") from err
    except (jwt.InvalidTokenError, jwt.PyJWTError) as err:
        raise AuthError(reason="malformed") from err
