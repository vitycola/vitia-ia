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
    if settings.auth_disabled:
        if settings.environment != "development":
            raise RuntimeError(
                "AUTH_DISABLED can only be set in development environment, "
                f"current: {settings.environment!r}"
            )
        logger.warning("auth_disabled — skipping JWT validation (dev only)")
        return CurrentUser(user_id="dev-user")

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        claims = verify_jwt(token, settings.supabase_jwks_url)
    except AuthError as err:
        logger.warning(
            "auth_failed",
            extra={"reason": err.reason, "jwks_url": settings.supabase_jwks_url},
        )
        detail = (
            f"Auth failed: {err.reason}"
            if settings.environment != "production"
            else "Could not validate credentials"
        )
        raise HTTPException(
            status_code=401,
            detail=detail,
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
