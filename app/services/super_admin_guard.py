from uuid import UUID

from fastapi import HTTPException, status

from app.models.user import UsuarioAccion


SUPER_ADMIN_ACTION = "SUPER_ADMIN"
ACTIVE_STATUS_NAME = "activo"


def _forbidden(code: str, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": code,
            "detail": detail,
        },
    )


def _conflict(code: str, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": code,
            "detail": detail,
        },
    )


async def usuario_es_super_admin(user_id: UUID) -> bool:
    """Indica si el usuario tiene asignada la acción global SUPER_ADMIN."""

    return await UsuarioAccion.filter(
        usuario_id=user_id,
        accion__nombre=SUPER_ADMIN_ACTION,
    ).exists()


async def usuario_es_super_admin_activo(user_id: UUID) -> bool:
    """Indica si el usuario es SUPER_ADMIN y además mantiene estatus Activo."""

    return await UsuarioAccion.filter(
        usuario_id=user_id,
        accion__nombre=SUPER_ADMIN_ACTION,
        usuario__estatus__nombre__iexact=ACTIVE_STATUS_NAME,
    ).exists()


async def contar_super_admin_activos() -> int:
    """Cuenta identidades activas con SUPER_ADMIN sin asumir unicidad del catálogo."""

    ids = await UsuarioAccion.filter(
        accion__nombre=SUPER_ADMIN_ACTION,
        usuario__estatus__nombre__iexact=ACTIVE_STATUS_NAME,
    ).values_list(
        "usuario_id",
        flat=True,
    )

    return len(set(ids))


async def validar_retiro_super_admin(
    target_user_id: UUID,
    current_user_id: UUID,
) -> None:
    """
    Protege el retiro explícito o en cascada de SUPER_ADMIN.

    Reglas:
    - Solo otro SUPER_ADMIN puede retirar SUPER_ADMIN.
    - Un SUPER_ADMIN no puede retirarse a sí mismo esa acción.
    - No se puede retirar al último SUPER_ADMIN activo.
    """

    if not await usuario_es_super_admin(current_user_id):
        raise _forbidden(
            "SUPER_ADMIN_REQUIRED",
            "Solo un SUPER_ADMIN puede retirar permisos SUPER_ADMIN.",
        )

    if target_user_id == current_user_id:
        raise _forbidden(
            "SELF_SUPER_ADMIN_REMOVAL_FORBIDDEN",
            "No puedes retirar tu propio permiso SUPER_ADMIN.",
        )

    if not await usuario_es_super_admin_activo(target_user_id):
        return

    if await contar_super_admin_activos() <= 1:
        raise _conflict(
            "LAST_ACTIVE_SUPER_ADMIN_REQUIRED",
            "La operación dejaría al sistema sin un SUPER_ADMIN activo.",
        )


async def validar_cambio_estatus_protegido(
    target_user_id: UUID,
    current_user_id: UUID,
    nuevo_estatus_nombre: str | None,
) -> None:
    """
    Protege la desactivación administrativa y al último SUPER_ADMIN activo.

    Cualquier cambio del propio usuario autenticado a un estatus distinto de
    Activo queda bloqueado para evitar auto-desactivaciones administrativas.
    """

    nuevo_es_activo = (
        nuevo_estatus_nombre is not None
        and nuevo_estatus_nombre.strip().lower() == ACTIVE_STATUS_NAME
    )

    if nuevo_es_activo:
        return

    if target_user_id == current_user_id:
        raise _forbidden(
            "SELF_DEACTIVATION_FORBIDDEN",
            "No puedes cambiar tu propio estatus a un estado no activo.",
        )

    if not await usuario_es_super_admin_activo(target_user_id):
        return

    if await contar_super_admin_activos() <= 1:
        raise _conflict(
            "LAST_ACTIVE_SUPER_ADMIN_REQUIRED",
            "La operación dejaría al sistema sin un SUPER_ADMIN activo.",
        )


async def validar_revocacion_total_por_inactividad(user_id: UUID) -> None:
    """Evita que la política de inactividad elimine al último SUPER_ADMIN activo."""

    if not await usuario_es_super_admin_activo(user_id):
        return

    if await contar_super_admin_activos() <= 1:
        raise _conflict(
            "LAST_ACTIVE_SUPER_ADMIN_REQUIRED",
            (
                "No se revocaron los permisos por inactividad porque esta cuenta "
                "es el último SUPER_ADMIN activo. Requiere revisión administrativa."
            ),
        )
