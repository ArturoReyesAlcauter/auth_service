from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status

from app.models.user import (
    UltimaSesion,
    User,
    UsuarioAccion,
    UsuarioModulo,
    UsuarioRegistro,
)


DIAS_MAXIMOS_INACTIVIDAD = 90


# Servicio para manejar la sesión del usuario.
# Si el usuario no tiene registro en ultima_sesion, lo crea.
# Si el usuario ya tiene registro, solo actualiza la fecha.
async def resetear_ultima_sesion(usuario: User):
    ahora = datetime.now(timezone.utc)

    ultima_sesion, _ = await UltimaSesion.get_or_create(
        usuario=usuario,
        defaults={
            "fecha_inicio_sesion": ahora,
        },
    )

    ultima_sesion.fecha_inicio_sesion = ahora
    await ultima_sesion.save(update_fields=["fecha_inicio_sesion", "fecha_actualizacion"])

    return ultima_sesion


async def revocar_accesos_usuario(usuario: User):
    """
    Elimina los accesos del usuario sin cambiar su estatus.

    Orden:
    1. acciones
    2. módulos
    3. registros/grupos
    """

    await UsuarioAccion.filter(usuario_id=usuario.id).delete()
    await UsuarioModulo.filter(usuario_id=usuario.id).delete()
    await UsuarioRegistro.filter(usuario_id=usuario.id).delete()


async def validar_ultima_sesion_o_revocar(usuario: User):
    """
    Valida si el usuario superó 90 días desde su última sesión.

    Si supera 90 días:
    - elimina acciones, módulos y registros/grupos
    - no cambia estatus
    - no actualiza la fecha
    - niega el acceso

    Si no supera 90 días:
    - actualiza fecha_inicio_sesion
    - permite continuar
    """

    ahora = datetime.now(timezone.utc)

    ultima_sesion, creada = await UltimaSesion.get_or_create(
        usuario=usuario,
        defaults={
            "fecha_inicio_sesion": ahora,
        },
    )

    # Si apenas se creó el registro, es su primera sesión registrada.
    # Permitimos el acceso.
    if creada:
        return ultima_sesion

    if ultima_sesion.fecha_inicio_sesion:
        fecha_limite = ultima_sesion.fecha_inicio_sesion + timedelta(
            days=DIAS_MAXIMOS_INACTIVIDAD
        )

        if ahora > fecha_limite:
            await revocar_accesos_usuario(usuario)

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario sin acceso por inactividad mayor a 3 meses. Contacte a un administrador para reactivar sus permisos.",
            )

    ultima_sesion.fecha_inicio_sesion = ahora
    await ultima_sesion.save(update_fields=["fecha_inicio_sesion", "fecha_actualizacion"])

    return ultima_sesion