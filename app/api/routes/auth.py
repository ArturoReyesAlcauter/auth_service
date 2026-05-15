from typing import Annotated

import io
import qrcode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.schemas.token import Token
from app.services import auth_service
from app.core.security import create_access_token
from app.models.user import User, UsuarioAccion


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
        "instancia_id": user.instancia_id, # Este será el entidad_federativa_id en el otro backend
        "acciones": lista_acciones
    }


# --- 1. LOGIN PASO 1: Validar credenciales ---

@router.post("/login")
async def login_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    """
    Paso 1: Valida CURP y contraseña.

    No entrega JWT todavía.
    Entrega un ID temporal para el segundo paso.
    """
    user = await auth_service.authenticate_user(
        curp=form_data.username,
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

    # Identificamos si necesita configurar o solo validar
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
async def login_verify_2fa(data: Verify2FA):
    """
    Paso 2: Verifica el código TOTP y entrega el JWT final.
    """
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

    return Token(
        access_token=access_token,
        token_type="bearer",
    )


# --- RUTAS DE CONFIGURACIÓN ---

@router.post("/setup")
async def setup_2fa(data: Setup2FA):
    """
    Genera el secreto y devuelve un código QR.

    Igual que tu proyecto anterior:
    - No devuelve JSON.
    - Devuelve directamente image/png.
    - Swagger muestra el QR como imagen.
    """
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

    # Generar secreto
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
async def enable_2fa(data: Verify2FA):
    """
    Verifica el primer código para activar el 2FA definitivamente
    y entrega el primer token de acceso.
    """
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

    # Activamos el 2FA oficialmente
    user.is_2fa_enabled = True
    await user.save()

    # Entregamos token para que el usuario no tenga que loguearse de nuevo tras activar
    payload = await generar_payload_usuario(user)
    access_token = create_access_token(data=payload)

    return Token(
        access_token=access_token,
        token_type="bearer",
    )