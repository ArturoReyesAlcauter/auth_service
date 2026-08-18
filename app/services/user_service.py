from uuid import UUID
from secrets import token_urlsafe
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from tortoise.exceptions import IntegrityError

from app.core.security import (
    get_password_hash,
    verify_password,
)

from app.models.user import (
    User,
    EstatusUsuario,
    Grupo,
    Modulo,
    Accion,
    UsuarioGrupo,
    UsuarioModulo,
    UsuarioAccion,
    TokenUsuario,
)

from app.schemas.user import (
    UserCreate,
    UserUpdate,
    CambiarPasswordUsuario,
    UsuarioGrupoCreate,
    UsuarioModuloCreate,
    UsuarioAccionCreate,
    UsuarioPermisosMasivosCreate,
)

from app.services.session_service import (
    resetear_ultima_sesion,
    invalidar_sesiones_usuario,
)

from app.services.notificacion_service import (
    enviar_correo_activacion_usuario,
    enviar_correo_cambio_estatus_usuario,
)


# ============================================================
# CREAR USUARIO
# ============================================================

async def create_user(
    user_in: UserCreate,
    creado_por: UUID,
) -> User:
    """
    Crea un usuario dentro de un grupo/registro específico.

    Reglas:
    - El usuario se crea sin contraseña.
    - El usuario debe pertenecer a un grupo desde su creación.
    - SUPER_ADMIN puede crear usuarios en cualquier grupo.
    - Un administrador solo puede crear usuarios dentro
      de los grupos que puede administrar.
    """

    if await User.exists(
        correo_electronico=user_in.correo_electronico
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo ya está registrado en el sistema.",
        )

    if await User.exists(
        curp=user_in.curp
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La CURP ya está registrada en el sistema.",
        )

    grupo = await Grupo.get_or_none(
        id=user_in.grupo_id
    )

    if not grupo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grupo no encontrado.",
        )

    await validar_accion_en_grupo_o_super_admin(
        user_id=creado_por,
        accion_nombre="CREAR_USUARIO",
        grupo_id=user_in.grupo_id,
    )

    user_data = user_in.model_dump()

    grupo_id = user_data.pop("grupo_id")

    # El usuario inicialmente no tiene contraseña.
    user_data["contrasena_hasheada"] = None

    # Nunca debe venir del frontend.
    user_data["creado_por"] = creado_por

    user = await User.create(
        **user_data
    )

    await UsuarioGrupo.get_or_create(
        usuario_id=user.id,
        grupo_id=grupo_id,
    )

    await user.fetch_related(
        "estatus",
        "instancia",
    )

    return user


# ============================================================
# ACTUALIZAR USUARIO
# ============================================================

async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    current_user_id: UUID,
) -> User:
    """
    Actualización administrativa de usuario.

    No permite modificar la contraseña.
    """

    await validar_usuario_objetivo_administrable(
        current_user_id=current_user_id,
        target_user_id=user_id,
    )

    user = await User.get_or_none(
        id=user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    update_data = user_in.model_dump(
        exclude_unset=True
    )

    nuevo_correo = update_data.get(
        "correo_electronico"
    )

    if nuevo_correo:

        correo_duplicado = await User.filter(
            correo_electronico=nuevo_correo
        ).exclude(
            id=user_id
        ).exists()

        if correo_duplicado:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El correo ya está registrado en otro usuario.",
            )

    nueva_curp = update_data.get(
        "curp"
    )

    if nueva_curp:

        curp_duplicada = await User.filter(
            curp=nueva_curp
        ).exclude(
            id=user_id
        ).exists()

        if curp_duplicada:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La CURP ya está registrada en otro usuario.",
            )

    # Nunca permitir modificar estos campos mediante UserUpdate.
    update_data.pop("contrasena_hasheada", None)
    update_data.pop("token_version", None)
    update_data.pop("creado_por", None)

    for field, value in update_data.items():
        setattr(
            user,
            field,
            value,
        )

    await user.save()

    await user.fetch_related(
        "estatus",
        "instancia",
    )

    return user


# ============================================================
# CAMBIAR PASSWORD
# ============================================================

