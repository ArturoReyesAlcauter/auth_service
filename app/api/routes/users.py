from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_active_user, requiere_accion
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserRead,
    UserUpdate,
    UserMeUpdate,
    UserListPublic,
    UsuarioGrupoCreate,
    UsuarioGrupoRead,
    UsuarioModuloCreate,
    UsuarioModuloRead,
    UsuarioAccionCreate,
    UsuarioAccionRead,
    UserWithPermissionsRead,
    GrupoCatalogoRead,
    UsuarioPermisosMasivosCreate,
    CrearPasswordPrimeraVez,
)
from app.services import user_service


router = APIRouter(prefix="/users", tags=["Usuarios"])


# ==========================================
# CREAR USUARIO
# ==========================================

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

    El usuario se crea sin contraseña.
    La contraseña se generará posteriormente mediante el enlace enviado por correo.

    Solo usuarios con permiso CREAR_USUARIO pueden ejecutar esta acción.
    """
    user = await user_service.create_user(user_in)
    await user.fetch_related("estatus", "instancia")
    return user


# ==========================================
# USUARIO AUTENTICADO / MI CUENTA
# ==========================================

@router.get(
    "/me",
    response_model=UserWithPermissionsRead,
    status_code=status.HTTP_200_OK,
)
async def obtener_mi_usuario(
    current_user: User = Depends(get_current_active_user),
):
    """
    Consulta la información del usuario autenticado junto con sus permisos.

    Devuelve:
    - datos generales del usuario
    - estatus
    - instancia
    - permisos organizados por grupo, módulo y acción
    """
    await current_user.fetch_related("estatus", "instancia")

    permisos = await user_service.obtener_permisos_usuario(current_user.id)

    return {
        "id": current_user.id,
        "nombre": current_user.nombre,
        "primer_apellido": current_user.primer_apellido,
        "segundo_apellido": current_user.segundo_apellido,
        "correo_electronico": current_user.correo_electronico,
        "curp": current_user.curp,
        "entidad_federativa_id": current_user.entidad_federativa_id,
        "numero_telefono": current_user.numero_telefono,
        "is_2fa_enabled": current_user.is_2fa_enabled,
        "estatus": current_user.estatus,
        "instancia": current_user.instancia,
        "intentos_login": current_user.intentos_login,
        "fecha_correo_verificado": current_user.fecha_correo_verificado,
        "fecha_creacion": current_user.fecha_creacion,
        "fecha_actualizacion": current_user.fecha_actualizacion,
        "permisos": permisos,
    }


@router.patch(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
)
async def modificar_mi_usuario(
    user_in: UserMeUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """
    Permite que el usuario autenticado actualice solo sus datos básicos.

    Campos permitidos:
    - nombre
    - primer_apellido
    - segundo_apellido
    - correo_electronico
    - numero_telefono
    - password_actual
    - password_nueva

    No permite modificar:
    - CURP
    - estatus
    - instancia
    - permisos
    - grupos
    - módulos
    - acciones
    """
    return await user_service.update_me(
        user_id=current_user.id,
        user_in=user_in,
    )


# ==========================================
# CREAR CONTRASEÑA POR PRIMERA VEZ
# ==========================================

@router.post(
    "/crear-password",
    status_code=status.HTTP_200_OK,
)
async def crear_password_primera_vez(
    data: CrearPasswordPrimeraVez,
):
    """
    Permite crear la contraseña por primera vez usando el token enviado por correo.

    Este endpoint no requiere JWT porque el usuario todavía no tiene contraseña
    ni ha iniciado sesión.
    """
    return await user_service.crear_password_primera_vez(
        token=data.token,
        password=data.password,
    )


# ==========================================
# LISTAR USUARIOS
# ==========================================

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


# ==========================================
# CATÁLOGO DE PERMISOS
# ==========================================

@router.get(
    "/catalogo-permisos",
    response_model=list[GrupoCatalogoRead],
    status_code=status.HTTP_200_OK,
)
async def listar_catalogo_permisos(
    current_user: User = Depends(requiere_accion("VER_USUARIOS")),
):
    """
    Devuelve todo el catálogo de permisos disponible.

    Respuesta:
    - grupos
        - módulos
            - acciones

    Uso:
    Este endpoint sirve para pintar en el frontend un árbol de permisos.
    Así el administrador puede seleccionar visualmente qué permisos
    asignar a un usuario sin buscar IDs manualmente.
    """
    return await user_service.get_catalogo_permisos()


@router.get(
    "/catalogo-permisos/{grupo_id}",
    response_model=GrupoCatalogoRead,
    status_code=status.HTTP_200_OK,
)
async def obtener_catalogo_permisos_por_grupo(
    grupo_id: UUID,
    current_user: User = Depends(requiere_accion("VER_USUARIOS")),
):
    """
    Devuelve el catálogo de permisos de un grupo específico.

    Respuesta:
    - grupo
        - módulos
            - acciones
    """
    return await user_service.get_catalogo_permisos_por_grupo(grupo_id)


# ==========================================
# MODIFICACIÓN ADMINISTRATIVA DE USUARIOS
# ==========================================

@router.patch(
    "/{user_id}/estatus/{estatus_id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
)
async def cambiar_estatus_usuario(
    user_id: UUID,
    estatus_id: int,
    current_user: User = Depends(requiere_accion("ACTUALIZAR_USUARIO")),
):
    """
    Cambia el estatus de un usuario usando cat_estatus_usuarios.

    Ejemplos:
    - 1 = Activo
    - 2 = En Proceso
    - 3 = Inactivo
    - 4 = Intentos en exceso sesión
    """
    return await user_service.cambiar_estatus_usuario(
        user_id=user_id,
        estatus_id=estatus_id,
    )


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
    Modifica datos administrativos de un usuario.

    Permite actualizar:
    - nombre
    - apellidos
    - correo electrónico
    - CURP
    - entidad federativa
    - teléfono
    - estatus
    - instancia

    No modifica:
    - contraseña
    - permisos
    - grupos
    - módulos
    - acciones
    """
    return await user_service.update_user(user_id, user_in)


