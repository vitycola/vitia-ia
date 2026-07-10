from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.jwt import AuthError, verify_jwt
from src.auth.models import CurrentUser
from src.config import Settings, get_settings

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

    try:
        claims = verify_jwt(
            credentials.credentials,
            settings.supabase_jwks_url,
        )
    except AuthError as err:
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
