from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from .config import settings
from .schemas import UserClaims

security = HTTPBearer()

async def get_current_user(creds: HTTPAuthorizationCredentials = Security(security)) -> UserClaims:
    token = creds.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGO])
        return UserClaims(**payload)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(*allowed_roles):
    """
    Allow access only if user's role is in the allowed_roles.
    """
    async def _checker(user: UserClaims = Security(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Access denied for role '{user.role}'")
        return user
    return _checker