async def cambiar_password_usuario(
    user_id: UUID,
    data: CambiarPasswordUsuario,
) -> dict:
    """
    Permite que el usuario autenticado cambie su propia contraseña.
    """

    user = await User.get_or_none(
        id=user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    if not user.contrasena_hasheada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "La cuenta aún no tiene contraseña configurada. "
                "Usa el enlace de activación."
            ),
        )

    if not verify_password(
        data.password_actual,
        user.contrasena_hasheada,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contraseña actual es incorrecta.",
        )

    if verify_password(
        data.password_nueva,
        user.contrasena_hasheada,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "La nueva contraseña no puede ser igual "
                "a la contraseña actual."
            ),
        )

    user.contrasena_hasheada = get_password_hash(
        data.password_nueva
    )

    user.intentos_login = 0
    user.token_version += 1

    await user.save(
        update_fields=[
            "contrasena_hasheada",
            "intentos_login",
            "token_version",
            "fecha_actualizacion",
        ]
    )

    return {
        "message": (
            "Contraseña actualizada correctamente. "
            "Por seguridad, vuelve a iniciar sesión."
        ),
    }


# ============================================================
# TOKEN CREACIÓN PASSWORD
# ============================================================

async def generar_token_creacion_password(
    user: User,
) -> str:

    await TokenUsuario.filter(
        usuario_id=user.id,
        tipo="CREAR_CONTRASENA",
    ).delete()

    token = token_urlsafe(48)

    fecha_expiracion = (
        datetime.now(timezone.utc)
        + timedelta(hours=24)
    )

    await TokenUsuario.create(
        usuario_id=user.id,
        token=token,
        tipo="CREAR_CONTRASENA",
        fecha_expiracion=fecha_expiracion,
    )

    return token


# ============================================================
# SISTEMAS DEL USUARIO PARA CORREO
# ============================================================

async def obtener_sistemas_usuario_para_correo(
    user_id: UUID,
) -> str:

    permisos = await obtener_permisos_usuario(
        user_id
    )

    grupos = permisos.get(
        "grupos",
        [],
    )

    if not grupos:
        return (
            "<li>No tienes sistemas asignados todavía.</li>"
        )

    html = ""

    for grupo in grupos:
        html += (
            f"<li><strong>{grupo['nombre']}</strong></li>"
        )

    return html


# ============================================================
# CREAR PASSWORD PRIMERA VEZ
# ============================================================

async def crear_password_primera_vez(
    token: str,
    password: str,
):
    """
    Permite crear la contraseña por primera vez usando
    el token enviado por correo.
    """

    token_db = await TokenUsuario.get_or_none(
        token=token,
        tipo="CREAR_CONTRASENA",
    ).prefetch_related(
        "usuario"
    )

    if not token_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o ya utilizado.",
        )

    ahora = datetime.now(timezone.utc)

    if (
        token_db.fecha_expiracion
        and token_db.fecha_expiracion < ahora
    ):
        await token_db.delete()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace para crear contraseña ha expirado.",
        )

    user = token_db.usuario

    if user.contrasena_hasheada:

        await token_db.delete()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta ya tiene una contraseña configurada.",
        )

    user.contrasena_hasheada = get_password_hash(
        password
    )

    user.intentos_login = 0

    await user.save(
        update_fields=[
            "contrasena_hasheada",
            "intentos_login",
            "fecha_actualizacion",
        ]
    )

    await token_db.delete()

    return {
        "message": (
            "Contraseña creada correctamente. "
            "Ya puedes iniciar sesión."
        ),
    }


# ============================================================
# REENVIAR CORREO DE CREACIÓN DE PASSWORD
# ============================================================

async def reenviar_correo_creacion_password(
    user_id: UUID,
    current_user_id: UUID,
):

    await validar_usuario_objetivo_administrable(
        current_user_id=current_user_id,
        target_user_id=user_id,
    )

    user = await User.get_or_none(
        id=user_id
    ).prefetch_related(
        "estatus",
        "instancia",
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    if user.contrasena_hasheada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya tiene una contraseña configurada.",
        )

    token = await generar_token_creacion_password(
        user
    )

    sistemas_html = await obtener_sistemas_usuario_para_correo(
        user.id
    )

    await enviar_correo_activacion_usuario(
        user=user,
        token=token,
        sistemas_html=sistemas_html,
    )

    return {
        "message": (
            "Correo de activación reenviado correctamente."
        ),
        "user_id": str(user.id),
        "correo_electronico": user.correo_electronico,
    }


# ============================================================
# CAMBIAR ESTATUS
# ============================================================

