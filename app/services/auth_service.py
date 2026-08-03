import pyotp

from secrets import token_urlsafe
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from tortoise.expressions import F

from app.core.security import verify_password, get_password_hash
from app.models.user import User, EstatusUsuario, TokenUsuario
from app.core.config import settings
from app.services import user_service
from app.services.notificacion_service import (
    enviar_correo_cambio_estatus_usuario,
    enviar_correo_recuperacion_password,
)


MAX_INTENTOS_LOGIN = 5

async def authenticate_user(curp: str, password: str):
    """
    Valida CURP y contraseña.

    - Si la contraseña es incorrecta, suma intentos_login.
    - Si llega a 5 intentos, cambia el estatus a "Intentos en exceso sesión".
    - Cuando bloquea por intentos, notifica al usuario por correo.
    - Si la contraseña es correcta, reinicia intentos_login a 0.
    """

    user = await User.get_or_none(curp=curp).prefetch_related(
        "estatus",
        "instancia",
    )

    if not user:
        # 1. MITIGACIÓN DE TIMING ATTACK
        # Generamos un hash con la contraseña recibida aunque el usuario no exista.
        get_password_hash(password)
        return None

    # Si el usuario existe pero no tiene contraseña hasheada,
    # es porque aún no activó su cuenta.
    if not user.contrasena_hasheada:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta aún no tiene contraseña configurada. Revisa el correo de activación o solicita un nuevo enlace.",
        )

    if user.intentos_login >= MAX_INTENTOS_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario bloqueado por exceder el número máximo de intentos de inicio de sesión.",
        )

    if not verify_password(password, user.contrasena_hasheada):
        # 2. MITIGACIÓN DE RACE CONDITION
        # Sumamos el intento directamente en la DB.
        await User.filter(id=user.id).update(
            intentos_login=F("intentos_login") + 1
        )

        # Refrescamos el objeto local para tener el contador real.
        await user.refresh_from_db(fields=["intentos_login"])

        # 3. VERIFICACIÓN Y CAMBIO DE ESTATUS POR BLOQUEO
        if user.intentos_login >= MAX_INTENTOS_LOGIN:
            estatus_bloqueado = await EstatusUsuario.get_or_none(
                nombre__iexact="Intentos en exceso sesión"
            )

            if not estatus_bloqueado:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No existe el estatus 'Intentos en exceso sesión' en cat_estatus_usuarios.",
                )

            # Guardamos el estatus anterior antes de cambiarlo.
            estatus_anterior = user.estatus

            # Asignamos el nuevo estatus en memoria.
            user.estatus = estatus_bloqueado

            # Guardamos únicamente el campo estatus_id.
            # Los intentos_login ya se actualizaron antes con F().
            await user.save(update_fields=["estatus_id"])

            # Invalidamos tokens activos del usuario para cerrar sesiones previas.
            await User.filter(id=user.id).update(
                token_version=F("token_version") + 1
            )

            # Notificamos por correo el bloqueo de cuenta.
            await enviar_correo_cambio_estatus_usuario(
                user=user,
                estatus_anterior=estatus_anterior,
                estatus_nuevo=estatus_bloqueado,
                motivo="Su cuenta fue bloqueada por exceder el número máximo de intentos de inicio de sesión.",
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario bloqueado por exceder el número máximo de intentos de inicio de sesión.",
            )

        # 4. CALCULAR INTENTOS RESTANTES SI AÚN NO SE BLOQUEA
        intentos_restantes = MAX_INTENTOS_LOGIN - user.intentos_login
        intentos_restantes = max(0, intentos_restantes)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"CURP o contraseña incorrectos. Intentos restantes: {intentos_restantes}",
        )

    # 5. SI LA CONTRASEÑA ES CORRECTA Y HABÍA INTENTOS FALLIDOS, RESETEAMOS A 0
    if user.intentos_login != 0:
        user.intentos_login = 0
        await user.save(update_fields=["intentos_login"])

    return user


