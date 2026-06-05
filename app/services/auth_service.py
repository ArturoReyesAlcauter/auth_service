import pyotp

from pathlib import Path
from secrets import token_urlsafe
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from tortoise.expressions import F

from app.core.config import settings
from app.core.security import verify_password, get_password_hash
from app.models.user import User, EstatusUsuario, TokenUsuario
from app.services.email_service import enviar_correo_html
from app.services.notificacion_service import enviar_correo_cambio_estatus_usuario


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
        issuer_name="Login PorTusDerechos",
    )


def verify_totp_code(secret: str | None, code: str) -> bool:
    """
    Verifica el código de 6 dígitos generado por Google Authenticator.

    valid_window=1 permite aceptar:
    - el código del bloque anterior
    - el código actual
    - el código del siguiente bloque

    Como TOTP normalmente cambia cada 30 segundos, esto da tolerancia
    aproximada de +/- 30 segundos.
    """
    if not secret:
        return False

    if not code:
        return False

    clean_code = code.strip().replace(" ", "")

    if not clean_code.isdigit():
        return False

    totp = pyotp.TOTP(secret)

    return totp.verify(
        clean_code,
        valid_window=1,
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
    
def render_template_email(nombre_template: str, contexto: dict) -> str:
    """
    Carga una plantilla HTML desde app/templates y reemplaza variables simples.

    Ejemplo:
    {{ nombre_completo }}
    {{ link_recuperacion }}
    """

    ruta_template = (
        Path(__file__).resolve().parent.parent
        / "templates"
        / nombre_template
    )

    html = ruta_template.read_text(encoding="utf-8")

    for clave, valor in contexto.items():
        html = html.replace(f"{{{{ {clave} }}}}", str(valor))

    return html


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


async def solicitar_recuperacion_password(correo_electronico: str):
    """
    Solicita recuperación de contraseña.

    Por seguridad, siempre responde el mismo mensaje aunque el correo no exista.
    Así evitamos revelar qué correos están registrados.
    """

    respuesta_generica = {
        "message": "Si la cuenta existe, se enviará un correo con instrucciones para restablecer la contraseña.",
    }

    user = await User.get_or_none(
        correo_electronico=correo_electronico,
    )

    if not user:
        return respuesta_generica

    if not user.contrasena_hasheada:
        return respuesta_generica

    token = await generar_token_recuperacion_password(user)

    link_recuperacion = (
        f"{settings.FRONTEND_URL}/restablecer-password?token={token}"
    )

    nombre_completo = " ".join(
        parte
        for parte in [
            user.nombre,
            user.primer_apellido,
            user.segundo_apellido,
        ]
        if parte
    )

    html = render_template_email(
        "email_recuperacion_password.html",
        {
            "nombre_completo": nombre_completo,
            "link_recuperacion": link_recuperacion,
        },
    )

    enviar_correo_html(
        destinatario=user.correo_electronico,
        asunto="Restablecimiento de contraseña",
        html=html,
    )

    return respuesta_generica




async def enviar_recuperacion_password_por_admin(user_id: UUID):
    """
    Envía un correo de recuperación de contraseña solicitado por un administrador.

    Este flujo se usa cuando el usuario no puede solicitar libremente la recuperación.
    El administrador valida la solicitud y dispara el envío del enlace.

    Reglas:
    - El usuario debe existir.
    - El usuario ya debe tener una contraseña configurada.
    - Se elimina cualquier token anterior de recuperación.
    - Se genera un nuevo token con vigencia de 24 horas.
    - Se envía correo con el enlace para restablecer contraseña.
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

    if not user.contrasena_hasheada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario aún no tiene contraseña configurada. Debe usar el flujo de activación de cuenta.",
        )

    token = await generar_token_recuperacion_password(user)

    link_recuperacion = (
        f"{settings.FRONTEND_URL}/restablecer-password?token={token}"
    )

    nombre_completo = " ".join(
        parte
        for parte in [
            user.nombre,
            user.primer_apellido,
            user.segundo_apellido,
        ]
        if parte
    )

    html = render_template_email(
        "email_recuperacion_password.html",
        {
            "nombre_completo": nombre_completo,
            "link_recuperacion": link_recuperacion,
        },
    )

    enviar_correo_html(
        destinatario=user.correo_electronico,
        asunto="Restablecimiento de contraseña",
        html=html,
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