async def cambiar_estatus_usuario(
    user_id: UUID,
    estatus_id: int,
    current_user_id: UUID,
) -> User:

    await validar_usuario_objetivo_administrable(
        current_user_id=current_user_id,
        target_user_id=user_id,
    )

    user = await User.get_or_none(
        id=user_id
    ).prefetch_related(
        "estatus",
        "instancia",
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    estatus_usuario = await EstatusUsuario.get_or_none(
        id=estatus_id
    )

    if not estatus_usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estatus de usuario no encontrado.",
        )

    estatus_anterior = user.estatus

    if (
        estatus_anterior
        and estatus_anterior.id == estatus_usuario.id
    ):
        return user

    user.estatus = estatus_usuario

    if estatus_usuario.nombre.lower() == "activo":
        user.intentos_login = 0

    await user.save(
        update_fields=[
            "estatus_id",
            "intentos_login",
        ]
    )

    # Invalidar todos los JWT activos por cambio de estatus.
    await invalidar_sesiones_usuario(user)

    await user.fetch_related(
        "estatus",
        "instancia",
    )

    await enviar_correo_cambio_estatus_usuario(
        user=user,
        estatus_anterior=estatus_anterior,
        estatus_nuevo=estatus_usuario,
        motivo=(
            "El estatus de su cuenta fue actualizado "
            "por un administrador."
        ),
    )

    return user

# ============================================================
# LISTAR USUARIOS
# ============================================================

async def get_users(
    current_user_id: UUID,
) -> list[dict]:

    es_super_admin = await usuario_es_super_admin(
        current_user_id
    )

    async def serializar_usuario_listado(
        user: User,
        incluir_detalle_permisos: bool,
        grupos_visibles: set[UUID] | None = None,
    ) -> dict:

        if incluir_detalle_permisos:

            permisos = await obtener_permisos_usuario(
                user.id
            )

            grupos = permisos.get(
                "grupos",
                []
            )

        else:

            grupos = []

            for asignacion in user.grupos_asignados:

                grupo = asignacion.grupo

                # Un administrador no debe ver grupos
                # que no puede administrar.
                if (
                    grupos_visibles is not None
                    and grupo.id not in grupos_visibles
                ):
                    continue

                grupos.append(
                    {
                        "id": grupo.id,
                        "nombre": grupo.nombre,
                        "descripcion": grupo.descripcion,
                    }
                )

            grupos.sort(
                key=lambda item: item["nombre"]
            )

        return {
            "id": user.id,
            "nombre": user.nombre,
            "primer_apellido": user.primer_apellido,
            "segundo_apellido": user.segundo_apellido,
            "correo_electronico": user.correo_electronico,
            "curp": user.curp,
            "entidad_federativa_id": user.entidad_federativa_id,
            "numero_telefono": user.numero_telefono,
            "estatus": user.estatus,
            "instancia": user.instancia,
            "grupos": grupos,
        }

    if es_super_admin:

        usuarios = await User.all().order_by(
            "primer_apellido",
            "segundo_apellido",
            "nombre",
        ).prefetch_related(
            "estatus",
            "instancia",
            "grupos_asignados",
            "grupos_asignados__grupo",
        )

        return [
            await serializar_usuario_listado(
                user=user,
                incluir_detalle_permisos=True,
            )
            for user in usuarios
        ]

    grupos_administrables = (
        await obtener_grupos_administrables_usuario(
            current_user_id
        )
    )

    if not grupos_administrables:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para consultar usuarios.",
        )

    usuarios_por_grupo_ids = await UsuarioGrupo.filter(
        grupo_id__in=grupos_administrables,
    ).values_list(
        "usuario_id",
        flat=True,
    )

    usuarios = await User.filter(
        id__in=usuarios_por_grupo_ids,
    ).order_by(
        "primer_apellido",
        "segundo_apellido",
        "nombre",
    ).prefetch_related(
        "estatus",
        "instancia",
        "grupos_asignados",
        "grupos_asignados__grupo",
    )

    return [
        await serializar_usuario_listado(
            user=user,
            incluir_detalle_permisos=False,
            grupos_visibles=grupos_administrables,
        )
        for user in usuarios
    ]


# ============================================================
# OBTENER USUARIO
# ============================================================

