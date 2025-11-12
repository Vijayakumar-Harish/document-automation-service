from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from .config import settings
from .schemas import UserClaims
from jwt import InvalidTokenError, ExpiredSignatureError
from .metrics_registry import errors_total

security = HTTPBearer()

async def get_current_user(creds: HTTPAuthorizationCredentials = Security(security)) -> UserClaims:
    token = creds.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGO], options={"require":["exp","iat"]})
        return UserClaims(**payload)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        errors_total.inc()
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
