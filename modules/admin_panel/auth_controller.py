import os
import uuid

import redis
import dotenv

from datetime import timedelta

from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from fastapi import APIRouter, Depends, HTTPException, status, Security, Response
from fastapi_jwt import JwtAccessBearer, JwtAuthorizationCredentials, JwtRefreshBearer

from modules.models import AdminUser

dotenv.load_dotenv('secrets.env')

SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = 'HS256'

redis_cli = redis.Redis(decode_responses=True)

access_security = JwtAccessBearer(
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    access_expires_delta=timedelta(minutes=15),
)

refresh_security = JwtRefreshBearer(
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    refresh_expires_delta=timedelta(days=7),
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

panel_auth_router = APIRouter(tags=["Panel Auth 🔐"], prefix='/panel/auth')


def get_user_from_jwt(credentials: JwtAuthorizationCredentials = Security(access_security)):
    return credentials.subject

def revoke_token(jti: str):
    """Добавить jti в чёрный список на 24 часа (или до истечения RT)"""
    redis_cli.setex(f"blacklist:jti:{jti}", 86400, "1")

def is_token_revoked(jti: str) -> bool:
    """Проверить, отозван ли токен"""
    return redis_cli.exists(f"blacklist:jti:{jti}") == 1


def authenticate_user(username: str, password: str) -> bool:
    try:
        expected_username = os.getenv("PANEL_USERNAME")
        expected_hashed_password = os.getenv("PANEL_PASSWORD")

        if not expected_username or not expected_hashed_password:
            raise RuntimeError("❌ PANEL_USERNAME или PANEL_PASSWORD не заданы в .env!")

        if username != expected_username:
            return False

        return pwd_context.verify(password, expected_hashed_password)
    except UnknownHashError as e:
        print("[Panel] Ошибка! Неизвестный хэш пароля.", e)
        return False


def authorize_user(credentials: JwtAuthorizationCredentials = Depends(access_security)):
    jti = credentials.jti
    if not jti:
        raise HTTPException(status_code=400, detail="Token doesn't contains jwt!")

    if is_token_revoked(jti):
        raise HTTPException(status_code=401, detail="Access token expired!")

    return credentials


@panel_auth_router.post("/login")
async def panel_login(user: AdminUser, response: Response):
    if not authenticate_user(user.username, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong username or password!",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = str(uuid.uuid4())

    access_token = access_security.create_access_token(
        subject=user.model_dump(),
        unique_identifier=jti
    )

    refresh_token = refresh_security.create_refresh_token(
        subject=user.model_dump(),
        unique_identifier=jti
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@panel_auth_router.post("/refresh")
async def refresh_token(credentials: JwtAuthorizationCredentials = Depends(refresh_security)):
    """
    Получает новый access_token по refresh_token.
    Не требует логина — только валидный refresh_token.
    """
    jti = credentials.jti
    if not jti:
        raise HTTPException(status_code=400, detail="Token doesn't contains jwt!")

    if is_token_revoked(jti):
        raise HTTPException(status_code=401, detail="Refresh Token expired!")

    new_access_token = access_security.create_access_token(subject=credentials.subject)
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }

@panel_auth_router.post("/logout")
async def logout(response: Response, credentials: JwtAuthorizationCredentials = Depends(refresh_security)):
    jti = credentials.jti
    if not jti:
        raise HTTPException(status_code=400, detail="Token doesn't contains jwt!")

    revoke_token(jti)

    response.delete_cookie(key="refresh_token", path="/")

    return {"message": "Successfully logout!"}
