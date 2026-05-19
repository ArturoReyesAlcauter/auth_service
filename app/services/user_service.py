from uuid import UUID

from fastapi import HTTPException, status
from tortoise.exceptions import IntegrityError
from app.core.security import get_password_hash
from app.models.user import (
    User,
    EstatusUsuario,
    RegistroPrincipal,
    Modulo,
    Accion,
    UsuarioRegistro,
    UsuarioModulo,
    UsuarioAccion,
)
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UsuarioRegistroCreate,
    UsuarioModuloCreate,
    UsuarioAccionCreate,
    UsuarioPermisosMasivosCreate,
)
from app.services.session_service import resetear_ultima_sesion


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


async def update_user(user_id: UUID, user_in: UserUpdate) -> User:
    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    update_data = user_in.model_dump(exclude_unset=True)

    nuevo_correo = update_data.get("correo_electronico")
    if nuevo_correo:
        correo_duplicado = await User.filter(
            correo_electronico=nuevo_correo
        ).exclude(id=user_id).exists()

        if correo_duplicado:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El correo ya está registrado en otro usuario.",
            )

    nueva_curp = update_data.get("curp")
    if nueva_curp:
        curp_duplicada = await User.filter(
            curp=nueva_curp
        ).exclude(id=user_id).exists()

        if curp_duplicada:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La CURP ya está registrada en otro usuario.",
            )

    password = update_data.pop("password", None)

    if password:
        update_data["contrasena_hasheada"] = get_password_hash(password)

    for field, value in update_data.items():
        setattr(user, field, value)

    await user.save()
    await user.fetch_related("estatus", "instancia")

    return user


async def cambiar_estatus_usuario(user_id: UUID, estatus_id: int) -> User:
    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    estatus_usuario = await EstatusUsuario.get_or_none(id=estatus_id)

    if not estatus_usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estatus de usuario no encontrado.",
        )

    # 1. Aplicamos los cambios al objeto en memoria
    user.estatus = estatus_usuario
    if estatus_usuario.nombre.lower() == "activo":
        user.intentos_login = 0

    # 2. Guardamos SOLO los campos que modificamos en memoria
    await user.save(update_fields=["estatus_id", "intentos_login"])

    # 3. Incrementamos la versión del token de forma atómica directo en la DB
    await User.filter(id=user_id).update(
        token_version=F("token_version") + 1
    )

    # 4. Refrescamos el objeto local con los últimos datos de la DB (incluyendo la nueva versión)
    await user.refresh_from_db()
    await user.fetch_related("estatus", "instancia")

    return user


async def get_users() -> list[User]:
    users = await User.all().prefetch_related("estatus", "instancia")
    return users

async def get_user_by_id(user_id: UUID) -> User:
    user = await User.get_or_none(id=user_id).prefetch_related(
        "estatus",
        "instancia",
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    return user


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

        await resetear_ultima_sesion(user)

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

        await resetear_ultima_sesion(user)

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

        await resetear_ultima_sesion(user)

        await asignacion.fetch_related("accion")
        return asignacion

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este usuario ya tiene asignada esa acción.",
        )   