async def get_user_by_id(
    user_id: UUID,
    current_user_id: UUID,
) -> User:

    user = await User.get_or_none(
        id=user_id
    ).prefetch_related(
        "estatus",
        "instancia",
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    await validar_usuario_objetivo_administrable(
        current_user_id=current_user_id,
        target_user_id=user_id,
    )

    return user


# ============================================================
# ASIGNAR GRUPO
# ============================================================

async def assign_user_grupo(
    user_id: UUID,
    data: UsuarioGrupoCreate,
    current_user_id: UUID,
) -> UsuarioGrupo:

    user = await User.get_or_none(
        id=user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    grupo = await Grupo.get_or_none(
        id=data.grupo_id
    )

    if not grupo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grupo no encontrado.",
        )

    await validar_accion_en_grupo_o_super_admin(
        user_id=current_user_id,
        accion_nombre="ASIGNAR_GRUPOS_USUARIO",
        grupo_id=data.grupo_id,
    )

    try:

        asignacion = await UsuarioGrupo.create(
            usuario_id=user_id,
            grupo_id=data.grupo_id,
        )

    except IntegrityError:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este usuario ya tiene asignado ese grupo.",
        )

    # Cambio de permisos:
    # actualizar actividad + invalidar sesiones.
    await resetear_ultima_sesion(user)

    await invalidar_sesiones_usuario(user)

    await asignacion.fetch_related(
        "grupo"
    )

    return asignacion


# ============================================================
# ASIGNAR MÓDULO
# ============================================================

async def assign_user_modulo(
    user_id: UUID,
    data: UsuarioModuloCreate,
    current_user_id: UUID,
) -> UsuarioModulo:

    user = await User.get_or_none(
        id=user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    modulo = await Modulo.get_or_none(
        id=data.modulo_id
    ).prefetch_related(
        "grupo"
    )

    if not modulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Módulo no encontrado.",
        )

    await validar_accion_en_grupo_o_super_admin(
        user_id=current_user_id,
        accion_nombre="ASIGNAR_MODULOS_USUARIO",
        grupo_id=modulo.grupo_id,
    )

    # El módulo requiere su grupo padre.
    await UsuarioGrupo.get_or_create(
        usuario_id=user_id,
        grupo_id=modulo.grupo_id,
    )

    try:

        asignacion = await UsuarioModulo.create(
            usuario_id=user_id,
            modulo_id=data.modulo_id,
        )

    except IntegrityError:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este usuario ya tiene asignado ese módulo.",
        )

    await resetear_ultima_sesion(user)

    await invalidar_sesiones_usuario(user)

    await asignacion.fetch_related(
        "modulo"
    )

    return asignacion


# ============================================================
# ASIGNAR ACCIÓN
# ============================================================

# ============================================================
# ASIGNAR ACCIÓN
# ============================================================

async def assign_user_accion(
    user_id: UUID,
    data: UsuarioAccionCreate,
    current_user_id: UUID,
) -> UsuarioAccion:

    user = await User.get_or_none(
        id=user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    accion = await Accion.get_or_none(
        id=data.accion_id
    ).prefetch_related(
        "modulo",
        "modulo__grupo",
    )

    if not accion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acción no encontrada.",
        )

    if (
        accion.nombre == "SUPER_ADMIN"
        and not await usuario_es_super_admin(
            current_user_id
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo un SUPER_ADMIN puede asignar "
                "permisos SUPER_ADMIN."
            ),
        )

    await validar_accion_en_grupo_o_super_admin(
        user_id=current_user_id,
        accion_nombre="ASIGNAR_ACCIONES_USUARIO",
        grupo_id=accion.modulo.grupo_id,
    )

    await UsuarioGrupo.get_or_create(
        usuario_id=user_id,
        grupo_id=accion.modulo.grupo_id,
    )

    await UsuarioModulo.get_or_create(
        usuario_id=user_id,
        modulo_id=accion.modulo_id,
    )

    try:

        asignacion = await UsuarioAccion.create(
            usuario_id=user_id,
            accion_id=data.accion_id,
        )

    except IntegrityError:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este usuario ya tiene asignada esa acción.",
        )

    await resetear_ultima_sesion(user)

    # Una sola invalidación.
    await invalidar_sesiones_usuario(user)

    await asignacion.fetch_related(
        "accion"
    )

    return asignacion

# ============================================================
# REMOVER GRUPO
# ============================================================

# ============================================================
# REMOVER GRUPO
# ============================================================

