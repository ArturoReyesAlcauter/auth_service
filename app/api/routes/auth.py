from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm


from app.api.dependencies import get_current_active_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_temp_token,
    decode_access_token,
)
from app.models.user import TokenUsuario, User, UsuarioAccion
from app.schemas.token import (
    ExchangeCodeRequest,
    RedirectCodeRequest,
    RedirectCodeResponse,
    RefreshTokenRequest,
    RestablecerPasswordRequest,
    TempTokenRequest,
    TempTokenVerifyRequest,
    Token,
    TwoFactorSetupRequiredResponse,
    TwoFactorSetupResponse,
    TwoFactorVerificationRequiredResponse,
)
from app.services import auth_service
from app.services.rate_limit_service import verificar_rate_limit
from app.services.session_service import validar_ultima_sesion_o_revocar


router = APIRouter(tags=["Autenticación"])


# --- FUNCIONES DE APOYO ---

def usuario_esta_activo(user: User) -> bool:
    """
    En el modelo anterior usabas user.is_active.
    En el modelo nuevo usamos la relación con cat_estatus_usuarios.
    """
    if not user.estatus:
        return False

    return user.estatus.nombre.lower() == "activo"


async def generar_payload_usuario(user: User) -> dict:
    """Extrae las acciones del usuario y prepara el payload del JWT."""
    acciones_db = await UsuarioAccion.filter(usuario_id=user.id).prefetch_related("accion")
    lista_acciones = [ua.accion.nombre for ua in acciones_db]

    return {
        "sub": str(user.id),
        "instancia_id": user.instancia_id,
        "entidad_federativa_id": user.entidad_federativa_id,
        "acciones": lista_acciones,
        "token_version": user.token_version,
    }


async def emitir_tokens_usuario(user: User) -> Token:
    """Genera access_token + refresh_token, guardando el refresh token en DB."""
    payload = await generar_payload_usuario(user)
    access_token = create_access_token(data=payload)

    refresh_token_str, expire_dt = create_refresh_token(
        {
            "sub": str(user.id),
            "token_version": user.token_version,
        },
        expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )

    await auth_service.store_refresh_token(
        user.id,
        refresh_token_str,
        expire_dt,
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token_str,
        token_type="bearer",
    )


async def obtener_usuario_desde_temp_token(temp_token: str, purpose: str) -> User:
    """Valida un temp_token 2FA y regresa el usuario asociado."""
    try:
        payload = decode_access_token(temp_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "TEMP_TOKEN_EXPIRED_OR_INVALID",
                "detail": "El token temporal expiró o no es válido.",
            },
        )

    user_id = payload.get("sub")
    token_version = payload.get("token_version")

    if (
        not user_id
        or payload.get("type") != "temp"
        or payload.get("purpose") != purpose
        or token_version is None
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "TEMP_TOKEN_INVALID_PURPOSE",
                "detail": "El token temporal no corresponde al flujo solicitado.",
            },
        )

    user = await User.get_or_none(id=user_id).prefetch_related(
        "estatus",
        "instancia",
    )

    if not user or not usuario_esta_activo(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "USER_INACTIVE",
                "detail": "Usuario inactivo o suspendido.",
            },
        )

    if user.token_version != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "TEMP_TOKEN_REVOKED",
                "detail": "El token temporal fue revocado por cambios en la cuenta.",
            },
        )

    return user


# --- 1. LOGIN PASO 1: Validar credenciales ---

