from uuid import UUID


from secrets import token_urlsafe
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from tortoise.exceptions import IntegrityError
from tortoise.expressions import F

from app.core.security import get_password_hash, verify_password


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

from app.services.session_service import resetear_ultima_sesion

from app.services.notificacion_service import (
    enviar_correo_activacion_usuario,
    enviar_correo_cambio_estatus_usuario,
)


async def create_user(user_in: UserCreate, creado_por: UUID) -> User:
    """
    Crea un usuario dentro de un grupo/registro específico.

    Reglas:
    - El usuario se crea sin contraseña.
    - El usuario debe pertenecer a un grupo desde su creación.
    - SUPER_ADMIN puede crear usuarios en cualquier grupo.
    - Un admin de registro solo puede crear usuarios dentro de su propio grupo.
    - Al crear el usuario, se asigna automáticamente la relación usuario_grupos.
    """

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

    grupo = await Grupo.get_or_none(id=user_in.grupo_id)

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

    # grupo_id no es columna directa de usuarios.
    # Se usa solo para crear la relación en usuario_grupos.
    grupo_id = user_data.pop("grupo_id")

    # El usuario se crea sin contraseña.
    # La contraseña se creará después mediante el enlace enviado por correo.
    user_data["contrasena_hasheada"] = None

    # Guardamos quién creó al usuario.
    # Este dato NO debe venir del frontend; se toma del usuario autenticado.
    user_data["creado_por"] = creado_por

    user = await User.create(**user_data)

    await UsuarioGrupo.get_or_create(
        usuario_id=user.id,
        grupo_id=grupo_id,
    )

    await user.fetch_related("estatus", "instancia")

    return user




async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    current_user_id: UUID,
) -> User:
    """
    Actualización administrativa de usuario.

    Permite corregir datos administrativos del usuario, pero NO permite
    modificar contraseña. La contraseña se maneja en flujos separados.
    """

    await validar_usuario_objetivo_administrable(
        current_user_id=current_user_id,
        target_user_id=user_id,
    )

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

    for field, value in update_data.items():
        setattr(user, field, value)

    await user.save()
    await user.fetch_related("estatus", "instancia")

    return user



async def cambiar_password_usuario(
    user_id: UUID,
    data: CambiarPasswordUsuario,
) -> dict:
    """
    Permite que el usuario autenticado cambie su propia contraseña.

    Reglas:
    - Requiere que el usuario esté autenticado.
    - Requiere contraseña actual correcta.
    - La nueva contraseña debe cumplir política de seguridad.
    - La nueva contraseña no puede ser igual a la actual.
    - Al cambiarla, se incrementa token_version para invalidar sesiones activas.
    """

    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    if not user.contrasena_hasheada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta aún no tiene contraseña configurada. Usa el enlace de activación.",
        )

    if not verify_password(data.password_actual, user.contrasena_hasheada):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contraseña actual es incorrecta.",
        )

    if verify_password(data.password_nueva, user.contrasena_hasheada):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña no puede ser igual a la contraseña actual.",
        )

    user.contrasena_hasheada = get_password_hash(data.password_nueva)
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
        "message": "Contraseña actualizada correctamente. Por seguridad, vuelve a iniciar sesión.",
    }




async def generar_token_creacion_password(user: User) -> str:
    """
    Genera un token para que el usuario cree su contraseña por primera vez.

    Si ya existía otro token de creación de contraseña para este usuario,
    lo eliminamos para dejar activo únicamente el más reciente.
    """

    await TokenUsuario.filter(
        usuario_id=user.id,
        tipo="CREAR_CONTRASENA",
    ).delete()

    token = token_urlsafe(48)

    fecha_expiracion = datetime.now(timezone.utc) + timedelta(hours=24)

    await TokenUsuario.create(
        usuario_id=user.id,
        token=token,
        tipo="CREAR_CONTRASENA",
        fecha_expiracion=fecha_expiracion,
    )

    return token


async def obtener_sistemas_usuario_para_correo(user_id: UUID) -> str:
    """
    Obtiene los grupos/sistemas asignados al usuario y los convierte en HTML
    para incluirlos en el correo de bienvenida.
    """

    permisos = await obtener_permisos_usuario(user_id)
    grupos = permisos.get("grupos", [])

    if not grupos:
        return "<li>No tienes sistemas asignados todavía.</li>"

    html = ""

    for grupo in grupos:
        html += f"<li><strong>{grupo['nombre']}</strong>"

       

        html += "</li>"

    return html