async def remove_user_grupo(user_id: UUID, grupo_id: UUID):
    """
    Quita a un usuario el acceso a un grupo/registro.

    Cascada lógica:
    - elimina acciones asignadas que pertenezcan a módulos de ese grupo
    - elimina módulos asignados que pertenezcan a ese grupo
    - elimina la relación usuario-registro
    - INCREMENTA LA VERSIÓN DEL TOKEN PARA CERRAR SESIONES ACTIVAS

    No elimina catálogos.
    No elimina el usuario.
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

    # 1. Obtener IDs de módulos que pertenecen al grupo
    modulo_ids = await Modulo.filter(
        registro_principal_id=grupo_id,
    ).values_list("id", flat=True)

    # 2. Obtener IDs de acciones que pertenecen a esos módulos
    accion_ids = await Accion.filter(
        modulo_id__in=modulo_ids,
    ).values_list("id", flat=True)

    # 3. Eliminar acciones asignadas al usuario que pertenecen al grupo
    acciones_eliminadas = 0
    if accion_ids:
        acciones_eliminadas = await UsuarioAccion.filter(
            usuario_id=user_id,
            accion_id__in=accion_ids,
        ).delete()

    # 4. Eliminar módulos asignados al usuario que pertenecen al grupo
    modulos_eliminados = 0
    if modulo_ids:
        modulos_eliminados = await UsuarioModulo.filter(
            usuario_id=user_id,
            modulo_id__in=modulo_ids,
        ).delete()

    # 5. Eliminar el registro/grupo asignado al usuario
    await asignacion.delete()

    # 6. KILL SWITCH: Invalidamos los JWT activos para forzar la actualización de permisos
    await User.filter(id=user_id).update(token_version=F("token_version") + 1)

    return {
        "message": "Acceso al grupo removido correctamente.",
        "user_id": str(user_id),
        "grupo_id": str(grupo_id),
        "acciones_eliminadas": acciones_eliminadas,
        "modulos_eliminados": modulos_eliminados,
        "grupo_eliminado": True,
    }

async def remove_user_modulo(user_id: UUID, modulo_id: UUID):
    """
    Quita a un usuario el acceso a un módulo.

    Cascada lógica:
    - elimina acciones asignadas que pertenezcan a ese módulo
    - elimina la relación usuario-módulo
    - INCREMENTA LA VERSIÓN DEL TOKEN PARA CERRAR SESIONES ACTIVAS

    No elimina el registro/grupo padre.
    No elimina catálogos.
    No elimina el usuario.
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

    # 1. Obtener acciones del módulo
    accion_ids = await Accion.filter(
        modulo_id=modulo_id,
    ).values_list("id", flat=True)

    # 2. Eliminar acciones asignadas al usuario de ese módulo
    acciones_eliminadas = 0
    if accion_ids:
        acciones_eliminadas = await UsuarioAccion.filter(
            usuario_id=user_id,
            accion_id__in=accion_ids,
        ).delete()

    # 3. Eliminar módulo asignado al usuario
    await asignacion.delete()

    # 4. KILL SWITCH: Invalidamos los JWT activos para forzar la actualización de permisos
    await User.filter(id=user_id).update(token_version=F("token_version") + 1)

    return {
        "message": "Acceso al módulo removido correctamente.",
        "user_id": str(user_id),
        "modulo_id": str(modulo_id),
        "acciones_eliminadas": acciones_eliminadas,
        "modulo_eliminado": True,
        "registro_padre_eliminado": False,
    }

