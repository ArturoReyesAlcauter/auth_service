import pyotp

from fastapi import HTTPException, status
from tortoise.expressions import F
from datetime import datetime
from uuid import UUID

from app.core.security import verify_password, get_password_hash
from app.models.user import User, EstatusUsuario
from app.models.user import TokenUsuario


MAX_INTENTOS_LOGIN = 5

async def authenticate_user(curp: str, password: str):
    """
    Valida CURP y contraseña.

    - Si la contraseña es incorrecta, suma intentos_login.
    - Si llega a 5 intentos, bloquea el login.
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

    if user.intentos_login >= MAX_INTENTOS_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario bloqueado por exceder el número máximo de intentos de inicio de sesión.",
        )

    if not verify_password(password, user.contrasena_hasheada):
        # 2. MITIGACIÓN DE RACE CONDITION
        # Sumamos el intento directamente en la DB
        await User.filter(id=user.id).update(intentos_login=F("intentos_login") + 1)
        
        # Refrescamos el objeto local para tener el contador real
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

            # Asignamos el nuevo estatus en memoria
            user.estatus = estatus_bloqueado

            # Guardamos únicamente el campo estatus_id, ya que los intentos se guardaron antes con F()
            await user.save(update_fields=["estatus_id"])
            
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