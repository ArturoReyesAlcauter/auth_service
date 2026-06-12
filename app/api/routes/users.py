from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_active_user, requiere_accion
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserRead,
    UserUpdate,
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
    CambiarPasswordUsuario,
)
from app.services import user_service, auth_service


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
    Crea un usuario dentro del servicio de autenticación.

    Este endpoint permite registrar una cuenta nueva dentro de auth_service.
    El usuario se crea SIN contraseña, ya que la contraseña será definida
    posteriormente por el propio usuario mediante un enlace de activación
    enviado por correo electrónico.

    Reglas de alcance:
    - SUPER_ADMIN / Dios puede crear usuarios en cualquier grupo o registro.
    - Un administrador normal solo puede crear usuarios dentro de los grupos
      donde tenga el permiso CREAR_USUARIO.
    - Si un administrador intenta crear un usuario en un grupo que no administra,
      el sistema debe responder 403.
    - El grupo inicial del usuario se define mediante grupo_id.

    Importancia de grupo_id:
    - grupo_id indica a qué registro o sistema pertenecerá inicialmente el usuario.
    - No representa todavía permisos funcionales completos.
    - Sirve para que el usuario no quede huérfano sin registro.
    - Sirve para validar que el administrador autenticado tenga permiso para
      crear usuarios dentro de ese grupo.
    - Sirve para que el usuario aparezca en el entorno correspondiente de los
      administradores de ese registro.

    Flujo esperado:
    1. El administrador crea el usuario con sus datos generales y grupo_id.
    2. El usuario queda registrado sin contraseña.
    3. El sistema asigna automáticamente la relación UsuarioGrupo con el grupo
       recibido en grupo_id.
    4. Posteriormente, el administrador asigna módulos y acciones mediante:
       POST /users/{user_id}/permisos
    5. Al asignar permisos, si el usuario todavía no tiene contraseña, el sistema
       envía el correo de bienvenida/activación con el enlace para crear la
       contraseña por primera vez.

    Campos importantes:
    - correo_electronico debe ser único.
    - curp debe ser única.
    - entidad_federativa_id indica la entidad federativa del usuario.
    - estatus_id indica el estado inicial de la cuenta.
    - instancia_id indica la institución o instancia asociada.
    - grupo_id indica el grupo/registro inicial del usuario.

    Restricciones:
    - No permite enviar contraseña.
    - No asigna módulos ni acciones automáticamente.
    - No envía correo de activación al crear el usuario.
    - El correo de activación se envía después, cuando se asignan permisos con
      POST /users/{user_id}/permisos.
    - No permite que un administrador normal cree usuarios en grupos fuera de
      su alcance.

    Ejemplo:
    - Si el usuario autenticado es SUPER_ADMIN, puede crear usuarios para MP,
      MH, VF, RNCAS o futuros registros.
    - Si el usuario autenticado administra solo MP, solo puede crear usuarios
      con grupo_id de MP.
    - Si el usuario autenticado administra MP y MH, puede crear usuarios con
      grupo_id de MP o MH.
    - Si intenta crear un usuario en VF/RNCAS sin administrar esos grupos,
      debe recibir 403.

    Permiso requerido:
    - CREAR_USUARIO
    """
    
    user = await user_service.create_user(
        user_in=user_in,
        creado_por=current_user.id,
        )
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
    Consulta la información del usuario autenticado.

    Este endpoint devuelve los datos principales de la cuenta que inició sesión,
    junto con su estatus, instancia y permisos asignados.

    La respuesta incluye:
    - datos generales del usuario
    - correo electrónico
    - CURP
    - entidad federativa
    - teléfono
    - estatus actual de la cuenta
    - instancia asociada
    - configuración de 2FA
    - permisos organizados por grupo, módulo y acción

    Uso principal:
    Este endpoint sirve para que el frontend pueda saber quién está autenticado
    y qué permisos tiene disponibles para habilitar o bloquear secciones del sistema.

    Requiere:
    - JWT válido.
    - Usuario activo.
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




# ==========================================
# CAMBIAR MI CONTRASEÑA
# ==========================================

@router.post(
    "/me/cambiar-password",
    status_code=status.HTTP_200_OK,
)
async def cambiar_mi_password(
    data: CambiarPasswordUsuario,
    current_user: User = Depends(get_current_active_user),
):
    """
    Permite al usuario autenticado cambiar su propia contraseña.

    Este endpoint solo modifica la contraseña del usuario que inició sesión.
    No permite modificar nombre, apellidos, correo, teléfono, CURP, estatus,
    instancia ni permisos.

    Reglas:
    - Requiere JWT válido.
    - Requiere usuario activo.
    - Requiere enviar la contraseña actual.
    - La contraseña actual debe ser correcta.
    - La nueva contraseña debe cumplir la política de seguridad.
    - La nueva contraseña no puede ser igual a la contraseña actual.

    Comportamiento:
    - Guarda la nueva contraseña de forma hasheada.
    - Reinicia intentos_login a 0.
    - Incrementa token_version para invalidar sesiones activas.
    - El usuario deberá iniciar sesión nuevamente.

    Body esperado:
    {
      "password_actual": "PasswordAnterior123!",
      "password_nueva": "PasswordNueva123!"
    }
    """
    return await user_service.cambiar_password_usuario(
        user_id=current_user.id,
        data=data,
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
    Permite crear la contraseña por primera vez usando un token enviado por correo.

    Este endpoint se usa únicamente para usuarios nuevos que fueron creados por
    un administrador y que todavía no tienen contraseña configurada.

    Flujo esperado:
    1. El administrador crea el usuario.
    2. El administrador asigna permisos.
    3. El sistema envía un correo con un enlace de activación.
    4. El usuario abre el enlace y captura su nueva contraseña.
    5. El frontend envía a este endpoint el token y la contraseña nueva.
    6. El sistema valida el token, guarda la contraseña hasheada y elimina el token.

    Este endpoint no requiere JWT porque el usuario aún no puede iniciar sesión.

    Reglas:
    - El token debe existir.
    - El token debe ser de tipo CREAR_CONTRASENA.
    - El token no debe estar expirado.
    - El usuario no debe tener una contraseña previamente configurada.
    - La contraseña debe cumplir la política de seguridad definida en el schema.

    Al finalizar:
    - Se guarda la contraseña hasheada.
    - Se reinician los intentos de login.
    - Se elimina el token para que no pueda reutilizarse.
    """
    return await user_service.crear_password_primera_vez(
        token=data.token,
        password=data.password,
    )


