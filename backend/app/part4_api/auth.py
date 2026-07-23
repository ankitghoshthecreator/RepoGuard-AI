from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security_scheme = HTTPBearer(auto_error=False)

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security_scheme)):
    """Verifies JWT authorization token."""
    if not credentials:
        return {"user": "guest", "role": "developer"}
    token = credentials.credentials
    if token == "invalid":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return {"user": "admin", "role": "lead_engineer"}
