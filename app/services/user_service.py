from uuid import UUID

from pathlib import Path
from secrets import token_urlsafe
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from tortoise.exceptions import IntegrityError
from tortoise.expressions import F

from app.core.security import get_password_hash, verify_password
from app.core.config import settings

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
    UserMeUpdate,
    CrearPasswordPrimeraVez,
    UsuarioGrupoCreate,
    UsuarioModuloCreate,
    UsuarioAccionCreate,
    UsuarioPermisosMasivosCreate,
)

from app.services.session_service import resetear_ultima_sesion
from app.services.email_service import enviar_correo_html
from app.services.notificacion_service import enviar_correo_cambio_estatus_usuario


async def create_user(user_in: UserCreate, creado_por: UUID) -> User:
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

    user_data = user_in.model_dump()

    # El usuario se crea sin contraseña.
    # La contraseña se creará después mediante el enlace enviado por correo.
    user_data["contrasena_hasheada"] = None

    # Guardamos quién creó al usuario.
    # Este dato NO debe venir del frontend; se toma del usuario autenticado.
    user_data["creado_por"] = creado_por

    user = await User.create(**user_data)

    await user.fetch_related("estatus", "instancia")

    return user


async def update_user(user_id: UUID, user_in: UserUpdate) -> User:
    """
    Actualización administrativa de usuario.

    Permite corregir datos administrativos del usuario, pero NO permite
    modificar contraseña. La contraseña se maneja en flujos separados.
    """

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




async def update_me(user_id: UUID, user_in: UserMeUpdate) -> User:
    """
    Actualiza los datos básicos del usuario autenticado.

    Permite modificar SOLO:
    - nombre
    - primer_apellido
    - segundo_apellido
    - correo_electronico
    - numero_telefono

    No permite modificar:
    - contraseña
    - CURP
    - estatus
    - instancia
    - entidad_federativa_id
    - permisos
    - grupos
    - módulos
    - acciones
    """

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

    for field, value in update_data.items():
        setattr(user, field, value)

    await user.save()
    await user.fetch_related("estatus", "instancia")

    return user






def render_template_email(nombre_template: str, contexto: dict) -> str:
    """
    Carga una plantilla HTML desde app/templates y reemplaza variables simples.

    Ejemplo:
    {{ nombre_completo }}
    {{ link_recuperacion }}
    """

    ruta_template = (
        Path(__file__).resolve().parent.parent
        / "templates"
        / nombre_template
    )

    html = ruta_template.read_text(encoding="utf-8")

    for clave, valor in contexto.items():
        html = html.replace(f"{{{{ {clave} }}}}", str(valor))

    return html





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


async def enviar_correo_bienvenida_usuario(user: User) -> None:
    """
    Envía el correo de bienvenida con el enlace para crear contraseña.

    Este correo debe enviarse después de que el administrador ya haya
    asignado permisos al usuario.
    """

    if user.contrasena_hasheada:
        return

    token = await generar_token_creacion_password(user)

    link_crear_password = (
        f"{settings.FRONTEND_URL}/crear-password?token={token}"
    )

    sistemas_html = await obtener_sistemas_usuario_para_correo(user.id)

    nombre_completo = " ".join(
        parte
        for parte in [
            user.nombre,
            user.primer_apellido,
            user.segundo_apellido,
        ]
        if parte
    )

    html = render_template_email(
        "email_bienvenida.html",
        {
            "nombre_completo": nombre_completo,
            "curp": user.curp,
            "correo_electronico": user.correo_electronico,
            "link_crear_password": link_crear_password,
            "sistemas_html": sistemas_html,
        },
    )

    enviar_correo_html(
        destinatario=user.correo_electronico,
        asunto="Bienvenida/o - Activación de cuenta institucional",
        html=html,
    )




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





async def reenviar_correo_creacion_password(user_id: UUID):
    """
    Reenvía el correo para crear contraseña por primera vez.

    Solo aplica para usuarios que todavía no tienen contraseña configurada.
    Al generar un nuevo token, se eliminan tokens anteriores del mismo tipo.
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

    if user.contrasena_hasheada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya tiene una contraseña configurada.",
        )

    await enviar_correo_bienvenida_usuario(user)

    return {
        "message": "Correo de activación reenviado correctamente.",
        "user_id": str(user.id),
        "correo_electronico": user.correo_electronico,
    }







async def cambiar_estatus_usuario(user_id: UUID, estatus_id: int) -> User:
    """
    Cambia el estatus de un usuario usando cat_estatus_usuarios.

    También:
    - reinicia intentos_login si el nuevo estatus es Activo
    - incrementa token_version para invalidar sesiones activas
    - envía correo notificando el cambio de estatus
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