def generate_totp_secret() -> str:
    """
    Genera el secret que se registra en Google Authenticator.
    """
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, account_name: str) -> str:
    """
    Genera la URI otpauth:// para Google Authenticator.

    Esta URI se mete dentro del QR.
    Google Authenticator la lee al escanearlo.
    """
    totp = pyotp.TOTP(secret)

    return totp.provisioning_uri(
        name=account_name,
        issuer_name=settings.TOTP_ISSUER,
    )


def verify_totp_code(secret: str | None, code: str, valid_window: int = 2) -> bool:
    """
    Verifica el código de 6 dígitos generado por Google Authenticator.

    valid_window=2 permite aceptar una tolerancia aproximada de +/- 60 segundos,
    porque Google Authenticator normalmente cambia el código cada 30 segundos.
    """
    if not secret:
        return False

    if not code:
        return False

    clean_code = str(code).strip().replace(" ", "")

    if not clean_code.isdigit():
        return False

    if len(clean_code) != 6:
        return False

    totp = pyotp.TOTP(secret)

    return totp.verify(
        clean_code,
        valid_window=valid_window,
    )

# Alias opcional por si en otro archivo ya estabas usando verify_totp
def verify_totp(secret: str | None, code: str) -> bool:
    return verify_totp_code(secret, code)

async def store_refresh_token(user_id: UUID, token: str, expire_date: datetime):
    """Guarda el refresh token en la base de datos para control de sesiones."""
    await TokenUsuario.create(
        usuario_id=user_id,
        token=token,
        tipo="REFRESH_TOKEN",
        fecha_expiracion=expire_date
    )

async def revoke_refresh_token(token: str):
    """Invalida un refresh token específico (ej. para Logout)."""
    await TokenUsuario.filter(token=token, tipo="REFRESH_TOKEN").delete()
    




def obtener_redirect_urls_permitidas() -> set[str]:
    return {
        url.strip().rstrip("/")
        for url in settings.ALLOWED_REDIRECT_URLS.split(",")
        if url.strip()
    }


def validar_redirect_url_permitida(redirect_url: str) -> str:
    clean_url = redirect_url.strip().rstrip("/")
    urls_permitidas = obtener_redirect_urls_permitidas()

    if clean_url not in urls_permitidas:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "REDIRECT_URL_NOT_ALLOWED",
                "detail": "La URL de redirección no está permitida.",
            },
        )

    return clean_url


async def generar_redirect_code(user: User, redirect_url: str) -> dict:
    """
    Genera un código temporal de un solo uso para transferir sesión
    desde Login Universal hacia un módulo externo autorizado.
    """
    validar_redirect_url_permitida(redirect_url)

    await TokenUsuario.filter(
        usuario_id=user.id,
        tipo="REDIRECT_CODE",
    ).delete()

    code = token_urlsafe(32)
    expires_in = settings.REDIRECT_CODE_EXPIRE_SECONDS
    fecha_expiracion = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    await TokenUsuario.create(
        usuario_id=user.id,
        token=code,
        tipo="REDIRECT_CODE",
        fecha_expiracion=fecha_expiracion,
    )

    return {
        "code": code,
        "expires_in": expires_in,
    }


async def consumir_redirect_code(code: str) -> User:
    """
    Consume un código temporal de redirección.

    El código se elimina al primer uso, aunque después falle una validación,
    para evitar reutilización.
    """
    token_db = await TokenUsuario.get_or_none(
        token=code,
        tipo="REDIRECT_CODE",
    ).prefetch_related("usuario")

    if not token_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "REDIRECT_CODE_INVALID",
                "detail": "Código temporal inválido o ya utilizado.",
            },
        )

    user = token_db.usuario
    ahora = datetime.now(timezone.utc)

    # Invalidar el código al intercambiarlo, incluso si ya expiró.
    await token_db.delete()

    if token_db.fecha_expiracion and token_db.fecha_expiracion < ahora:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "REDIRECT_CODE_EXPIRED",
                "detail": "El código temporal expiró.",
            },
        )

    await user.fetch_related("estatus", "instancia")

    if not user.estatus or user.estatus.nombre.lower() != "activo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "USER_INACTIVE",
                "detail": "Usuario inactivo o suspendido.",
            },
        )

    return user