# ==========================================
# CONSULTAR USUARIO POR ID
# ==========================================

@router.get(
    "/{user_id}",
    response_model=UserWithPermissionsRead,
    status_code=status.HTTP_200_OK,
)
async def obtener_usuario_por_id(
    user_id: UUID,
    current_user: User = Depends(requiere_accion("VER_USUARIO_DETALLE")),
):
    """
    Consulta un usuario específico por su ID junto con sus grupos,
    módulos y acciones asignadas.
    """
    user = await user_service.get_user_by_id(user_id)

    permisos = await user_service.obtener_permisos_usuario(user.id)

    return {
        "id": user.id,
        "nombre": user.nombre,
        "primer_apellido": user.primer_apellido,
        "segundo_apellido": user.segundo_apellido,
        "correo_electronico": user.correo_electronico,
        "curp": user.curp,
        "entidad_federativa_id": user.entidad_federativa_id,
        "numero_telefono": user.numero_telefono,
        "is_2fa_enabled": user.is_2fa_enabled,
        "estatus": user.estatus,
        "instancia": user.instancia,
        "intentos_login": user.intentos_login,
        "fecha_correo_verificado": user.fecha_correo_verificado,
        "fecha_creacion": user.fecha_creacion,
        "fecha_actualizacion": user.fecha_actualizacion,
        "permisos": permisos,
    }


# ==========================================
# ASIGNACIÓN MASIVA DE PERMISOS
# ==========================================

@router.post(
    "/{user_id}/permisos",
    status_code=status.HTTP_201_CREATED,
)
async def asignar_permisos_masivos_usuario(
    user_id: UUID,
    data: UsuarioPermisosMasivosCreate,
    current_user: User = Depends(requiere_accion("ASIGNAR_ACCIONES_USUARIO")),
):
    """
    Asigna permisos a un usuario de forma masiva.

    Body permitido:
    {
      "grupo_id": "uuid-opcional-del-grupo",
      "modulo_ids": ["uuid-modulo-1", "uuid-modulo-2"],
      "accion_ids": ["uuid-accion-1", "uuid-accion-2"]
    }

    Reglas:
    - Si mandas solo grupo_id, asigna el grupo.
    - Si mandas módulos, asigna esos módulos y su grupo padre.
    - Si mandas acciones, asigna esas acciones, sus módulos padre
      y sus grupos padre.
    - Si algo ya estaba asignado, no duplica ni marca error.
    """
    return await user_service.assign_user_permisos_masivos(
        user_id=user_id,
        data=data,
    )


# ==========================================
# ASIGNAR ACCESOS INDIVIDUALES
# ==========================================

@router.post(
    "/{user_id}/grupos",
    response_model=UsuarioGrupoRead,
    status_code=status.HTTP_201_CREATED,
)
async def asignar_grupo_usuario(
    user_id: UUID,
    data: UsuarioGrupoCreate,
    current_user: User = Depends(requiere_accion("ASIGNAR_GRUPOS_USUARIO")),
):
    """
    Asigna un grupo a un usuario.

    Internamente:
    No crea un grupo nuevo, solo crea la asignación usuario-grupo.
    """
    return await user_service.assign_user_grupo(user_id, data)


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
    Solo elimina la asignación en usuario_grupos.
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