async def remove_user_grupo(
    user_id: UUID,
    grupo_id: UUID,
    current_user_id: UUID,
):

    user = await User.get_or_none(
        id=user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    grupo = await Grupo.get_or_none(
        id=grupo_id
    )

    if not grupo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grupo no encontrado.",
        )

    await validar_accion_en_grupo_o_super_admin(
        user_id=current_user_id,
        accion_nombre="QUITAR_GRUPOS_USUARIO",
        grupo_id=grupo_id,
    )

    asignacion = await UsuarioGrupo.get_or_none(
        usuario_id=user_id,
        grupo_id=grupo_id,
    )

    if not asignacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no tiene asignado este grupo.",
        )

    modulo_ids = await Modulo.filter(
        grupo_id=grupo_id,
    ).values_list(
        "id",
        flat=True,
    )

    accion_ids = await Accion.filter(
        modulo_id__in=modulo_ids,
    ).values_list(
        "id",
        flat=True,
    )

    acciones_eliminadas = 0

    if accion_ids:

        acciones_eliminadas = await UsuarioAccion.filter(
            usuario_id=user_id,
            accion_id__in=accion_ids,
        ).delete()

    modulos_eliminados = 0

    if modulo_ids:

        modulos_eliminados = await UsuarioModulo.filter(
            usuario_id=user_id,
            modulo_id__in=modulo_ids,
        ).delete()

    await asignacion.delete()

    # El cambio de permisos invalida los JWT actuales.
    await invalidar_sesiones_usuario(user)

    return {
        "message": "Acceso al grupo removido correctamente.",
        "user_id": str(user_id),
        "grupo_id": str(grupo_id),
        "acciones_eliminadas": acciones_eliminadas,
        "modulos_eliminados": modulos_eliminados,
        "grupo_eliminado": True,
    }


# ============================================================
# REMOVER MÓDULO
# ============================================================

async def remove_user_modulo(
    user_id: UUID,
    modulo_id: UUID,
    current_user_id: UUID,
):

    user = await User.get_or_none(
        id=user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    modulo = await Modulo.get_or_none(
        id=modulo_id
    ).prefetch_related(
        "grupo"
    )

    if not modulo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Módulo no encontrado.",
        )

    await validar_accion_en_grupo_o_super_admin(
        user_id=current_user_id,
        accion_nombre="QUITAR_MODULOS_USUARIO",
        grupo_id=modulo.grupo_id,
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

    accion_ids = await Accion.filter(
        modulo_id=modulo_id,
    ).values_list(
        "id",
        flat=True,
    )

    acciones_eliminadas = 0

    if accion_ids:

        acciones_eliminadas = await UsuarioAccion.filter(
            usuario_id=user_id,
            accion_id__in=accion_ids,
        ).delete()

    await asignacion.delete()

    # El cambio de permisos invalida los JWT actuales.
    await invalidar_sesiones_usuario(user)

    return {
        "message": "Acceso al módulo removido correctamente.",
        "user_id": str(user_id),
        "modulo_id": str(modulo_id),
        "acciones_eliminadas": acciones_eliminadas,
        "modulo_eliminado": True,
        "grupo_padre_eliminado": False,
    }

# ============================================================
# REMOVER ACCIÓN
# ============================================================

async def remove_user_accion(
    user_id: UUID,
    accion_id: UUID,
    current_user_id: UUID,
):

    user = await User.get_or_none(
        id=user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    accion = await Accion.get_or_none(
        id=accion_id
    ).prefetch_related(
        "modulo",
        "modulo__grupo",
    )

    if not accion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acción no encontrada.",
        )

    await validar_accion_en_grupo_o_super_admin(
        user_id=current_user_id,
        accion_nombre="QUITAR_ACCIONES_USUARIO",
        grupo_id=accion.modulo.grupo_id,
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

    # El cambio de permisos invalida los JWT actuales.
    await invalidar_sesiones_usuario(user)

    return {
        "message": "Acceso a la acción removido correctamente.",
        "user_id": str(user_id),
        "accion_id": str(accion_id),
    }

# ============================================================
# VALIDAR ACCIÓN
# ============================================================

async def usuario_tiene_accion(
    user_id: UUID,
    accion_nombre: str,
) -> bool:

    return await UsuarioAccion.filter(
        usuario_id=user_id,
        accion__nombre=accion_nombre,
    ).exists()


# ============================================================
# VALIDAR SUPER ADMIN
# ============================================================

async def usuario_es_super_admin(
    user_id: UUID,
) -> bool:

    return await UsuarioAccion.filter(
        usuario_id=user_id,
        accion__nombre="SUPER_ADMIN",
    ).exists()


# ============================================================
# VALIDAR ACCIÓN EN GRUPO
# ============================================================

async def usuario_tiene_accion_en_grupo(
    user_id: UUID,
    accion_nombre: str,
    grupo_id: UUID,
) -> bool:

    return await UsuarioAccion.filter(
        usuario_id=user_id,
        accion__nombre=accion_nombre,
        accion__modulo__grupo_id=grupo_id,
    ).exists()


async def validar_accion_en_grupo_o_super_admin(
    user_id: UUID,
    accion_nombre: str,
    grupo_id: UUID,
) -> None:

    if await usuario_es_super_admin(user_id):
        return

    tiene_permiso = await usuario_tiene_accion_en_grupo(
        user_id=user_id,
        accion_nombre=accion_nombre,
        grupo_id=grupo_id,
    )

    if not tiene_permiso:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "No tienes permiso para realizar esta "
                "acción dentro de este registro."
            ),
        )