@router.post(
    "/login",
    response_model=(
        TwoFactorSetupRequiredResponse
        | TwoFactorVerificationRequiredResponse
    ),
)
async def login_access_token(
    request: Request,
    form_data: Annotated[
        OAuth2PasswordRequestForm,
        Depends(),
    ],
):
    """
    Paso 1: valida CURP y contraseña.

    No entrega tokens de sesión todavía.

    Devuelve un token temporal para continuar con:
    - la configuración inicial de 2FA; o
    - la verificación de un 2FA ya configurado.
    """

    ip_cliente = (
        request.client.host
        if request.client
        else "unknown"
    )

    verificar_rate_limit(
        key=f"login:ip:{ip_cliente}",
        max_intentos=20,
        ventana_segundos=60,
        mensaje=(
            "Demasiados intentos de inicio de sesión "
            "desde esta IP. Intenta de nuevo en un momento."
        ),
    )

    user = await auth_service.authenticate_user(
        curp=form_data.username.upper().strip(),
        password=form_data.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "detail": "CURP o contraseña incorrectos",
            },
        )

    if not usuario_esta_activo(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "USER_INACTIVE",
                "detail": "Usuario inactivo",
            },
        )

    await validar_ultima_sesion_o_revocar(user)

    if user.is_2fa_enabled:
        expire_minutes = 10

        temp_token = create_temp_token(
            data={
                "sub": str(user.id),
                "token_version": user.token_version,
            },
            purpose="login_2fa",
            expire_minutes=expire_minutes,
        )

        return TwoFactorVerificationRequiredResponse(
            temp_token=temp_token,
            temp_token_expires_in=(
                expire_minutes * 60
            ),
            message=(
                "Ingresa tu código de "
                "Google Authenticator."
            ),
        )

    expire_minutes = 60

    temp_token = create_temp_token(
        data={
            "sub": str(user.id),
            "token_version": user.token_version,
        },
        purpose="setup_2fa",
        expire_minutes=expire_minutes,
    )

    return TwoFactorSetupRequiredResponse(
        temp_token=temp_token,
        temp_token_expires_in=(
            expire_minutes * 60
        ),
        message=(
            "Es obligatorio configurar "
            "la seguridad de 2 pasos."
        ),
    )

# --- 2. LOGIN PASO 2: Validar el código 2FA ---

@router.post("/login/2fa", response_model=Token)
async def login_verify_2fa(
    request: Request,
    data: TempTokenVerifyRequest,
):
    """Verifica el código TOTP y entrega tokens de sesión."""

    ip_cliente = request.client.host if request.client else "unknown"

    verificar_rate_limit(
        key=f"login_2fa:ip:{ip_cliente}",
        max_intentos=20,
        ventana_segundos=60,
        mensaje="Demasiados intentos de verificación 2FA desde esta IP.",
    )

    user = await obtener_usuario_desde_temp_token(data.temp_token, purpose="login_2fa")

    if not user.is_2fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TWO_FACTOR_NOT_ENABLED", "detail": "2FA no está habilitado."},
        )

    is_valid = auth_service.verify_totp_code(user.totp_secret, data.code)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TWO_FACTOR_CODE_INVALID", "detail": "Código de verificación incorrecto."},
        )

    return await emitir_tokens_usuario(user)


# --- RUTAS DE CONFIGURACIÓN 2FA ---

@router.post(
    "/setup",
    response_model=TwoFactorSetupResponse,
)
async def setup_2fa(
    request: Request,
    response: Response,
    data: TempTokenRequest,
) -> TwoFactorSetupResponse:
    """
    Genera o recupera la configuración inicial de 2FA.

    Devuelve la URI otpauth para que el frontend genere
    el código QR y la clave manual para configuración.
    """

    ip_cliente = (
        request.client.host
        if request.client
        else "unknown"
    )

    verificar_rate_limit(
        key=f"setup_2fa:ip:{ip_cliente}",
        max_intentos=10,
        ventana_segundos=60,
        mensaje=(
            "Demasiadas solicitudes para configurar "
            "2FA desde esta IP."
        ),
    )

    user = await obtener_usuario_desde_temp_token(
        data.temp_token,
        purpose="setup_2fa",
    )

    if user.is_2fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "TWO_FACTOR_ALREADY_ENABLED",
                "detail": "2FA ya está activado.",
            },
        )

    secret = user.totp_secret

    if not secret:
        secret = auth_service.generate_totp_secret()
        user.totp_secret = secret

        await user.save(
            update_fields=[
                "totp_secret",
                "fecha_actualizacion",
            ]
        )

    qr_uri = auth_service.get_provisioning_uri(
        secret=secret,
        account_name=user.correo_electronico,
    )
    
    response.headers["Cache-Control"] = (
    "no-store, no-cache, must-revalidate, private"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return TwoFactorSetupResponse(
        qr_uri=qr_uri,
        manual_key=secret,
    )


@router.post(
    "/enable",
    response_model=Token,
)
async def enable_2fa(
    request: Request,
    data: TempTokenVerifyRequest,
):
    """
    Verifica el primer código TOTP, activa 2FA
    y entrega los tokens definitivos de sesión.
    """

    ip_cliente = (
        request.client.host
        if request.client
        else "unknown"
    )

    verificar_rate_limit(
        key=f"enable_2fa:ip:{ip_cliente}",
        max_intentos=20,
        ventana_segundos=60,
        mensaje=(
            "Demasiados intentos para activar 2FA "
            "desde esta IP. Intenta de nuevo en un momento."
        ),
    )

    user = await obtener_usuario_desde_temp_token(
        data.temp_token,
        purpose="setup_2fa",
    )

    if user.is_2fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TWO_FACTOR_ALREADY_ENABLED",
                "detail": (
                    "La autenticación en dos pasos "
                    "ya está activada."
                ),
            },
        )

    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "TWO_FACTOR_SETUP_REQUIRED",
                "detail": (
                    "Primero debes generar la configuración "
                    "mediante POST /auth/setup."
                ),
            },
        )

    codigo_valido = auth_service.verify_totp_code(
        user.totp_secret,
        data.code,
    )

    if not codigo_valido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "TWO_FACTOR_CODE_INVALID",
                "detail": (
                    "El código de autenticación es inválido."
                ),
            },
        )

    user.is_2fa_enabled = True

    # Cambiar esta versión invalida inmediatamente
    # el temp_token usado para configurar 2FA.
    user.token_version += 1

    await user.save(
        update_fields=[
            "is_2fa_enabled",
            "token_version",
            "fecha_actualizacion",
        ]
    )

    # Los tokens definitivos se crean usando
    # la nueva versión del usuario.
    return await emitir_tokens_usuario(user)


