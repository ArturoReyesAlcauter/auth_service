import jwt
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pwdlib import PasswordHash

from app.core.config import settings

# Instanciamos el hasheador con el algoritmo recomendado (Argon2)
password_hash = PasswordHash.recommended()


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


# --- FUNCIÓN PARA CREAR JWT DE ACCESO ---
def create_access_token(data: dict) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update(
        {
            "exp": expire,
            "type": "access",
        }
    )

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    return encoded_jwt


# --- FUNCIÓN PARA CREAR JWT TEMPORAL 2FA ---
def create_temp_token(data: dict, purpose: str, expire_minutes: int) -> str:
    """
    Crea un JWT temporal para continuar el flujo de 2FA.

    No debe usarse como Authorization Bearer ni para consumir endpoints
    protegidos. El campo purpose limita si sirve para setup_2fa o login_2fa.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

    to_encode.update(
        {
            "exp": expire,
            "type": "temp",
            "purpose": purpose,
        }
    )

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


# --- FUNCIÓN PARA LEER / VALIDAR JWT ---
def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )


def create_refresh_token(data: dict, expire_days: int = 7) -> tuple[str, datetime]:
    to_encode = data.copy()

    # Expiración de vida larga para el Refresh Token
    expire = datetime.now(timezone.utc) + timedelta(days=expire_days)

    # jti permite distinguir cada refresh token y soportar rotación/reuso.
    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
            "jti": str(uuid4()),
        }
    )

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    return encoded_jwt, expire