async def remove_user_accion(user_id: UUID, accion_id: UUID):
    """
    Quita a un usuario el acceso a una acción.

    No elimina la acción del catálogo.
    Solo elimina la relación en usuario_acciones.
    INCREMENTA LA VERSIÓN DEL TOKEN PARA CERRAR SESIONES ACTIVAS.
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

    # 1. Eliminar la asignación de la acción
    await asignacion.delete()

    # 2. KILL SWITCH: Invalidamos los JWT activos para forzar la actualización de permisos
    await User.filter(id=user_id).update(token_version=F("token_version") + 1)

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


# ==========================================
# CATÁLOGO COMPLETO DE PERMISOS
# ==========================================

async def get_catalogo_permisos():
    """
    Devuelve todo el catálogo de permisos del sistema.

    Estructura que devuelve:
    - registros/grupos principales
        - módulos de cada registro
            - acciones de cada módulo

    Esto sirve principalmente para el frontend, para que pueda mostrar
    un árbol de permisos y el usuario administrador pueda seleccionar
    qué permisos asignar sin buscar IDs manualmente en la base de datos.
    """

    registros = await RegistroPrincipal.all().prefetch_related(
        # Carga los módulos relacionados con cada registro.
        "modulos",

        # Carga las acciones relacionadas con cada módulo.
        "modulos__acciones",
    )

    return registros




async def get_catalogo_permisos_por_registro(registro_id: UUID):
    """
    Devuelve módulos y acciones de un registro/grupo específico.
    """

    registro = await RegistroPrincipal.get_or_none(
        id=registro_id
    ).prefetch_related(
        "modulos",
        "modulos__acciones",
    )

    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro o grupo no encontrado.",
        )

    return registro



# ==========================================
# ASIGNACIÓN MASIVA DE PERMISOS
# ==========================================

async def assign_user_permisos_masivos(
    user_id: UUID,
    data: UsuarioPermisosMasivosCreate,
):
    """
    Asigna permisos a un usuario de forma masiva.

    Puede asignar:
    - un registro/grupo completo
    - uno o varios módulos
    - una o varias acciones

    Reglas importantes:
    1. Si se asigna un módulo, también se asigna automáticamente
       su registro/grupo padre.
    2. Si se asigna una acción, también se asigna automáticamente
       su módulo padre y su registro/grupo padre.
    3. Si algo ya estaba asignado, no marca error; simplemente lo ignora.
    4. Si se manda registro_id, se valida que los módulos y acciones
       realmente pertenezcan a ese registro.

    Esto evita que el frontend tenga que hacer muchas peticiones como:
    - asignar grupo
    - asignar módulo
    - asignar acción
    una por una.
    """

    # Primero validamos que el usuario exista.
    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )



    # Contadores para informar cuántos permisos nuevos se asignaron.
    # Si el permiso ya existía, no se cuenta como nuevo.
    registros_asignados = 0
    modulos_asignados = 0
    acciones_asignadas = 0

    # ==========================================
    # 1. ASIGNAR REGISTRO / GRUPO SI VIENE
    # ==========================================

    if data.registro_id:
        # Validamos que el registro/grupo exista.
        registro = await RegistroPrincipal.get_or_none(id=data.registro_id)

        if not registro:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro o grupo no encontrado.",
            )

        # get_or_create evita duplicados.
        # Si ya existe la relación usuario-registro, no la vuelve a crear.
        _, creado = await UsuarioRegistro.get_or_create(
            usuario_id=user_id,
            registro_id=data.registro_id,
        )

        if creado:
            registros_asignados += 1

    # ==========================================
    # 2. ASIGNAR MÓDULOS
    # ==========================================

    for modulo_id in data.modulo_ids:
        # Buscamos el módulo y cargamos su registro padre.
        modulo = await Modulo.get_or_none(id=modulo_id).prefetch_related(
            "registro_principal"
        )

        if not modulo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Módulo no encontrado: {modulo_id}",
            )

        # Si el request mandó un registro_id, validamos que este módulo
        # realmente pertenezca a ese registro.
        # Esto evita asignar por error módulos de otro sistema.
        if data.registro_id and modulo.registro_principal_id != data.registro_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El módulo {modulo.nombre} no pertenece al registro indicado.",
            )

        # Al asignar un módulo, también aseguramos que el usuario tenga
        # asignado el registro/grupo padre del módulo.
        _, registro_creado = await UsuarioRegistro.get_or_create(
            usuario_id=user_id,
            registro_id=modulo.registro_principal_id,
        )

        if registro_creado:
            registros_asignados += 1

        # Ahora sí asignamos el módulo al usuario.
        _, modulo_creado = await UsuarioModulo.get_or_create(
            usuario_id=user_id,
            modulo_id=modulo_id,
        )

        if modulo_creado:
            modulos_asignados += 1

    # ==========================================
    # 3. ASIGNAR ACCIONES
    # ==========================================

    for accion_id in data.accion_ids:
        # Buscamos la acción y cargamos:
        # - su módulo padre
        # - el registro padre de ese módulo
        accion = await Accion.get_or_none(id=accion_id).prefetch_related(
            "modulo",
            "modulo__registro_principal",
        )

        if not accion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Acción no encontrada: {accion_id}",
            )

        # Si el request mandó un registro_id, validamos que esta acción
        # realmente pertenezca a ese registro.
        if data.registro_id and accion.modulo.registro_principal_id != data.registro_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La acción {accion.nombre} no pertenece al registro indicado.",
            )

        # Al asignar una acción, también aseguramos que el usuario tenga
        # asignado el registro/grupo padre.
        _, registro_creado = await UsuarioRegistro.get_or_create(
            usuario_id=user_id,
            registro_id=accion.modulo.registro_principal_id,
        )

        if registro_creado:
            registros_asignados += 1

        # También aseguramos que tenga asignado el módulo padre.
        _, modulo_creado = await UsuarioModulo.get_or_create(
            usuario_id=user_id,
            modulo_id=accion.modulo_id,
        )

        if modulo_creado:
            modulos_asignados += 1

        # Finalmente asignamos la acción específica.
        _, accion_creada = await UsuarioAccion.get_or_create(
            usuario_id=user_id,
            accion_id=accion_id,
        )

        if accion_creada:
            acciones_asignadas += 1

    # Si se asignó al menos un permiso nuevo, actualizamos la última sesión.
    if registros_asignados > 0 or modulos_asignados > 0 or acciones_asignadas > 0:
        await resetear_ultima_sesion(user)

    # Consultamos los permisos finales del usuario para devolverlos
    # ya actualizados en la respuesta.
    permisos = await obtener_permisos_usuario(user_id)

    return {
    "message": "Permisos asignados correctamente.",
    "user_id": str(user_id),
    "registros_asignados": registros_asignados,
    "modulos_asignados": modulos_asignados,
    "acciones_asignadas": acciones_asignadas,
    "permisos": permisos,
}