# ============================================================
# GRUPOS ADMINISTRABLES
# ============================================================

async def obtener_grupos_administrables_usuario(
    user_id: UUID,
) -> set[UUID]:

    if await usuario_es_super_admin(user_id):

        grupo_ids = await Grupo.all().values_list(
            "id",
            flat=True,
        )

        return set(grupo_ids)

    asignaciones = await UsuarioAccion.filter(
        usuario_id=user_id,
        accion__nombre="ADMINISTRAR_USUARIOS",
    ).prefetch_related(
        "accion",
        "accion__modulo",
        "accion__modulo__grupo",
    )

    grupos = set()

    for asignacion in asignaciones:

        grupos.add(
            asignacion.accion.modulo.grupo.id
        )

    return grupos


# ============================================================
# PERTENENCIA A GRUPO
# ============================================================

async def usuario_pertenece_a_grupo(
    user_id: UUID,
    grupo_id: UUID,
) -> bool:

    return await UsuarioGrupo.filter(
        usuario_id=user_id,
        grupo_id=grupo_id,
    ).exists()


# ============================================================
# VALIDAR USUARIO ADMINISTRABLE
# ============================================================

async def validar_usuario_objetivo_administrable(
    current_user_id: UUID,
    target_user_id: UUID,
) -> None:

    if await usuario_es_super_admin(
        current_user_id
    ):
        return

    grupos_administrables = (
        await obtener_grupos_administrables_usuario(
            current_user_id
        )
    )

    if not grupos_administrables:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes grupos administrables.",
        )

    pertenece_a_grupo_administrable = (
        await UsuarioGrupo.filter(
            usuario_id=target_user_id,
            grupo_id__in=grupos_administrables,
        ).exists()
    )

    if not pertenece_a_grupo_administrable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "No tienes permiso para operar sobre "
                "este usuario."
            ),
        )


# ============================================================
# OBTENER PERMISOS DEL USUARIO
# ============================================================

async def obtener_permisos_usuario(
    user_id: UUID,
) -> dict:

    grupos_asignados = await UsuarioGrupo.filter(
        usuario_id=user_id,
    ).prefetch_related(
        "grupo"
    )

    modulos_asignados = await UsuarioModulo.filter(
        usuario_id=user_id,
    ).prefetch_related(
        "modulo",
        "modulo__grupo",
    )

    acciones_asignadas = await UsuarioAccion.filter(
        usuario_id=user_id,
    ).prefetch_related(
        "accion",
        "accion__modulo",
        "accion__modulo__grupo",
    )

    grupos_dict = {}

    # ========================================================
    # GRUPOS
    # ========================================================

    for item in grupos_asignados:

        grupo = item.grupo
        grupo_id = str(grupo.id)

        if grupo_id not in grupos_dict:

            grupos_dict[grupo_id] = {
                "id": grupo.id,
                "nombre": grupo.nombre,
                "descripcion": grupo.descripcion,
                "modulos": {},
            }

    # ========================================================
    # MÓDULOS
    # ========================================================

    for item in modulos_asignados:

        modulo = item.modulo
        grupo = modulo.grupo

        grupo_id = str(grupo.id)
        modulo_id = str(modulo.id)

        if grupo_id not in grupos_dict:

            grupos_dict[grupo_id] = {
                "id": grupo.id,
                "nombre": grupo.nombre,
                "descripcion": grupo.descripcion,
                "modulos": {},
            }

        if modulo_id not in grupos_dict[grupo_id]["modulos"]:

            grupos_dict[grupo_id]["modulos"][modulo_id] = {
                "id": modulo.id,
                "nombre": modulo.nombre,
                "descripcion": modulo.descripcion,
                "acciones": {},
            }

    # ========================================================
    # ACCIONES
    # ========================================================

    for item in acciones_asignadas:

        accion = item.accion
        modulo = accion.modulo
        grupo = modulo.grupo

        grupo_id = str(grupo.id)
        modulo_id = str(modulo.id)
        accion_id = str(accion.id)

        if grupo_id not in grupos_dict:

            grupos_dict[grupo_id] = {
                "id": grupo.id,
                "nombre": grupo.nombre,
                "descripcion": grupo.descripcion,
                "modulos": {},
            }

        if modulo_id not in grupos_dict[grupo_id]["modulos"]:

            grupos_dict[grupo_id]["modulos"][modulo_id] = {
                "id": modulo.id,
                "nombre": modulo.nombre,
                "descripcion": modulo.descripcion,
                "acciones": {},
            }

        grupos_dict[grupo_id]["modulos"][
            modulo_id
        ]["acciones"][accion_id] = {
            "id": accion.id,
            "nombre": accion.nombre,
            "descripcion": accion.descripcion,
        }

    # ========================================================
    # ORDENAR
    # ========================================================

    grupos = []

    for grupo_data in grupos_dict.values():

        modulos = []

        for modulo_data in grupo_data["modulos"].values():

            acciones = list(
                modulo_data["acciones"].values()
            )

            acciones.sort(
                key=lambda accion: accion["nombre"]
            )

            modulo_data["acciones"] = acciones

            modulos.append(
                modulo_data
            )

        modulos.sort(
            key=lambda modulo: modulo["nombre"]
        )

        grupo_data["modulos"] = modulos

        grupos.append(
            grupo_data
        )

    grupos.sort(
        key=lambda grupo: grupo["nombre"]
    )

    return {
        "grupos": grupos,
    }