# --- ROTACIÓN DE REFRESH TOKEN ---

@router.post("/refresh", response_model=Token)
async def refresh_access_token(data: RefreshTokenRequest):
    """
    Recibe un refresh_token válido, lo revoca (rotación) y devuelve
    un nuevo Access Token y un nuevo Refresh Token.
    """

    try:
        payload = decode_access_token(data.refresh_token)
        user_id = payload.get("sub")

        if not user_id or payload.get("type") != "refresh":
            raise ValueError()

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "REFRESH_TOKEN_INVALID", "detail": "Refresh token inválido o expirado."},
        )

    token_db = await TokenUsuario.get_or_none(
        token=data.refresh_token,
        tipo="REFRESH_TOKEN",
    )

    if not token_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SESSION_REVOKED", "detail": "Sesión revocada o inexistente."},
        )

    user = await User.get_or_none(id=user_id).prefetch_related(
        "estatus",
        "instancia",
    )

    if not user or not usuario_esta_activo(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "USER_INACTIVE", "detail": "Usuario inactivo o suspendido."},
        )

    payload_token_version = payload.get("token_version")

    if payload_token_version != user.token_version:
        await token_db.delete()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SESSION_REVOKED", "detail": "Sesión revocada. Inicia sesión nuevamente."},
        )

    await token_db.delete()
    return await emitir_tokens_usuario(user)


# --- CERRAR SESIÓN ---

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(data: RefreshTokenRequest):
    """
    Cierra sesión eliminando el refresh_token en la base de datos.
    """

    return await auth_service.cerrar_sesion(
        refresh_token=data.refresh_token,
    )


# --- RESTABLECER CONTRASEÑA CON TOKEN ENVIADO POR ADMIN ---

@router.post(
    "/restablecer-password",
    status_code=status.HTTP_200_OK,
)
async def restablecer_password(
    data: RestablecerPasswordRequest,
):
    """Restablece la contraseña usando el token enviado por correo."""
    return await auth_service.restablecer_password(
        token=data.token,
        password_nueva=data.password_nueva,
    )


# --- REDIRECCIÓN SEGURA HACIA MÓDULOS EXTERNOS ---

@router.post(
    "/redirect-code",
    response_model=RedirectCodeResponse,
    status_code=status.HTTP_200_OK,
)
async def crear_redirect_code(
    data: RedirectCodeRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Genera un código temporal de un solo uso para redirigir al usuario
    autenticado hacia un módulo externo permitido sin exponer tokens en la URL.
    """
    return await auth_service.generar_redirect_code(
        user=current_user,
        redirect_url=data.redirect_url,
    )


@router.post("/exchange-code", response_model=Token)
async def exchange_redirect_code(data: ExchangeCodeRequest):
    """
    Intercambia un código temporal de redirección por tokens de sesión.
    El código queda invalidado al primer uso.
    """
    user = await auth_service.consumir_redirect_code(data.code)
    return await emitir_tokens_usuario(user)