async def generar_token_recuperacion_password(user: User) -> str:
    """
    Genera un token temporal para recuperar/restablecer contraseña.

    Elimina tokens anteriores del mismo tipo para que solo quede activo
    el enlace más reciente.
    """

    await TokenUsuario.filter(
        usuario_id=user.id,
        tipo="RECUPERACION_CONTRASENA",
    ).delete()

    token = token_urlsafe(48)

    fecha_expiracion = datetime.now(timezone.utc) + timedelta(hours=24)

    await TokenUsuario.create(
        usuario_id=user.id,
        token=token,
        tipo="RECUPERACION_CONTRASENA",
        fecha_expiracion=fecha_expiracion,
    )

    return token


async def enviar_recuperacion_password_por_admin(
    user_id: UUID,
    current_user_id: UUID,
):
    """
    Envía un correo de recuperación de contraseña solicitado por un administrador.

    Reglas:
    - SUPER_ADMIN / Dios puede enviar recuperación a cualquier usuario.
    - Un administrador normal solo puede enviar recuperación a usuarios que
      pertenezcan a sus grupos administrables.
    - El usuario debe existir.
    - El usuario ya debe tener una contraseña configurada.
    """

    user = await User.get_or_none(id=user_id).prefetch_related(
        "estatus",
        "instancia",
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    await user_service.validar_usuario_objetivo_administrable(
        current_user_id=current_user_id,
        target_user_id=user_id,
    )

    if not user.contrasena_hasheada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario aún no tiene contraseña configurada. Debe usar el flujo de activación de cuenta.",
        )

    token = await generar_token_recuperacion_password(user)

    await enviar_correo_recuperacion_password(
        user=user,
        token=token,
    )

    return {
        "message": "Correo de recuperación de contraseña enviado correctamente.",
        "user_id": str(user.id),
        "correo_electronico": user.correo_electronico,
    }




async def restablecer_password(token: str, password_nueva: str):
    """
    Restablece la contraseña usando un token de recuperación.
    """

    token_db = await TokenUsuario.get_or_none(
        token=token,
        tipo="RECUPERACION_CONTRASENA",
    ).prefetch_related("usuario")

    if not token_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o ya utilizado.",
        )

    ahora = datetime.now(timezone.utc)

    if token_db.fecha_expiracion and token_db.fecha_expiracion < ahora:
        await token_db.delete()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace para restablecer contraseña ha expirado.",
        )

    user = token_db.usuario

    if not user.contrasena_hasheada:
        await token_db.delete()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta aún no tiene contraseña configurada. Usa el enlace de activación.",
        )

    user.contrasena_hasheada = get_password_hash(password_nueva)
    user.intentos_login = 0
    user.token_version += 1

    await user.save(
        update_fields=[
            "contrasena_hasheada",
            "intentos_login",
            "token_version",
            "fecha_actualizacion",
        ]
    )

    await token_db.delete()

    return {
        "message": "Contraseña restablecida correctamente. Ya puedes iniciar sesión.",
    }


async def cerrar_sesion(refresh_token: str):
    """
    Cierra sesión revocando el refresh token e invalidando
    los access tokens activos del usuario.

    Lo usa:
    - POST /auth/logout
    - cierre manual de sesión
    - cierre por inactividad desde frontend
    """

    token_db = await TokenUsuario.get_or_none(
        token=refresh_token,
        tipo="REFRESH_TOKEN",
    ).prefetch_related("usuario")

    # Logout debe ser idempotente:
    # si el token ya no existe, igual respondemos OK para que el frontend limpie sesión.
    if not token_db:
        return {
            "message": "Sesión cerrada correctamente.",
        }

    user = token_db.usuario

    # 1. Eliminamos el refresh token actual.
    await token_db.delete()

    # 2. Incrementamos token_version para invalidar access tokens activos.
    await User.filter(id=user.id).update(
        token_version=F("token_version") + 1
    )

    return {
        "message": "Sesión cerrada correctamente.",
    }