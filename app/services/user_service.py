from uuid import UUID

from fastapi import HTTPException, status
from tortoise.exceptions import IntegrityError

from app.core.security import get_password_hash
from app.models.user import (
    User,
    RegistroPrincipal,
    Modulo,
    Accion,
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
    data: UsuarioRegistroCreate,
) -> UsuarioRegistro:
    """
    Asigna un grupo a un usuario.

    Internamente:
    grupo = RegistroPrincipal
    usuario_grupo = UsuarioRegistro
    """

    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    grupo = await RegistroPrincipal.get_or_none(id=data.registro_id)

    if not grupo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grupo no encontrado.",
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
            detail="Este usuario ya tiene asignado ese grupo.",
        )


async def assign_user_modulo(
    user_id: UUID,
    data: UsuarioModuloCreate,
) -> UsuarioModulo:
    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    modulo = await Modulo.get_or_none(id=data.modulo_id)

    if not modulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Módulo no encontrado.",
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
    data: UsuarioAccionCreate,
) -> UsuarioAccion:
    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    accion = await Accion.get_or_none(id=data.accion_id)

    if not accion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acción no encontrada.",
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


async def remove_user_grupo(user_id: UUID, grupo_id: UUID):
    """
    Quita a un usuario el acceso a un grupo.

    No elimina el grupo del catálogo.
    Solo elimina la relación en usuario_registros.
    """

    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    grupo = await RegistroPrincipal.get_or_none(id=grupo_id)

    if not grupo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grupo no encontrado.",
        )

    asignacion = await UsuarioRegistro.get_or_none(
        usuario_id=user_id,
        registro_id=grupo_id,
    )

    if not asignacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no tiene asignado este grupo.",
        )

    await asignacion.delete()

    return {
        "message": "Acceso al grupo removido correctamente.",
        "user_id": str(user_id),
        "grupo_id": str(grupo_id),
    }


async def remove_user_modulo(user_id: UUID, modulo_id: UUID):
    """
    Quita a un usuario el acceso a un módulo.

    No elimina el módulo del catálogo.
    Solo elimina la relación en usuario_modulos.
    """

    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    modulo = await Modulo.get_or_none(id=modulo_id)

    if not modulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Módulo no encontrado.",
        )

    asignacion = await UsuarioModulo.get_or_none(
        usuario_id=user_id,
        modulo_id=modulo_id,
    )

    if not asignacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no tiene asignado este módulo.",
        )

    await asignacion.delete()

    return {
        "message": "Acceso al módulo removido correctamente.",
        "user_id": str(user_id),
        "modulo_id": str(modulo_id),
    }


async def remove_user_accion(user_id: UUID, accion_id: UUID):
    """
    Quita a un usuario el acceso a una acción.

    No elimina la acción del catálogo.
    Solo elimina la relación en usuario_acciones.
    """

    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    accion = await Accion.get_or_none(id=accion_id)

    if not accion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acción no encontrada.",
        )

    asignacion = await UsuarioAccion.get_or_none(
        usuario_id=user_id,
        accion_id=accion_id,
    )

    if not asignacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no tiene asignada esta acción.",
        )

    await asignacion.delete()

    return {
        "message": "Acceso a la acción removido correctamente.",
        "user_id": str(user_id),
        "accion_id": str(accion_id),
    }


async def usuario_tiene_accion(user_id: UUID, accion_nombre: str) -> bool:
    return await UsuarioAccion.filter(
        usuario_id=user_id,
        accion__nombre=accion_nombre,
    ).exists()


async def obtener_permisos_usuario(user_id: UUID) -> dict:
    registros_asignados = await UsuarioRegistro.filter(
        usuario_id=user_id,
    ).prefetch_related("registro")

    modulos_asignados = await UsuarioModulo.filter(
        usuario_id=user_id,
    ).prefetch_related("modulo", "modulo__registro_principal")

    acciones_asignadas = await UsuarioAccion.filter(
        usuario_id=user_id,
    ).prefetch_related("accion", "accion__modulo")

    return {
        "registros": [item.registro for item in registros_asignados],
        "modulos": [item.modulo for item in modulos_asignados],
        "acciones": [item.accion for item in acciones_asignadas],
    }