# ============================================================
# CATÁLOGO COMPLETO DE PERMISOS
# ============================================================

async def get_catalogo_permisos(
    current_user_id: UUID,
):

    if await usuario_es_super_admin(
        current_user_id
    ):

        return await Grupo.all().prefetch_related(
            "modulos",
            "modulos__acciones",
        )

    grupos_administrables = (
        await obtener_grupos_administrables_usuario(
            current_user_id
        )
    )

    if not grupos_administrables:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "No tienes permisos para consultar "
                "el catálogo de permisos."
            ),
        )

    return await Grupo.filter(
        id__in=grupos_administrables,
    ).prefetch_related(
        "modulos",
        "modulos__acciones",
    )


# ============================================================
# CATÁLOGO DE PERMISOS POR GRUPO
# ============================================================

async def get_catalogo_permisos_por_grupo(
    grupo_id: UUID,
    current_user_id: UUID,
):

    await validar_accion_en_grupo_o_super_admin(
        user_id=current_user_id,
        accion_nombre="VER_USUARIOS",
        grupo_id=grupo_id,
    )

    grupo = await Grupo.get_or_none(
        id=grupo_id
    ).prefetch_related(
        "modulos",
        "modulos__acciones",
    )

    if not grupo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grupo no encontrado.",
        )

    return grupo


# ============================================================
# ASIGNACIÓN MASIVA DE PERMISOS
# ============================================================

