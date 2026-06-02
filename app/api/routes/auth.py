from typing import Annotated

import io
import qrcode

from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.services.rate_limit_service import verificar_rate_limit
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.schemas.token import (
    Token,
    RefreshTokenRequest,
    RecuperarPasswordRequest,
    RestablecerPasswordRequest,
)
from app.services import auth_service
from app.services.session_service import validar_ultima_sesion_o_revocar
from app.core.security import create_access_token, create_refresh_token, decode_access_token
from app.models.user import User, UsuarioAccion
from app.models.user import TokenUsuario
from app.core.config import settings


router = APIRouter(tags=["Autenticación"])


# --- ESQUEMAS DE APOYO ---

class Verify2FA(BaseModel):
    user_id: str
    code: str


class Setup2FA(BaseModel):
    user_id: str


# --- FUNCIONES DE APOYO ---

def usuario_esta_activo(user: User) -> bool:
    """
    En el modelo anterior usabas user.is_active.
    En el modelo nuevo usamos la relación con cat_estatus_usuarios.
    """
    if not user.estatus:
        return False

    return user.estatus.nombre.lower() == "activo"

# --- HELPER PARA OBTENER LOS CLAIMS ---
async def generar_payload_usuario(user: User) -> dict:
    """Extrae las acciones del usuario y prepara el payload del JWT."""
    acciones_db = await UsuarioAccion.filter(usuario_id=user.id).prefetch_related("accion")
    lista_acciones = [ua.accion.nombre for ua in acciones_db]
    
    return {
        "sub": str(user.id),
        "instancia_id": user.instancia_id,
        "entidad_federativa_id": user.entidad_federativa_id,
        "acciones": lista_acciones,
        "token_version": user.token_version
    }


# --- 1. LOGIN PASO 1: Validar credenciales ---

@router.post("/login")
async def login_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    """
    Paso 1: Valida CURP y contraseña.

    No entrega JWT todavía.
    Entrega un ID temporal para el segundo paso.
    """

    ip_cliente = request.client.host if request.client else "unknown"
   

    verificar_rate_limit(
        key=f"login:ip:{ip_cliente}",
        max_intentos=20,
        ventana_segundos=60,
        mensaje="Demasiados intentos de inicio de sesión desde esta IP. Intenta de nuevo en un momento.",
    )


    user = await auth_service.authenticate_user(
        curp=form_data.username.upper().strip(),
        password=form_data.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CURP o contraseña incorrectos",
        )

    if not usuario_esta_activo(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo",
        )

    await validar_ultima_sesion_o_revocar(user)

    if user.is_2fa_enabled:
        return {
            "status": "pending_2fa",
            "temp_user_id": str(user.id),
            "message": "Ingresa tu código de Google Authenticator",
        }

    return {
        "status": "pending_setup",
        "temp_user_id": str(user.id),
        "message": "Es obligatorio configurar la seguridad de 2 pasos.",
    }

# --- 2. LOGIN PASO 2: Validar el código 2FA ---

@router.post("/login/2fa", response_model=Token)
async def login_verify_2fa(
    request: Request,
    data: Verify2FA,
):
    """
    Paso 2: Verifica el código TOTP y entrega el JWT final.
    """

    ip_cliente = request.client.host if request.client else "unknown"

    verificar_rate_limit(
        key=f"login_2fa:ip:{ip_cliente}",
        max_intentos=20,
        ventana_segundos=60,
        mensaje="Demasiados intentos de verificación 2FA desde esta IP.",
    )

    user = await User.get_or_none(id=data.user_id).prefetch_related(
        "estatus",
        "instancia",
    )

    if not user or not usuario_esta_activo(user) or not user.is_2fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Petición inválida o 2FA no habilitado",
        )

    is_valid = auth_service.verify_totp_code(user.totp_secret, data.code)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código de verificación incorrecto",
        )

    payload = await generar_payload_usuario(user)
    access_token = create_access_token(data=payload)

    refresh_token_str, expire_dt = create_refresh_token(
        {"sub": str(user.id)},
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


# --- RUTAS DE CONFIGURACIÓN ---

@router.post("/setup")
async def setup_2fa(
    request: Request,
    data: Setup2FA,
):
    ip_cliente = request.client.host if request.client else "unknown"

    verificar_rate_limit(
        key=f"setup_2fa:ip:{ip_cliente}",
        max_intentos=10,
        ventana_segundos=60,
        mensaje="Demasiadas solicitudes para configurar 2FA desde esta IP.",
    )

    user = await User.get_or_none(id=data.user_id).prefetch_related(
        "estatus",
        "instancia",
    )

    if not user or not usuario_esta_activo(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inválido.",
        )

    if user.is_2fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA ya está activado.",
        )

    secret = auth_service.generate_totp_secret()
    user.totp_secret = secret
    await user.save()

    uri = auth_service.get_provisioning_uri(
        secret=secret,
        account_name=user.correo_electronico,
    )

    qr = qrcode.make(uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/png",
    )


