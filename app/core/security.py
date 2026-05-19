import jwt
from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash
from app.core.config import settings

# Instanciamos el hasheador con el algoritmo recomendado (Argon2)
password_hash = PasswordHash.recommended()


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


# --- FUNCIÓN PARA CREAR JWT ---
def create_access_token(data: dict) -> str:
    to_encode = data.copy()

    # Calculamos cuándo expira el token
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    # Firmamos el token con la llave secreta del .env
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    return encoded_jwt


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
    
    # Agregamos una bandera para distinguirlo en caso de que intenten usarlo como access token
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    
    return encoded_jwt, expire