from uuid import UUID
import re

from pydantic import BaseModel, Field, field_validator


# ==========================================
# CONFIGURACIÓN DE CONTRASEÑAS
# ==========================================

PASSWORD_REGEX = (
    r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)"
    r"(?=.*[@$!%*?&._-])[A-Za-z\d@$!%*?&._-]{8,}$"
)

PASSWORD_ERROR_MSG = (
    "La contraseña debe tener mínimo 8 caracteres, una mayúscula, "
    "una minúscula, un número y un carácter especial."
)


# ==========================================
# JWT / LOGIN
# ==========================================
# Lo que la API devuelve cuando el login es exitoso
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# Lo que guardaremos dentro del token JWT
class TokenPayload(BaseModel):
    sub: str | None = None


# Datos que recibirá el endpoint /auth/login
class LoginRequest(BaseModel):
    curp: str = Field(..., min_length=18, max_length=18)
    password: str


# Datos para configurar Google Authenticator
class TwoFactorSetupRequest(BaseModel):
    user_id: UUID


# Datos para verificar o habilitar 2FA
class TwoFactorVerifyRequest(BaseModel):
    user_id: UUID
    code: str = Field(..., min_length=6, max_length=6)

class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TempTokenRequest(BaseModel):
    temp_token: str


class TempTokenVerifyRequest(BaseModel):
    temp_token: str
    code: str = Field(..., min_length=6, max_length=6)


class RedirectCodeRequest(BaseModel):
    redirect_url: str


class RedirectCodeResponse(BaseModel):
    code: str
    expires_in: int


class ExchangeCodeRequest(BaseModel):
    code: str
    

# ==========================================
# RECUPERACIÓN DE CONTRASEÑA
# ==========================================

class RestablecerPasswordRequest(BaseModel):
    """
    Body para restablecer la contraseña usando el token enviado por correo.
    """

    token: str
    password_nueva: str = Field(..., min_length=8)

    @field_validator("password_nueva")
    @classmethod
    def validar_password_fuerte(cls, v: str) -> str:
        if not re.match(PASSWORD_REGEX, v):
            raise ValueError(PASSWORD_ERROR_MSG)
        return v