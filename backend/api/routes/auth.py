from fastapi import APIRouter, HTTPException, Response, Request, status
from fastapi.responses import JSONResponse
from core.auth import (
    verify_password, create_access_token,
    create_refresh_token, decode_token
)
from core.config import settings
from schemas import LoginRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response):
    # Проверяем логин
    if body.login != settings.admin_login:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    # Проверяем пароль против bcrypt хэша из .env
    if not verify_password(body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    token_data = {"sub": body.login}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Refresh token в httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.jwt_refresh_ttl_days * 24 * 3600,
        path="/api/auth/refresh",
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token не найден")

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный refresh token")

    login = payload.get("sub")
    if not login or login != settings.admin_login:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен")

    access_token = create_access_token({"sub": login})
    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token", path="/api/auth/refresh")
    return {"detail": "Вышли из системы"}


@router.get("/me")
async def me(request: Request):
    from core.auth import get_current_user
    from fastapi import Depends
    # Быстрая проверка токена
    token = request.cookies.get("access_token") or (
        request.headers.get("Authorization", "").replace("Bearer ", "") or None
    )
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    payload = decode_token(token)
    return {"login": payload.get("sub")}