async def assign_user_grupo(
    user_id: UUID,
    data: UsuarioGrupoCreate,
) -> UsuarioGrupo:
    """
    Asigna un grupo a un usuario.

    Internamente:
    grupo = Grupo
    usuario_grupo = UsuarioGrupo
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

async def remove_user_modulo(user_id: UUID, modulo_id: UUID):
    """
    Quita a un usuario el acceso a un módulo.

    Cascada lógica:
    - elimina acciones asignadas que pertenezcan a ese módulo
    - elimina la relación usuario-módulo
    - INCREMENTA LA VERSIÓN DEL TOKEN PARA CERRAR SESIONES ACTIVAS

    No elimina el grupo padre.
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
        "grupo_padre_eliminado": False,
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

async def get_catalogo_permisos():
    """
    Devuelve todo el catálogo de permisos del sistema.

    Estructura que devuelve:
    - /grupos 
        - módulos de cada grupo
            - acciones de cada módulo

    Esto sirve principalmente para el frontend, para que pueda mostrar
    un árbol de permisos y el usuario administrador pueda seleccionar
    qué permisos asignar sin buscar IDs manualmente en la base de datos.
    """

    grupos = await Grupo.all().prefetch_related(
        # Carga los módulos relacionados con cada grupo.
        "modulos",

        # Carga las acciones relacionadas con cada módulo.
        "modulos__acciones",
    )

    return grupos




async def get_catalogo_permisos_por_grupo(grupo_id: UUID):
    """
    Devuelve módulos y acciones de un grupo específico.
    """

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
):
    """
    Asigna permisos a un usuario de forma masiva.

    Puede asignar:
    - un grupo completo
    - uno o varios módulos
    - una o varias acciones

    Reglas importantes:
    1. Si se asigna un módulo, también se asigna automáticamente
       su grupo padre.
    2. Si se asigna una acción, también se asigna automáticamente
       su módulo padre y su grupo padre.
    3. Si algo ya estaba asignado, no marca error; simplemente lo ignora.
    4. Si se manda grupo_id, se valida que los módulos y acciones
       realmente pertenezcan a ese grupo.

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
    grupos_asignados = 0
    modulos_asignados = 0
    acciones_asignadas = 0

    # ==========================================
    # 1. ASIGNAR GRUPO SI VIENE
    # ==========================================

    if data.grupo_id:
        grupo = await Grupo.get_or_none(id=data.grupo_id)

        if not grupo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grupo no encontrado.",
            )

        _, creado = await UsuarioGrupo.get_or_create(
            usuario_id=user_id,
            grupo_id=data.grupo_id,
        )

        if creado:
            grupos_asignados += 1

    # ==========================================
    # 2. ASIGNAR MÓDULOS
    # ==========================================

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

        _, grupo_creado = await UsuarioGrupo.get_or_create(
            usuario_id=user_id,
            grupo_id=modulo.grupo_id,
        )

        if grupo_creado:
            grupos_asignados += 1

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
        accion = await Accion.get_or_none(id=accion_id).prefetch_related(
            "modulo",
            "modulo__grupo",
        )

        if not accion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Acción no encontrada: {accion_id}",
            )

        if data.grupo_id and accion.modulo.grupo_id != data.grupo_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La acción {accion.nombre} no pertenece al grupo indicado.",
            )

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
            accion_id=accion_id,
        )

        if accion_creada:
            acciones_asignadas += 1

    # Esta parte debe ir FUERA de los for.
    permisos_nuevos_asignados = (
        grupos_asignados > 0
        or modulos_asignados > 0
        or acciones_asignadas > 0
    )

    # Si se asignó al menos un permiso nuevo, actualizamos la última sesión.
    if permisos_nuevos_asignados:
        await resetear_ultima_sesion(user)

    correo_bienvenida_enviado = False

    # Si el usuario todavía no tiene contraseña, enviamos correo de bienvenida.
    # Lo mandamos después de asignar permisos para que el correo ya incluya sistemas/módulos.
    if permisos_nuevos_asignados and not user.contrasena_hasheada:
        await enviar_correo_bienvenida_usuario(user)
        correo_bienvenida_enviado = True

    # Consultamos los permisos finales del usuario para devolverlos
    # ya actualizados en la respuesta.
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




