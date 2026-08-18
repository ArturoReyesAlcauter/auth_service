from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from tortoise.expressions import F
from app.models.user import (
    User,
    UltimaSesion,
    UsuarioAccion,
    UsuarioModulo,
    UsuarioGrupo,
)


DIAS_MAXIMOS_INACTIVIDAD = 90


async def resetear_ultima_sesion(usuario: User):
    """
    Registra la actividad más reciente del usuario.

    Si el usuario todavía no tiene registro en ultima_sesion,
    se crea.

    Si ya existe, se actualiza la fecha de última sesión.
    """

    ahora = datetime.now(timezone.utc)

    ultima_sesion, _ = await UltimaSesion.get_or_create(
        usuario=usuario,
        defaults={
            "fecha_inicio_sesion": ahora,
        },
    )

    ultima_sesion.fecha_inicio_sesion = ahora

    await ultima_sesion.save(
        update_fields=[
            "fecha_inicio_sesion",
            "fecha_actualizacion",
        ]
    )

    return ultima_sesion


async def invalidar_sesiones_usuario(
    usuario: User,
) -> User:
    """
    Invalida todos los JWT activos del usuario incrementando
    token_version de forma atómica en la base de datos.

    Los JWT existentes contienen la versión anterior y dejan
    de ser válidos inmediatamente.

    Después de actualizar la base de datos, refrescamos el
    objeto recibido para mantener sincronizado token_version.
    """

    await User.filter(
        id=usuario.id
    ).update(
        token_version=F("token_version") + 1
    )

    await usuario.refresh_from_db(
        fields=["token_version"]
    )

    return usuario


async def revocar_accesos_usuario(usuario: User):
    """
    Elimina todos los permisos asignados directamente al usuario.

    Se eliminan:

    1. Acciones
    2. Módulos
    3. Grupos

    No elimina al usuario ni modifica su estatus.
    """

    await UsuarioAccion.filter(
        usuario_id=usuario.id
    ).delete()

    await UsuarioModulo.filter(
        usuario_id=usuario.id
    ).delete()

    await UsuarioGrupo.filter(
        usuario_id=usuario.id
    ).delete()


async def validar_ultima_sesion_o_revocar(usuario: User):
    """
    Verifica si el usuario lleva más de 90 días sin actividad.

    Comportamiento:

    - Primera sesión:
        Se crea el registro y se permite el acceso.

    - Menos de 90 días:
        Se actualiza la fecha de última sesión y se permite el acceso.

    - Más de 90 días:
        Se eliminan sus permisos y se rechaza el acceso.

    Importante:
    - No cambia el estatus del usuario.
    - No actualiza la fecha cuando la cuenta ya superó los 90 días.
    """

    ahora = datetime.now(timezone.utc)

    ultima_sesion, creada = await UltimaSesion.get_or_create(
        usuario=usuario,
        defaults={
            "fecha_inicio_sesion": ahora,
        },
    )

    # Primera sesión registrada.
    if creada:
        return ultima_sesion

    if ultima_sesion.fecha_inicio_sesion:

        fecha_limite = (
            ultima_sesion.fecha_inicio_sesion
            + timedelta(days=DIAS_MAXIMOS_INACTIVIDAD)
        )

        if ahora > fecha_limite:

            await revocar_accesos_usuario(usuario)

            # También invalidamos cualquier JWT que pudiera
            # seguir activo.
            await invalidar_sesiones_usuario(usuario)

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Usuario sin acceso por inactividad mayor a 3 meses. "
                    "Contacte a un administrador para reactivar sus permisos."
                ),
            )

    # El usuario sigue activo.
    ultima_sesion.fecha_inicio_sesion = ahora

    await ultima_sesion.save(
        update_fields=[
            "fecha_inicio_sesion",
            "fecha_actualizacion",
        ]
    )

    return ultima_sesion