# ==========================================
# Reenviar password 
# ==========================================
@router.post(
    "/{user_id}/reenviar-activacion",
    status_code=status.HTTP_200_OK,
)
async def reenviar_activacion_usuario(
    user_id: UUID,
    current_user: User = Depends(requiere_accion("ACTUALIZAR_USUARIO")),
):
    """
    Reenvía el correo de activación para que un usuario cree su contraseña.

    Este endpoint es usado por un administrador cuando un usuario nuevo no alcanzó
    a crear su contraseña, perdió el correo de activación o el enlace anterior expiró.

    Solo aplica para usuarios que todavía NO tienen contraseña configurada.

    Flujo:
    1. El administrador solicita reenviar el correo de activación.
    2. El sistema valida que el usuario exista.
    3. El sistema valida que el usuario aún no tenga contraseña.
    4. Se elimina cualquier token anterior de creación de contraseña.
    5. Se genera un nuevo token.
    6. Se envía un nuevo correo de activación.

    Restricciones:
    - Si el usuario ya tiene contraseña, no se reenvía activación.
    - No modifica permisos.
    - No cambia el estatus del usuario.

    Permiso requerido:
    - ACTUALIZAR_USUARIO
    """
    return await user_service.reenviar_correo_creacion_password(user_id)




# ==========================================
# ENVIAR RECUPERACIÓN DE CONTRASEÑA
# ==========================================

