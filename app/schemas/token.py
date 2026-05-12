from uuid import UUID

from pydantic import BaseModel, Field


# Lo que la API devuelve cuando el login es exitoso
class Token(BaseModel):
    access_token: str
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