async def assign_user_permisos_masivos(
    user_id: UUID,
    data: UsuarioPermisosMasivosCreate,
    current_user_id: UUID,
):

    user = await User.get_or_none(
        id=user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    grupos_a_validar = set()

    # ========================================================
    # 1. VALIDAR GRUPO
    # ========================================================

    if data.grupo_id:

        grupo = await Grupo.get_or_none(
            id=data.grupo_id
        )

        if not grupo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grupo no encontrado.",
            )

        grupos_a_validar.add(
            data.grupo_id
        )

        await validar_accion_en_grupo_o_super_admin(
            user_id=current_user_id,
            accion_nombre="ASIGNAR_GRUPOS_USUARIO",
            grupo_id=data.grupo_id,
        )

    # ========================================================
    # 2. VALIDAR MÓDULOS
    # ========================================================

    modulos_validos = []

    for modulo_id in data.modulo_ids:

        modulo = await Modulo.get_or_none(
            id=modulo_id
        ).prefetch_related(
            "grupo"
        )

        if not modulo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Módulo no encontrado: {modulo_id}",
            )

        if (
            data.grupo_id
            and modulo.grupo_id != data.grupo_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"El módulo {modulo.nombre} "
                    "no pertenece al grupo indicado."
                ),
            )

        grupos_a_validar.add(
            modulo.grupo_id
        )

        await validar_accion_en_grupo_o_super_admin(
            user_id=current_user_id,
            accion_nombre="ASIGNAR_MODULOS_USUARIO",
            grupo_id=modulo.grupo_id,
        )

        modulos_validos.append(
            modulo
        )

    # ========================================================
    # 3. VALIDAR ACCIONES
    # ========================================================

    acciones_validas = []

    for accion_id in data.accion_ids:

        accion = await Accion.get_or_none(
            id=accion_id
        ).prefetch_related(
            "modulo",
            "modulo__grupo",
        )

        if not accion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Acción no encontrada: {accion_id}",
            )

        if (
            accion.nombre == "SUPER_ADMIN"
            and not await usuario_es_super_admin(
                current_user_id
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Solo el super usuario puede asignar "
                    "permisos SUPER_ADMIN."
                ),
            )

        if (
            data.grupo_id
            and accion.modulo.grupo_id != data.grupo_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"La acción {accion.nombre} "
                    "no pertenece al grupo indicado."
                ),
            )

        grupos_a_validar.add(
            accion.modulo.grupo_id
        )

        await validar_accion_en_grupo_o_super_admin(
            user_id=current_user_id,
            accion_nombre="ASIGNAR_ACCIONES_USUARIO",
            grupo_id=accion.modulo.grupo_id,
        )

        acciones_validas.append(
            accion
        )

    # ========================================================
    # 4. VALIDAR QUE HAYA PERMISOS
    # ========================================================

    if not grupos_a_validar:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Debes enviar al menos un grupo, módulo "
                "o acción para asignar permisos."
            ),
        )

    # ========================================================
    # 5. ASIGNAR
    # ========================================================

    grupos_asignados = 0
    modulos_asignados = 0
    acciones_asignadas = 0

    # ========================================================
    # GRUPO
    # ========================================================

    if data.grupo_id:

        _, creado = await UsuarioGrupo.get_or_create(
            usuario_id=user_id,
            grupo_id=data.grupo_id,
        )

        if creado:
            grupos_asignados += 1

    # ========================================================
    # MÓDULOS
    # ========================================================

    for modulo in modulos_validos:

        _, grupo_creado = await UsuarioGrupo.get_or_create(
            usuario_id=user_id,
            grupo_id=modulo.grupo_id,
        )

        if grupo_creado:
            grupos_asignados += 1

        _, modulo_creado = await UsuarioModulo.get_or_create(
            usuario_id=user_id,
            modulo_id=modulo.id,
        )

        if modulo_creado:
            modulos_asignados += 1

    # ========================================================
    # ACCIONES
    # ========================================================

    for accion in acciones_validas:

        _, grupo_creado = await UsuarioGrupo.get_or_create(
            usuario_id=user_id,
            grupo_id=accion.modulo.grupo_id,
        )

        if grupo_creado:
            grupos_asignados += 1

        _, modulo_creado = await UsuarioModulo.get_or_create(
            usuario_id=user_id,
            modulo_id=accion.modulo_id,
        )

        if modulo_creado:
            modulos_asignados += 1

        _, accion_creada = await UsuarioAccion.get_or_create(
            usuario_id=user_id,
            accion_id=accion.id,
        )

        if accion_creada:
            acciones_asignadas += 1

    # ========================================================
    # ¿SE ASIGNÓ ALGO NUEVO?
    # ========================================================

    permisos_nuevos_asignados = (
        grupos_asignados > 0
        or modulos_asignados > 0
        or acciones_asignadas > 0
    )

    if permisos_nuevos_asignados:

        # Registrar actividad administrativa.
        await resetear_ultima_sesion(user)

        # Invalidar los JWT UNA SOLA VEZ,
        # aunque se hayan asignado varios permisos.
        await invalidar_sesiones_usuario(user)

    # ========================================================
    # CORREO DE BIENVENIDA
    # ========================================================

    correo_bienvenida_enviado = False

    if (
        permisos_nuevos_asignados
        and not user.contrasena_hasheada
    ):

        token = await generar_token_creacion_password(
            user
        )

        sistemas_html = (
            await obtener_sistemas_usuario_para_correo(
                user.id
            )
        )

        await enviar_correo_activacion_usuario(
            user=user,
            token=token,
            sistemas_html=sistemas_html,
        )

        correo_bienvenida_enviado = True

    # ========================================================
    # PERMISOS ACTUALES
    # ========================================================

    permisos = await obtener_permisos_usuario(
        user_id
    )

    return {
        "message": "Permisos asignados correctamente.",
        "user_id": str(user_id),
        "grupos_asignados": grupos_asignados,
        "modulos_asignados": modulos_asignados,
        "acciones_asignadas": acciones_asignadas,
        "correo_bienvenida_enviado": (
            correo_bienvenida_enviado
        ),
        "permisos": permisos,
    }