@router.post(
    "/{user_id}/enviar-recuperacion-password",
    status_code=status.HTTP_200_OK,
)
async def enviar_recuperacion_password_usuario(
    user_id: UUID,
    current_user: User = Depends(requiere_accion("ACTUALIZAR_USUARIO")),
):
    """
    Envía al usuario un correo para restablecer su contraseña.

    Este endpoint solo puede ejecutarlo un administrador o usuario autorizado.
    Se usa cuando el usuario notificó al administrador que olvidó su contraseña.

    Flujo:
    1. El usuario solicita apoyo al administrador.
    2. El administrador entra al sistema.
    3. El administrador ejecuta este endpoint sobre el usuario correspondiente.
    4. El sistema genera un token temporal de recuperación.
    5. Se envía un correo al usuario con un enlace.
    6. El usuario debe usar el enlace antes de 24 horas.
    7. El usuario captura una nueva contraseña.
    8. El sistema actualiza la contraseña y elimina el token.

    Reglas:
    - El usuario debe existir.
    - El usuario debe tener contraseña previamente configurada.
    - Si ya existía un token anterior de recuperación, se elimina.
    - Solo queda válido el enlace más reciente.
    - No se devuelve el token en la respuesta por seguridad.

    Permiso requerido:
    - ACTUALIZAR_USUARIO
    """
    return await auth_service.enviar_recuperacion_password_por_admin(user_id)





# ==========================================
# LISTAR USUARIOS
# ==========================================

