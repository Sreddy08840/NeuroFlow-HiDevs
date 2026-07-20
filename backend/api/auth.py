from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from backend.config import settings


router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token to use in Authorization header")
    token_type: str = Field(..., description="Token type, always 'bearer'")
    expires_in: int = Field(..., description="Token expiration time in seconds")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        client_id: str = payload.get("sub")
        scopes: list = payload.get("scopes", [])
        if client_id is None:
            raise credentials_exception
        return {"client_id": client_id, "scopes": scopes}
    except JWTError:
        raise credentials_exception


def require_scope(required_scope: str):
    def dependency(current_user: dict = Depends(get_current_user)):
        if required_scope not in current_user["scopes"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return dependency


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Obtain access token",
    description="Exchange client ID and secret for a JWT access token. Tokens are valid for 24 hours by default."
)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # In production, use proper hashing (bcrypt) for client secrets!
    client_data = settings.jwt_clients.get(form_data.username)
    if not client_data or client_data["client_secret"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect client ID or secret",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": form_data.username, "scopes": client_data["scopes"]},
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60
    }