async def crear_password_primera_vez(token: str, password: str):
    """
    Permite crear la contraseña por primera vez usando el token enviado por correo.

    Este flujo se usa cuando el usuario todavía no tiene contraseña configurada.
    """

    token_db = await TokenUsuario.get_or_none(
        token=token,
        tipo="CREAR_CONTRASENA",
    ).prefetch_related("usuario")

    if not token_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o ya utilizado.",
        )

    ahora = datetime.now(timezone.utc)

    if token_db.fecha_expiracion and token_db.fecha_expiracion < ahora:
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

    user.contrasena_hasheada = get_password_hash(password)
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
        "message": "Contraseña creada correctamente. Ya puedes iniciar sesión.",
    }





async def reenviar_correo_creacion_password(
    user_id: UUID,
    current_user_id: UUID,
):
    """
    Reenvía el correo para crear contraseña por primera vez.

    Reglas:
    - SUPER_ADMIN puede reenviar activación a cualquier usuario.
    - Admin normal solo puede reenviar activación a usuarios de sus grupos administrables.
    - Solo aplica si el usuario todavía no tiene contraseña configurada.
    """

    await validar_usuario_objetivo_administrable(
        current_user_id=current_user_id,
        target_user_id=user_id,
    )

    user = await User.get_or_none(id=user_id).prefetch_related(
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

    token = await generar_token_creacion_password(user)

    sistemas_html = await obtener_sistemas_usuario_para_correo(user.id)

    await enviar_correo_activacion_usuario(
        user=user,
        token=token,
        sistemas_html=sistemas_html,
    )

    return {
        "message": "Correo de activación reenviado correctamente.",
        "user_id": str(user.id),
        "correo_electronico": user.correo_electronico,
    }







async def cambiar_estatus_usuario(
    user_id: UUID,
    estatus_id: int,
    current_user_id: UUID,
) -> User:
    """
    Cambia el estatus de un usuario usando cat_estatus_usuarios.

    Reglas de alcance:
    - SUPER_ADMIN / Dios puede cambiar el estatus de cualquier usuario.
    - Un administrador normal solo puede cambiar el estatus de usuarios que
      pertenezcan a sus grupos administrables.
    - Si intenta cambiar el estatus de un usuario fuera de su alcance,
      se responde 403.

    También:
    - Reinicia intentos_login si el nuevo estatus es Activo.
    - Incrementa token_version para invalidar sesiones activas.
    - Envía correo notificando el cambio de estatus.
    """

    await validar_usuario_objetivo_administrable(
        current_user_id=current_user_id,
        target_user_id=user_id,
    )

    user = await User.get_or_none(id=user_id).prefetch_related(
        "estatus",
        "instancia",
    )

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

    estatus_anterior = user.estatus

    # Si el usuario ya tiene ese mismo estatus, no hacemos nada.
    if estatus_anterior and estatus_anterior.id == estatus_usuario.id:
        return user

    # Cambiamos el estatus en memoria.
    user.estatus = estatus_usuario

    # Si se reactiva la cuenta, reiniciamos intentos fallidos.
    if estatus_usuario.nombre.lower() == "activo":
        user.intentos_login = 0

    # Guardamos el cambio de estatus.
    await user.save(
        update_fields=[
            "estatus_id",
            "intentos_login",
        ]
    )

    # Invalidamos tokens activos para que el cambio de estatus tenga efecto.
    await User.filter(id=user_id).update(
        token_version=F("token_version") + 1
    )

    # Refrescamos el usuario para devolver datos actualizados.
    await user.refresh_from_db()
    await user.fetch_related("estatus", "instancia")

    # Enviamos correo notificando el cambio de estatus.
    await enviar_correo_cambio_estatus_usuario(
        user=user,
        estatus_anterior=estatus_anterior,
        estatus_nuevo=estatus_usuario,
        motivo="El estatus de su cuenta fue actualizado por un administrador.",
    )

    return user


async def get_users(current_user_id: UUID) -> list[dict]:
    """
    Lista usuarios según el alcance administrativo del usuario autenticado.

    Reglas:
    - SUPER_ADMIN ve todos los usuarios con grupos, módulos y acciones.
    - Admin de registro ve solo usuarios de sus grupos administrables.
    - Admin normal solo ve grupos, no módulos ni acciones.
    """

    es_super_admin = await usuario_es_super_admin(current_user_id)

    async def serializar_usuario_listado(
        user: User,
        incluir_detalle_permisos: bool,
    ) -> dict:
        if incluir_detalle_permisos:
            permisos = await obtener_permisos_usuario(user.id)
            grupos = permisos.get("grupos", [])
        else:
            grupos = []

            for asignacion in user.grupos_asignados:
                grupo = asignacion.grupo

                grupos.append(
                    {
                        "id": grupo.id,
                        "nombre": grupo.nombre,
                        "descripcion": grupo.descripcion,
                    }
                )

            grupos.sort(key=lambda item: item["nombre"])

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

    grupos_administrables = await obtener_grupos_administrables_usuario(
        current_user_id
    )

    if not grupos_administrables:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para consultar usuarios.",
        )

    usuarios_por_grupo_ids = await UsuarioGrupo.filter(
        grupo_id__in=grupos_administrables,
    ).values_list("usuario_id", flat=True)

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
        )
        for user in usuarios
    ]





