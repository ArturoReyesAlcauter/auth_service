from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_active_user, requiere_accion
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserRead,
    UserUpdate,
    UserListPublic,
    UsuarioRegistroCreate,
    UsuarioRegistroRead,
    UsuarioModuloCreate,
    UsuarioModuloRead,
    UsuarioAccionCreate,
    UsuarioAccionRead,
    UserWithPermissionsRead,
)
from app.services import user_service


router = APIRouter(prefix="/users", tags=["Usuarios"])


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def crear_usuario(
    user_in: UserCreate,
    current_user: User = Depends(requiere_accion("CREAR_USUARIO")),
):
    """
    Crea un usuario en el servicio de autenticación.
    Solo usuarios con permiso CREAR_USUARIO pueden ejecutar esta acción.
    """
    user = await user_service.create_user(user_in)
    await user.fetch_related("estatus", "instancia")
    return user

@router.patch(
    "/{user_id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
)
async def modificar_usuario(
    user_id: UUID,
    user_in: UserUpdate,
    current_user: User = Depends(requiere_accion("ACTUALIZAR_USUARIO")),
):
    """
    Modifica los datos generales de un usuario.

    Permite actualizar:
    - nombre
    - apellidos
    - correo electrónico
    - CURP
    - entidad federativa
    - teléfono
    - contraseña
    - estatus
    - instancia

    No modifica permisos, grupos, módulos ni acciones.
    """
    return await user_service.update_user(user_id, user_in)

@router.get(
    "",
    response_model=list[UserListPublic],
    status_code=status.HTTP_200_OK,
)
async def listar_usuarios(
    current_user: User = Depends(requiere_accion("VER_USUARIOS")),
):
    """
    Lista usuarios registrados.
    Solo usuarios con permiso VER_USUARIOS pueden ejecutar esta acción.
    """
    return await user_service.get_users()


@router.get(
    "/me",
    response_model=UserWithPermissionsRead,
    status_code=status.HTTP_200_OK,
)
async def obtener_mi_usuario(
    current_user: User = Depends(get_current_active_user),
):
    await current_user.fetch_related("estatus", "instancia")

    permisos = await user_service.obtener_permisos_usuario(current_user.id)

    return {
        **current_user.__dict__,
        "estatus": current_user.estatus,
        "instancia": current_user.instancia,
        "permisos": permisos,
    }


# ==========================================
# ASIGNAR ACCESOS
# ==========================================

@router.post(
    "/{user_id}/grupos",
    response_model=UsuarioRegistroRead,
    status_code=status.HTTP_201_CREATED,
)
async def asignar_grupo_usuario(
    user_id: UUID,
    data: UsuarioRegistroCreate,
    current_user: User = Depends(requiere_accion("ASIGNAR_GRUPOS_USUARIO")),
):
    """
    Asigna un grupo a un usuario.

    Internamente:
    grupo = RegistroPrincipal.
    No crea un grupo nuevo, solo crea la asignación usuario-grupo.
    """
    return await user_service.assign_user_registro(user_id, data)



@router.post(
    "/{user_id}/modulos",
    response_model=UsuarioModuloRead,
    status_code=status.HTTP_201_CREATED,
)
async def asignar_modulo_usuario(
    user_id: UUID,
    data: UsuarioModuloCreate,
    current_user: User = Depends(requiere_accion("ASIGNAR_MODULOS_USUARIO")),
):
    """
    Asigna un módulo específico a un usuario.

    No crea un módulo nuevo, solo crea la asignación usuario-módulo.
    """
    return await user_service.assign_user_modulo(user_id, data)


@router.post(
    "/{user_id}/acciones",
    response_model=UsuarioAccionRead,
    status_code=status.HTTP_201_CREATED,
)
async def asignar_accion_usuario(
    user_id: UUID,
    data: UsuarioAccionCreate,
    current_user: User = Depends(requiere_accion("ASIGNAR_ACCIONES_USUARIO")),
):
    """
    Asigna una acción específica a un usuario.

    No crea una acción nueva, solo crea la asignación usuario-acción.
    """
    return await user_service.assign_user_accion(user_id, data)


# ==========================================
# QUITAR / BLOQUEAR ACCESOS
# ==========================================

@router.delete(
    "/{user_id}/grupos/{grupo_id}",
    status_code=status.HTTP_200_OK,
)
async def quitar_grupo_usuario(
    user_id: UUID,
    grupo_id: UUID,
    current_user: User = Depends(requiere_accion("QUITAR_GRUPOS_USUARIO")),
):
    """
    Quita a un usuario el acceso a un grupo.

    No elimina el grupo del catálogo.
    Solo elimina la asignación en usuario_registros.
    """
    return await user_service.remove_user_grupo(user_id, grupo_id)

@router.delete(
    "/{user_id}/modulos/{modulo_id}",
    status_code=status.HTTP_200_OK,
)
async def quitar_modulo_usuario(
    user_id: UUID,
    modulo_id: UUID,
    current_user: User = Depends(requiere_accion("QUITAR_MODULOS_USUARIO")),
):
    """
    Quita a un usuario el acceso a un módulo.

    No elimina el módulo del catálogo.
    Solo elimina la asignación en usuario_modulos.
    """
    return await user_service.remove_user_modulo(user_id, modulo_id)


@router.delete(
    "/{user_id}/acciones/{accion_id}",
    status_code=status.HTTP_200_OK,
)
async def quitar_accion_usuario(
    user_id: UUID,
    accion_id: UUID,
    current_user: User = Depends(requiere_accion("QUITAR_ACCIONES_USUARIO")),
):
    """
    Quita a un usuario el acceso a una acción.

    No elimina la acción del catálogo.
    Solo elimina la asignación en usuario_acciones.
    """
    return await user_service.remove_user_accion(user_id, accion_id)