@router.get(
    "",
    response_model=list[UserListPublic],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
async def listar_usuarios(
    current_user: User = Depends(requiere_accion("VER_USUARIOS")),
):
    """
    Lista usuarios según el alcance del usuario autenticado.

    Este endpoint devuelve el listado de usuarios disponibles para el usuario
    que inició sesión, respetando la jerarquía y los permisos por grupo/registro.

    Reglas principales:
    - SUPER_ADMIN / Dios puede visualizar todos los usuarios de todos los
      registros existentes en el servicio de autenticación.
    - Un administrador normal no ve todos los usuarios del sistema.
    - Un administrador normal solo puede visualizar usuarios que pertenezcan
      a los grupos/registros donde él tenga permiso administrativo.
    - Si un administrador pertenece o administra más de un grupo, podrá ver
      usuarios de todos esos grupos.
    - Si un usuario pertenece a alguno de los grupos administrables por el
      administrador autenticado, aparecerá en el listado.
    - Si un usuario pertenece únicamente a grupos que el administrador no
      administra, no aparecerá en la respuesta.

    Ejemplos:
    - Si el usuario autenticado es SUPER_ADMIN:
      puede ver usuarios de MP, MH, VF, RNCAS y futuros registros.

    - Si el usuario autenticado administra solo MP:
      verá usuarios que pertenezcan a MP.
      No verá usuarios exclusivos de MH, VF o RNCAS.

    - Si el usuario autenticado administra MP y MH:
      verá usuarios de MP, usuarios de MH y usuarios que pertenezcan a ambos.
      No verá usuarios exclusivos de VF o RNCAS.

    - Si un usuario objetivo pertenece a MP y RNCAS:
      un administrador de MP sí podrá verlo porque existe cruce con MP.
      un administrador de MH no podrá verlo si no administra MP ni RNCAS.

    Información devuelta:
    - Datos generales del usuario.
    - Estatus.
    - Instancia.
    - Grupos a los que pertenece el usuario.

    Profundidad de información:
    - SUPER_ADMIN puede recibir información más completa de los permisos del
      usuario, incluyendo grupos, módulos y acciones, si el service así lo
      serializa.
    - Un administrador normal solo recibe el listado de usuarios permitidos
      junto con sus grupos correspondientes.
    - Un administrador normal no debe recibir módulos ni acciones de los
      usuarios listados.

    Este endpoint no devuelve:
    - Contraseñas.
    - Tokens.
    - Secretos de 2FA.
    - Información de recuperación de contraseña.

    Uso principal:
    Sirve para que el panel de administración muestre únicamente los usuarios
    que están dentro del entorno o alcance del administrador autenticado.

    Permiso requerido:
    - VER_USUARIOS
    """
    return await user_service.get_users(current_user.id)


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
    Devuelve el catálogo completo de permisos disponible en el sistema.

    La respuesta está organizada jerárquicamente:

    Grupo
      -> Módulos
          -> Acciones

    Uso principal:
    Este endpoint sirve para que el frontend pueda mostrar un árbol de permisos
    y permitir al administrador seleccionar qué accesos asignar a un usuario.

    Ejemplo de uso:
    - Mostrar grupos como MP, MH, VF o RNCAS.
    - Mostrar módulos asociados a cada grupo.
    - Mostrar acciones específicas de cada módulo.

    Este endpoint no asigna permisos.
    Solo consulta el catálogo disponible.

    Permiso requerido:
    - VER_USUARIOS
    """
    return await user_service.get_catalogo_permisos(current_user.id)


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

    La respuesta incluye:
    - datos del grupo
    - módulos pertenecientes al grupo
    - acciones disponibles dentro de cada módulo

    Uso principal:
    Sirve cuando el frontend necesita cargar únicamente los permisos de un sistema
    específico, por ejemplo solo MP, solo MH, solo VF o solo RNCAS.

    Parámetros:
    - grupo_id: identificador UUID del grupo que se desea consultar.

    Si el grupo no existe, el servicio devuelve error 404.

    Permiso requerido:
    - VER_USUARIOS
    """
    return await user_service.get_catalogo_permisos_por_grupo(
    grupo_id=grupo_id,
    current_user_id=current_user.id,
)


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
    Cambia el estatus de un usuario usando el catálogo cat_estatus_usuarios.

    Este endpoint permite activar, inactivar, bloquear o cambiar el estado de una
    cuenta según los valores registrados en la tabla cat_estatus_usuarios.

    Ejemplos comunes:
    - 1 = Activo
    - 2 = En Proceso
    - 3 = Inactivo
    - 4 = Intentos en exceso sesión

    Comportamiento:
    - Cambia el estatus del usuario.
    - Si el nuevo estatus es Activo, reinicia intentos_login a 0.
    - Incrementa token_version para invalidar sesiones activas.
    - Envía correo al usuario notificando el cambio de estatus.

    Uso principal:
    Sirve para que un administrador pueda bloquear, reactivar o inactivar cuentas
    desde el panel de administración.

    Permiso requerido:
    - ACTUALIZAR_USUARIO
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

    Este endpoint es usado por administradores para corregir o actualizar datos
    de una cuenta existente.

    Permite actualizar:
    - nombre
    - primer_apellido
    - segundo_apellido
    - correo_electronico
    - CURP
    - entidad_federativa_id
    - numero_telefono
    - estatus_id
    - instancia_id

    No permite actualizar:
    - contraseña
    - permisos
    - grupos
    - módulos
    - acciones
    - secreto 2FA
    - tokens

    La contraseña se maneja en flujos separados:
    - creación de contraseña por primera vez
    - recuperación de contraseña
    - cambio de contraseña desde /users/me

    Validaciones:
    - El correo no debe estar registrado en otro usuario.
    - La CURP no debe estar registrada en otro usuario.

    Permiso requerido:
    - ACTUALIZAR_USUARIO
    """
    return await user_service.update_user(
        user_id=user_id,
        user_in=user_in,
        current_user_id=current_user.id,
    )


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
    Consulta un usuario específico por su ID.

    Devuelve información detallada del usuario, incluyendo sus permisos asignados
    organizados por grupo, módulo y acción.

    La respuesta incluye:
    - datos generales
    - estatus
    - instancia
    - configuración de 2FA
    - intentos de login
    - fechas de creación y actualización
    - permisos asignados

    Uso principal:
    Sirve para mostrar el detalle de un usuario en una pantalla administrativa
    y revisar exactamente qué accesos tiene.

    Parámetros:
    - user_id: UUID del usuario a consultar.

    Permiso requerido:
    - VER_USUARIO_DETALLE
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

    Este endpoint permite otorgar accesos a un usuario sin tener que llamar
    individualmente a los endpoints de grupos, módulos y acciones.

    Permite asignar:
    - Un grupo directo mediante grupo_id.
    - Varios módulos mediante modulo_ids.
    - Varias acciones mediante accion_ids.

    Funcionamiento jerárquico:
    - Si se envía grupo_id, se asigna ese grupo al usuario.
    - Si se envían modulo_ids, el sistema asigna automáticamente el grupo padre
      de cada módulo.
    - Si se envían accion_ids, el sistema asigna automáticamente:
        1. La acción.
        2. El módulo padre de esa acción.
        3. El grupo padre de ese módulo.

    Esto significa que no es obligatorio enviar grupo_id si se están enviando
    módulos o acciones, ya que el backend puede detectar sus grupos padre.

    Ejemplo 1: asignar solo un grupo
    {
      "grupo_id": "uuid-del-grupo",
      "modulo_ids": [],
      "accion_ids": []
    }

    Ejemplo 2: asignar un grupo con varios módulos
    {
      "grupo_id": "uuid-del-grupo",
      "modulo_ids": [
        "uuid-modulo-1",
        "uuid-modulo-2"
      ],
      "accion_ids": []
    }

    Ejemplo 3: asignar varios grupos indirectamente
    Si se desea asignar más de un grupo en una sola petición, se debe enviar
    grupo_id como null y mandar módulos o acciones pertenecientes a distintos
    grupos.

    {
      "grupo_id": null,
      "modulo_ids": [
        "uuid-modulo-del-grupo-mp",
        "uuid-modulo-del-grupo-mh"
      ],
      "accion_ids": []
    }

    En ese caso el backend asignará automáticamente ambos grupos al usuario,
    porque cada módulo pertenece a un grupo distinto.

    Ejemplo 4: asignar acciones
    {
      "grupo_id": null,
      "modulo_ids": [],
      "accion_ids": [
        "uuid-accion-1",
        "uuid-accion-2",
        "uuid-accion-3"
      ]
    }

    En este caso el backend asignará las acciones indicadas y también asignará
    automáticamente los módulos y grupos correspondientes.

    Reglas de seguridad:
    - SUPER_ADMIN / Dios puede asignar permisos de cualquier grupo.
    - Un administrador de registro solo puede asignar permisos dentro de los
      grupos donde tenga permiso administrativo.
    - Si intenta asignar permisos de un grupo que no administra, el sistema debe
      responder 403.
    - La acción SUPER_ADMIN solo puede ser asignada por un usuario que ya sea
      SUPER_ADMIN.
    - Ningún administrador normal puede otorgar permisos de Dios.

    Comportamiento con duplicados:
    - Si el usuario ya tiene asignado un grupo, módulo o acción, no se duplica.
    - El endpoint puede usarse para agregar nuevos permisos sin borrar los
      permisos anteriores.

    Envío de correo:
    - Este endpoint también forma parte del flujo de activación de cuenta.
    - Si el usuario todavía no tiene contraseña configurada, después de asignar
      permisos el sistema envía el correo de bienvenida/activación.
    - Ese correo incluye el enlace para que el usuario cree su contraseña por
      primera vez.
    - Si el usuario ya tiene contraseña, no se vuelve a enviar correo de
      creación de contraseña.

    Uso recomendado:
    - Crear primero el usuario con POST /users.
    - Después asignar sus permisos con POST /users/{user_id}/permisos.
    - Al asignar permisos, se activa el flujo de correo para creación de
      contraseña, si aplica.

    Permiso requerido:
    - ASIGNAR_ACCIONES_USUARIO
    """
    return await user_service.assign_user_permisos_masivos(
    user_id=user_id,
    data=data,
    current_user_id=current_user.id,
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

    Un grupo representa un sistema o conjunto principal de permisos, por ejemplo:
    MP, MH, VF o RNCAS.

    Este endpoint solo crea la relación entre el usuario y el grupo.
    No crea grupos nuevos en el catálogo.

    Si el usuario ya tiene asignado ese grupo, el servicio devuelve error de conflicto.

    Uso recomendado:
    Utilizar este endpoint cuando se desea asignar únicamente el acceso general
    a un grupo sin asignar módulos o acciones específicas.

    Para asignaciones completas se recomienda usar:
    POST /users/{user_id}/permisos

    Permiso requerido:
    - ASIGNAR_GRUPOS_USUARIO
    """
    return await user_service.assign_user_grupo(
    user_id=user_id,
    data=data,
    current_user_id=current_user.id,
)


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

    Un módulo representa una sección funcional dentro de un grupo o sistema.

    Este endpoint solo crea la relación entre el usuario y el módulo.
    No crea módulos nuevos en el catálogo.

    Si el usuario ya tiene asignado ese módulo, el servicio devuelve error de conflicto.

    Nota:
    Este endpoint no asigna automáticamente acciones internas del módulo.
    Para asignar acciones específicas debe usarse:
    POST /users/{user_id}/acciones

    Para asignaciones jerárquicas automáticas se recomienda usar:
    POST /users/{user_id}/permisos

    Permiso requerido:
    - ASIGNAR_MODULOS_USUARIO
    """
    return await user_service.assign_user_modulo(
    user_id=user_id,
    data=data,
    current_user_id=current_user.id,
)

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

    Una acción representa un permiso puntual dentro de un módulo, por ejemplo:
    crear, leer, editar, aprobar, devolver o administrar.

    Este endpoint solo crea la relación entre el usuario y la acción.
    No crea acciones nuevas en el catálogo.

    Si el usuario ya tiene asignada esa acción, el servicio devuelve error de conflicto.

    Uso principal:
    Sirve para otorgar permisos específicos sin modificar todos los accesos del usuario.

    Para asignaciones jerárquicas automáticas se recomienda usar:
    POST /users/{user_id}/permisos

    Permiso requerido:
    - ASIGNAR_ACCIONES_USUARIO
    """
    return await user_service.assign_user_accion(
        user_id=user_id,
        data=data,
        current_user_id=current_user.id,
    )


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

    Este endpoint elimina la relación entre el usuario y el grupo indicado.
    No elimina el grupo del catálogo.

    Comportamiento:
    - Elimina el grupo asignado al usuario.
    - Elimina los módulos asignados que pertenezcan a ese grupo.
    - Elimina las acciones asignadas que pertenezcan a módulos de ese grupo.
    - Incrementa token_version para invalidar sesiones activas.

    Uso principal:
    Sirve para retirar completamente el acceso de un usuario a un sistema.

    Importante:
    Si el usuario tenía sesión activa, deberá iniciar sesión nuevamente para que
    el cambio de permisos se refleje correctamente.

    Permiso requerido:
    - QUITAR_GRUPOS_USUARIO
    """
    return await user_service.remove_user_grupo(
        user_id=user_id,
        grupo_id=grupo_id,
        current_user_id=current_user.id,
    )


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

    Este endpoint elimina la relación entre el usuario y el módulo indicado.
    No elimina el módulo del catálogo.

    Comportamiento:
    - Elimina el módulo asignado al usuario.
    - Elimina las acciones asignadas que pertenezcan a ese módulo.
    - No elimina el grupo padre.
    - Incrementa token_version para invalidar sesiones activas.

    Uso principal:
    Sirve para retirar acceso a una sección específica de un sistema sin quitar
    completamente el grupo principal.

    Permiso requerido:
    - QUITAR_MODULOS_USUARIO
    """
    return await user_service.remove_user_modulo(
    user_id=user_id,
    modulo_id=modulo_id,
    current_user_id=current_user.id,
)


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
    Quita a un usuario una acción específica.

    Este endpoint elimina únicamente la relación entre el usuario y la acción
    indicada. No elimina la acción del catálogo.

    Comportamiento:
    - Elimina la acción asignada al usuario.
    - No elimina el módulo padre.
    - No elimina el grupo padre.
    - Incrementa token_version para invalidar sesiones activas.

    Uso principal:
    Sirve para retirar un permiso puntual sin afectar otros accesos del usuario.

    Ejemplo:
    Quitar permiso para aprobar registros, pero conservar permisos de lectura
    o edición.

    Permiso requerido:
    - QUITAR_ACCIONES_USUARIO
    """
    return await user_service.remove_user_accion(
    user_id=user_id,
    accion_id=accion_id,
    current_user_id=current_user.id,
)