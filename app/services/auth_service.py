import pyotp

from app.core.security import verify_password
from fastapi import HTTPException, status
from app.models.user import User

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
        return None

    if user.intentos_login >= MAX_INTENTOS_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario bloqueado por exceder el número máximo de intentos de inicio de sesión.",
        )

    if not verify_password(password, user.contrasena_hasheada):
        user.intentos_login += 1
        await user.save(update_fields=["intentos_login"])

        intentos_restantes = MAX_INTENTOS_LOGIN - user.intentos_login

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"CURP o contraseña incorrectos. Intentos restantes: {intentos_restantes}",
        )

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