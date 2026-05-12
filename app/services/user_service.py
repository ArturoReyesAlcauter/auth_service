from uuid import UUID

from fastapi import HTTPException, status
from tortoise.exceptions import IntegrityError

from app.core.security import get_password_hash
from app.models.user import (
    User,
    UsuarioRegistro,
    UsuarioModulo,
    UsuarioAccion,
)
from app.schemas.user import (
    UserCreate,
    UsuarioRegistroCreate,
    UsuarioModuloCreate,
    UsuarioAccionCreate,
)


async def create_user(user_in: UserCreate) -> User:
    if await User.exists(correo_electronico=user_in.correo_electronico):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo ya está registrado en el sistema.",
        )

    if await User.exists(curp=user_in.curp):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La CURP ya está registrada en el sistema.",
        )

    user_data = user_in.model_dump(exclude={"password"})

    user_data["contrasena_hasheada"] = get_password_hash(user_in.password)

    user = await User.create(**user_data)
    return user


async def get_users() -> list[User]:
    users = await User.all().prefetch_related("estatus", "instancia")
    return users


async def assign_user_registro(
    user_id: UUID,
    data: UsuarioRegistroCreate
) -> UsuarioRegistro:
    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    try:
        asignacion = await UsuarioRegistro.create(
            usuario_id=user_id,
            registro_id=data.registro_id,
        )

        await asignacion.fetch_related("registro")
        return asignacion

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este usuario ya tiene asignado ese registro.",
        )


async def assign_user_modulo(
    user_id: UUID,
    data: UsuarioModuloCreate
) -> UsuarioModulo:
    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    try:
        asignacion = await UsuarioModulo.create(
            usuario_id=user_id,
            modulo_id=data.modulo_id,
        )

        await asignacion.fetch_related("modulo")
        return asignacion

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este usuario ya tiene asignado ese módulo.",
        )


async def assign_user_accion(
    user_id: UUID,
    data: UsuarioAccionCreate
) -> UsuarioAccion:
    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    try:
        asignacion = await UsuarioAccion.create(
            usuario_id=user_id,
            accion_id=data.accion_id,
        )

        await asignacion.fetch_related("accion")
        return asignacion

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este usuario ya tiene asignada esa acción.",
        )


async def usuario_tiene_accion(user_id: UUID, accion_nombre: str) -> bool:
    return await UsuarioAccion.filter(
        usuario_id=user_id,
        accion__nombre=accion_nombre
    ).exists()


async def obtener_permisos_usuario(user_id: UUID) -> dict:
    registros_asignados = await UsuarioRegistro.filter(
        usuario_id=user_id
    ).prefetch_related("registro")

    modulos_asignados = await UsuarioModulo.filter(
        usuario_id=user_id
    ).prefetch_related("modulo", "modulo__registro_principal")

    acciones_asignadas = await UsuarioAccion.filter(
        usuario_id=user_id
    ).prefetch_related("accion", "accion__modulo")

    return {
        "registros": [item.registro for item in registros_asignados],
        "modulos": [item.modulo for item in modulos_asignados],
        "acciones": [item.accion for item in acciones_asignadas],
    }