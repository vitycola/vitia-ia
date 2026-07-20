import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.jwt import AuthError, verify_jwt
from src.auth.models import CurrentUser
from src.config import Settings, get_settings

logger = logging.getLogger("vitia.auth")

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    logger.info("auth_attempt", extra={"token_prefix": token[:30] if token else None})
    try:
        claims = verify_jwt(token, settings.supabase_jwks_url)
    except AuthError as err:
        logger.warning(
            "auth_failed",
            extra={
                "reason": err.reason,
                "token_prefix": token[:30] if token else None,
                "jwks_url": settings.supabase_jwks_url,
            },
        )
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(user_id=sub)