async def get_user_by_id(
    user_id: UUID,
    current_user_id: UUID,
) -> User:
    """
    Obtiene un usuario por ID validando alcance administrativo.

    Reglas:
    - SUPER_ADMIN / Dios puede consultar cualquier usuario.
    - Un administrador normal solo puede consultar usuarios que pertenezcan
      a sus grupos administrables.
    - Si el usuario objetivo está fuera de su alcance, responde 403.
    """

    user = await User.get_or_none(id=user_id).prefetch_related(
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

    

    

async def assign_user_grupo(
    user_id: UUID,
    data: UsuarioGrupoCreate,
    current_user_id: UUID,
) -> UsuarioGrupo:
    """
    Asigna un grupo a un usuario validando alcance administrativo.

    Reglas:
    - SUPER_ADMIN puede asignar cualquier grupo.
    - Admin de registro solo puede asignar grupos de su propio alcance.
    """

    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    grupo = await Grupo.get_or_none(id=data.grupo_id)

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

        await resetear_ultima_sesion(user)

        await asignacion.fetch_related("grupo")
        return asignacion

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este usuario ya tiene asignado ese grupo.",
        )

async def assign_user_modulo(
    user_id: UUID,
    data: UsuarioModuloCreate,
    current_user_id: UUID,
) -> UsuarioModulo:
    """
    Asigna un módulo a un usuario validando alcance administrativo.

    Reglas:
    - SUPER_ADMIN puede asignar cualquier módulo.
    - Admin de registro solo puede asignar módulos de su registro.
    - Al asignar módulo, también se asegura que el usuario tenga el grupo padre.
    """

    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    modulo = await Modulo.get_or_none(id=data.modulo_id).prefetch_related(
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

    await UsuarioGrupo.get_or_create(
        usuario_id=user_id,
        grupo_id=modulo.grupo_id,
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
    current_user_id: UUID,
) -> UsuarioAccion:
    """
    Asigna una acción a un usuario validando alcance administrativo.

    Reglas:
    - SUPER_ADMIN puede asignar cualquier acción.
    - Admin de registro solo puede asignar acciones de su registro.
    - Al asignar acción, también se asegura grupo padre y módulo padre.
    """

    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    accion = await Accion.get_or_none(id=data.accion_id).prefetch_related(
        "modulo",
        "modulo__grupo",
    )

    if not accion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acción no encontrada.",
        )
    
    if accion.nombre == "SUPER_ADMIN" and not await usuario_es_super_admin(current_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el super usuario puede asignar permisos SUPER_ADMIN.",
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

        await resetear_ultima_sesion(user)

        await asignacion.fetch_related("accion")
        return asignacion

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este usuario ya tiene asignada esa acción.",
        )


