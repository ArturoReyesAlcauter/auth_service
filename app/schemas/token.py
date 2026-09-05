import re
from typing import Literal
from uuid import UUID

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

class Token(BaseModel):
    """Tokens entregados cuando la autenticación termina correctamente."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    """
    Respuesta del nuevo contrato de autenticación.

    El access token se entrega al frontend mediante JSON.
    El refresh token se administra mediante una cookie HttpOnly
    y no se expone a JavaScript.
    """

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Contenido básico almacenado dentro de un JWT."""

    sub: str | None = None


class LoginRequest(BaseModel):
    """Credenciales de inicio de sesión."""

    curp: str = Field(
        ...,
        min_length=18,
        max_length=18,
    )
    password: str


# ==========================================
# RESPUESTAS DEL FLUJO 2FA
# ==========================================

class TwoFactorSetupRequiredResponse(BaseModel):
    """
    Respuesta de /auth/login cuando el usuario todavía
    no ha configurado la autenticación en dos pasos.
    """

    status: Literal[
        "two_factor_setup_required"
    ] = "two_factor_setup_required"

    temp_token: str
    temp_token_expires_in: int

    two_factor_configured: Literal[False] = False

    message: str


class TwoFactorVerificationRequiredResponse(BaseModel):
    """
    Respuesta de /auth/login cuando el usuario ya tiene
    configurada la autenticación en dos pasos.
    """

    status: Literal[
        "pending_2fa"
    ] = "pending_2fa"

    temp_token: str
    temp_token_expires_in: int

    two_factor_configured: Literal[True] = True

    message: str


class TwoFactorSetupResponse(BaseModel):
    """
    Información que necesita el frontend para mostrar
    la configuración de Google Authenticator.
    """

    status: Literal[
        "two_factor_setup_required"
    ] = "two_factor_setup_required"

    two_factor_configured: Literal[False] = False

    qr_uri: str
    manual_key: str


# ==========================================
# REQUESTS DEL FLUJO 2FA
# ==========================================

class TwoFactorSetupRequest(BaseModel):
    """
    Esquema anterior conservado temporalmente por compatibilidad.

    El flujo vigente utiliza TempTokenRequest.
    """

    user_id: UUID


class TwoFactorVerifyRequest(BaseModel):
    """
    Esquema anterior conservado temporalmente por compatibilidad.

    El flujo vigente utiliza TempTokenVerifyRequest.
    """

    user_id: UUID
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
    )


class TempTokenRequest(BaseModel):
    """Token temporal recibido desde /auth/login."""

    temp_token: str


class TempTokenVerifyRequest(BaseModel):
    """Token temporal y código TOTP de seis dígitos."""

    temp_token: str

    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )


# ==========================================
# REFRESH TOKEN Y REDIRECCIÓN SSO
# ==========================================

class RefreshTokenRequest(BaseModel):
    refresh_token: str


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
    Body para restablecer la contraseña usando el token
    enviado por correo.
    """

    token: str

    password_nueva: str = Field(
        ...,
        min_length=8,
    )

    @field_validator("password_nueva")
    @classmethod
    def validar_password_fuerte(
        cls,
        value: str,
    ) -> str:
        if not re.match(
            PASSWORD_REGEX,
            value,
        ):
            raise ValueError(
                PASSWORD_ERROR_MSG,
            )

        return value