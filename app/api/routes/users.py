from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserRead,
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
async def crear_usuario(user_in: UserCreate):
    """
    Crea un usuario en el servicio de autenticación.
    """
    user = await user_service.create_user(user_in)
    await user.fetch_related("estatus", "instancia")
    return user


@router.get(
    "",
    response_model=list[UserListPublic],
    status_code=status.HTTP_200_OK,
)
async def listar_usuarios(
    current_user: User = Depends(get_current_active_user),
):
    """
    Lista usuarios registrados.
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
    """
    Devuelve el usuario autenticado junto con sus permisos.
    """
    permisos = await user_service.obtener_permisos_usuario(current_user.id)

    return {
        **current_user.__dict__,
        "permisos": permisos,
    }


@router.post(
    "/{user_id}/registros",
    response_model=UsuarioRegistroRead,
    status_code=status.HTTP_201_CREATED,
)
async def asignar_registro_usuario(
    user_id: UUID,
    data: UsuarioRegistroCreate,
    current_user: User = Depends(get_current_active_user),
):
    """
    Asigna un registro principal a un usuario.
    Ejemplo: MP, MH, VF, RNCAS.
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
    current_user: User = Depends(get_current_active_user),
):
    """
    Asigna un módulo específico a un usuario.
    Ejemplo: Datos Generales, NNA, Seguimiento.
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
    current_user: User = Depends(get_current_active_user),
):
    """
    Asigna una acción específica a un usuario.
    Ejemplo: CREAR_NNA, LEER_NNA, EDITAR_NNA.
    """
    return await user_service.assign_user_accion(user_id, data)