@router.post("/enable", response_model=Token)
async def enable_2fa(
    request: Request,
    data: Verify2FA,
):
    """
    Verifica el primer código para activar el 2FA definitivamente
    y entrega el primer token de acceso.
    """

    ip_cliente = request.client.host if request.client else "unknown"

    verificar_rate_limit(
        key=f"enable_2fa:ip:{ip_cliente}",
        max_intentos=20,
        ventana_segundos=60,
        mensaje="Demasiados intentos para activar 2FA desde esta IP. Intenta de nuevo en un momento.",
    )

    user = await User.get_or_none(id=data.user_id).prefetch_related(
        "estatus",
        "instancia",
    )

    if not user or not usuario_esta_activo(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inválido.",
        )

    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Primero debes generar el QR (setup).",
        )

    is_valid = auth_service.verify_totp_code(user.totp_secret, data.code)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido. Intenta de nuevo.",
        )

    user.is_2fa_enabled = True
    await user.save()

    payload = await generar_payload_usuario(user)
    access_token = create_access_token(data=payload)

    refresh_token_str, expire_dt = create_refresh_token(
        {"sub": str(user.id)},
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

# --- ROTACIÓN DE REFRESH TOKEN ---

@router.post("/refresh", response_model=Token)
async def refresh_access_token(data: RefreshTokenRequest):
    """
    Recibe un refresh_token válido, lo revoca (rotación) y devuelve 
    un nuevo Access Token y un nuevo Refresh Token.
    """
    # 1. Validar criptográficamente el token
    try:
        payload = decode_access_token(data.refresh_token)
        user_id = payload.get("sub")
        if not user_id or payload.get("type") != "refresh":
            raise ValueError()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado.",
        )

    # 2. Validar que exista en la base de datos (no haya sido revocado / logged out)
    token_db = await TokenUsuario.get_or_none(token=data.refresh_token, tipo="REFRESH_TOKEN")
    if not token_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión revocada o inexistente.",
        )

    # 3. Validar estado del usuario
    user = await User.get_or_none(id=user_id).prefetch_related("estatus", "instancia")
    if not user or not usuario_esta_activo(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo o suspendido.",
        )

    # 4. Rotación del Token: Eliminar el viejo para evitar re-uso
    await token_db.delete()

    # 5. Emitir nuevos tokens
    new_payload = await generar_payload_usuario(user)
    new_access_token = create_access_token(data=new_payload)
    
    new_refresh_str, expire_dt = create_refresh_token({"sub": str(user.id)}, expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await auth_service.store_refresh_token(user.id, new_refresh_str, expire_dt)

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_str,
        token_type="bearer"
    )

# --- CERRAR SESIÓN ---

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(data: RefreshTokenRequest):
    """
    Invalida el refresh_token en la base de datos, cerrando la sesión de ese dispositivo.
    """
    await auth_service.revoke_refresh_token(data.refresh_token)
    return {"message": "Sesión cerrada correctamente."}




@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(data: RefreshTokenRequest):
    """
    Invalida el refresh_token en la base de datos, cerrando la sesión de ese dispositivo.
    """
    await auth_service.revoke_refresh_token(data.refresh_token)
    return {"message": "Sesión cerrada correctamente."}


# --- RECUPERACIÓN DE CONTRASEÑA ---

@router.post(
    "/recuperar-password",
    status_code=status.HTTP_200_OK,
)
async def recuperar_password(
    data: RecuperarPasswordRequest,
):
    """
    Solicita un correo para restablecer contraseña.

    No requiere JWT porque el usuario no puede iniciar sesión
    si olvidó su contraseña.

    Por seguridad, aunque el correo no exista, se responde el mismo mensaje.
    """
    return await auth_service.solicitar_recuperacion_password(
        correo_electronico=data.correo_electronico,
    )


@router.post(
    "/restablecer-password",
    status_code=status.HTTP_200_OK,
)
async def restablecer_password(
    data: RestablecerPasswordRequest,
):
    """
    Restablece la contraseña usando el token enviado por correo.
    """
    return await auth_service.restablecer_password(
        token=data.token,
        password_nueva=data.password_nueva,
    )