async def remove_user_grupo(
    user_id: UUID,
    grupo_id: UUID,
    current_user_id: UUID,
):
    """
    Quita a un usuario el acceso a un grupo.

    Cascada lógica:
    - elimina acciones asignadas que pertenezcan a módulos de ese grupo
    - elimina módulos asignados que pertenezcan a ese grupo
    - elimina la relación usuario-grupo
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

    grupo = await Grupo.get_or_none(id=grupo_id)

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

    # 1. Obtener IDs de módulos que pertenecen al grupo
    modulo_ids = await Modulo.filter(
        grupo_id=grupo_id,
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

    # 5. Eliminar el grupo asignado al usuario
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

async def remove_user_modulo(
    user_id: UUID,
    modulo_id: UUID,
    current_user_id: UUID,
):
    """
    Quita a un usuario el acceso a un módulo.

    Cascada lógica:
    - elimina acciones asignadas que pertenezcan a ese módulo
    - elimina la relación usuario-módulo
    - incrementa token_version para cerrar sesiones activas
    """

    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    modulo = await Modulo.get_or_none(id=modulo_id).prefetch_related("grupo")

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
    ).values_list("id", flat=True)

    acciones_eliminadas = 0

    if accion_ids:
        acciones_eliminadas = await UsuarioAccion.filter(
            usuario_id=user_id,
            accion_id__in=accion_ids,
        ).delete()

    await asignacion.delete()

    await User.filter(id=user_id).update(
        token_version=F("token_version") + 1
    )

    return {
        "message": "Acceso al módulo removido correctamente.",
        "user_id": str(user_id),
        "modulo_id": str(modulo_id),
        "acciones_eliminadas": acciones_eliminadas,
        "modulo_eliminado": True,
        "grupo_padre_eliminado": False,
    }

async def remove_user_accion(
    user_id: UUID,
    accion_id: UUID,
    current_user_id: UUID,
):
    """
    Quita a un usuario el acceso a una acción.

    No elimina la acción del catálogo.
    Solo elimina la relación en usuario_acciones.
    Incrementa token_version para cerrar sesiones activas.
    """

    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    accion = await Accion.get_or_none(id=accion_id).prefetch_related(
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

    await User.filter(id=user_id).update(
        token_version=F("token_version") + 1
    )

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




async def usuario_es_super_admin(user_id: UUID) -> bool:
    """
    Indica si el usuario tiene el permiso SUPER_ADMIN.

    Este permiso representa al usuario Dios / administrador global.
    Si lo tiene, puede administrar cualquier grupo o sistema.
    """

    return await UsuarioAccion.filter(
        usuario_id=user_id,
        accion__nombre="SUPER_ADMIN",
    ).exists()


async def usuario_tiene_accion_en_grupo(
    user_id: UUID,
    accion_nombre: str,
    grupo_id: UUID,
) -> bool:
    """
    Valida si un usuario tiene una acción específica dentro de un grupo específico.

    Ejemplo:
    - CREAR_USUARIO dentro del grupo MP
    - ASIGNAR_ACCIONES_USUARIO dentro del grupo MH
    - ACTUALIZAR_USUARIO dentro del grupo VF

    Esto evita que un admin de MP pueda administrar usuarios o permisos de MH.
    """

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
    """
    Valida que el usuario pueda ejecutar una acción dentro de un grupo.

    Reglas:
    - Si el usuario tiene SUPER_ADMIN, se permite.
    - Si no tiene SUPER_ADMIN, debe tener la acción dentro del grupo indicado.
    - Si no cumple, devuelve HTTP 403.
    """

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
            detail="No tienes permiso para realizar esta acción dentro de este registro.",
        )


async def obtener_grupos_administrables_usuario(user_id: UUID) -> set[UUID]:
    """
    Devuelve los grupos/registros que el usuario puede administrar.

    Si el usuario tiene SUPER_ADMIN:
    - Devuelve todos los grupos.

    Si no tiene SUPER_ADMIN:
    - Devuelve únicamente los grupos donde tenga ADMINISTRAR_USUARIOS.
    """

    if await usuario_es_super_admin(user_id):
        grupo_ids = await Grupo.all().values_list("id", flat=True)
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
        grupos.add(asignacion.accion.modulo.grupo.id)

    return grupos


async def usuario_pertenece_a_grupo(
    user_id: UUID,
    grupo_id: UUID,
) -> bool:
    """
    Valida si un usuario pertenece a un grupo/registro.

    Sirve para saber si un admin puede ver o modificar a ese usuario
    según el grupo que administra.
    """

    return await UsuarioGrupo.filter(
        usuario_id=user_id,
        grupo_id=grupo_id,
    ).exists()





async def validar_usuario_objetivo_administrable(
    current_user_id: UUID,
    target_user_id: UUID,
) -> None:
    """
    Valida que el usuario autenticado pueda operar sobre el usuario objetivo.

    Reglas:
    - SUPER_ADMIN / Dios puede operar sobre cualquier usuario.
    - Un administrador normal solo puede operar sobre usuarios que pertenezcan
      a los grupos donde él tiene ADMINISTRAR_USUARIOS.
    - Si el usuario objetivo no pertenece a ningún grupo administrable por el
      administrador autenticado, se responde 403.
    """

    # Si el usuario autenticado es SUPER_ADMIN, puede operar sobre cualquiera.
    if await usuario_es_super_admin(current_user_id):
        return

    # Obtenemos los grupos que administra el usuario autenticado.
    grupos_administrables = await obtener_grupos_administrables_usuario(
        current_user_id
    )

    if not grupos_administrables:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes grupos administrables.",
        )

    # Validamos si el usuario objetivo pertenece a por lo menos
    # uno de los grupos administrables del usuario autenticado.
    pertenece_a_grupo_administrable = await UsuarioGrupo.filter(
        usuario_id=target_user_id,
        grupo_id__in=grupos_administrables,
    ).exists()

    if not pertenece_a_grupo_administrable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para operar sobre este usuario.",
        )







async def obtener_permisos_usuario(user_id: UUID) -> dict:
    """
    Devuelve los permisos del usuario organizados de forma jerárquica:

    Grupo
      -> Módulos
          -> Acciones
    """

    grupos_asignados = await UsuarioGrupo.filter(
        usuario_id=user_id,
    ).prefetch_related("grupo")

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

        grupos_dict[grupo_id]["modulos"][modulo_id]["acciones"][accion_id] = {
            "id": accion.id,
            "nombre": accion.nombre,
            "descripcion": accion.descripcion,
        }

    grupos = []

    for grupo_data in grupos_dict.values():
        modulos = []

        for modulo_data in grupo_data["modulos"].values():
            acciones = list(modulo_data["acciones"].values())
            acciones.sort(key=lambda accion: accion["nombre"])

            modulo_data["acciones"] = acciones
            modulos.append(modulo_data)

        modulos.sort(key=lambda modulo: modulo["nombre"])

        grupo_data["modulos"] = modulos
        grupos.append(grupo_data)

    grupos.sort(key=lambda grupo: grupo["nombre"])

    return {
        "grupos": grupos,
    }

# ==========================================
# CATÁLOGO COMPLETO DE PERMISOS
# ==========================================

async def get_catalogo_permisos(current_user_id: UUID):
    """
    Devuelve el catálogo de permisos según el alcance administrativo.

    Reglas:
    - SUPER_ADMIN ve todos los grupos.
    - Admin de registro ve únicamente los grupos donde tiene ADMINISTRAR_USUARIOS.
    """

    if await usuario_es_super_admin(current_user_id):
        return await Grupo.all().prefetch_related(
            "modulos",
            "modulos__acciones",
        )

    grupos_administrables = await obtener_grupos_administrables_usuario(
        current_user_id
    )

    if not grupos_administrables:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para consultar el catálogo de permisos.",
        )

    return await Grupo.filter(
        id__in=grupos_administrables,
    ).prefetch_related(
        "modulos",
        "modulos__acciones",
    )




async def get_catalogo_permisos_por_grupo(
    grupo_id: UUID,
    current_user_id: UUID,
):
    """
    Devuelve módulos y acciones de un grupo específico, validando alcance.

    Reglas:
    - SUPER_ADMIN puede consultar cualquier grupo.
    - Admin de registro solo puede consultar su propio grupo.
    """

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






# ==========================================
# ASIGNACIÓN MASIVA DE PERMISOS
# ==========================================
async def assign_user_permisos_masivos(
    user_id: UUID,
    data: UsuarioPermisosMasivosCreate,
    current_user_id: UUID,
):
    """
    Asigna permisos a un usuario de forma masiva.

    Reglas:
    - SUPER_ADMIN puede asignar permisos de cualquier grupo.
    - Un admin de registro solo puede asignar permisos dentro de su grupo.
    - Si se envía grupo_id, los módulos y acciones deben pertenecer a ese grupo.
    - Si no se envía grupo_id, el backend detecta los grupos de módulos/acciones.
    """

    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    grupos_a_validar = set()

    # ==========================================
    # 1. VALIDAR GRUPO SI VIENE
    # ==========================================

    if data.grupo_id:
        grupo = await Grupo.get_or_none(id=data.grupo_id)

        if not grupo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grupo no encontrado.",
            )

        grupos_a_validar.add(data.grupo_id)

    # ==========================================
    # 2. VALIDAR MÓDULOS Y DETECTAR SUS GRUPOS
    # ==========================================

    modulos_validos = []

    for modulo_id in data.modulo_ids:
        modulo = await Modulo.get_or_none(id=modulo_id).prefetch_related(
            "grupo"
        )

        if not modulo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Módulo no encontrado: {modulo_id}",
            )

        if data.grupo_id and modulo.grupo_id != data.grupo_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El módulo {modulo.nombre} no pertenece al grupo indicado.",
            )

        grupos_a_validar.add(modulo.grupo_id)
        modulos_validos.append(modulo)

    # ==========================================
    # 3. VALIDAR ACCIONES Y DETECTAR SUS GRUPOS
    # ==========================================

    acciones_validas = []

    for accion_id in data.accion_ids:
        accion = await Accion.get_or_none(id=accion_id).prefetch_related(
            "modulo",
            "modulo__grupo",
        )

        if not accion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Acción no encontrada: {accion_id}",
            )

        if accion.nombre == "SUPER_ADMIN" and not await usuario_es_super_admin(current_user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el usuario Dios puede asignar permisos SUPER_ADMIN.",
            )

        if data.grupo_id and accion.modulo.grupo_id != data.grupo_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La acción {accion.nombre} no pertenece al grupo indicado.",
            )

        grupos_a_validar.add(accion.modulo.grupo_id)
        acciones_validas.append(accion)

    if not grupos_a_validar:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes enviar al menos un grupo, módulo o acción para asignar permisos.",
        )

    # ==========================================
    # 4. VALIDAR ALCANCE DEL ADMIN ACTUAL
    # ==========================================

    for grupo_id in grupos_a_validar:
        await validar_accion_en_grupo_o_super_admin(
            user_id=current_user_id,
            accion_nombre="ASIGNAR_ACCIONES_USUARIO",
            grupo_id=grupo_id,
        )

    # ==========================================
    # 5. ASIGNAR PERMISOS
    # ==========================================

    grupos_asignados = 0
    modulos_asignados = 0
    acciones_asignadas = 0

    if data.grupo_id:
        _, creado = await UsuarioGrupo.get_or_create(
            usuario_id=user_id,
            grupo_id=data.grupo_id,
        )

        if creado:
            grupos_asignados += 1

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

    permisos_nuevos_asignados = (
        grupos_asignados > 0
        or modulos_asignados > 0
        or acciones_asignadas > 0
    )

    if permisos_nuevos_asignados:
        await resetear_ultima_sesion(user)

    correo_bienvenida_enviado = False

    if permisos_nuevos_asignados and not user.contrasena_hasheada:
        token = await generar_token_creacion_password(user)

        sistemas_html = await obtener_sistemas_usuario_para_correo(user.id)

        await enviar_correo_activacion_usuario(
            user=user,
            token=token,
            sistemas_html=sistemas_html,
        )

        correo_bienvenida_enviado = True

    permisos = await obtener_permisos_usuario(user_id)

    return {
        "message": "Permisos asignados correctamente.",
        "user_id": str(user_id),
        "grupos_asignados": grupos_asignados,
        "modulos_asignados": modulos_asignados,
        "acciones_asignadas": acciones_asignadas,
        "correo_bienvenida_enviado": correo_bienvenida_enviado,
        "permisos": permisos,
    }




