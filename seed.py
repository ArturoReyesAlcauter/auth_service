import asyncio

from tortoise import Tortoise
from tortoise.expressions import F

from app.core.config import TORTOISE_ORM, settings
from app.core.security import get_password_hash
from app.models.user import (
    Accion,
    EstatusUsuario,
    Grupo,
    Instancia,
    Modulo,
    User,
    UsuarioAccion,
    UsuarioGrupo,
    UsuarioModulo,
)


# ==========================================
# USUARIO ADMIN PREDETERMINADO
# ==========================================

ADMIN_CURP = "AURA000101HDFXXX01"
ADMIN_PASSWORD = settings.ADMIN_INITIAL_PASSWORD
ADMIN_EMAIL = "admin@portusderechos.gob.mx"
ADMIN_ENTIDAD_FEDERATIVA_ID = 9


# ==========================================
# CATÁLOGO ACTUAL DE SISTEMAS Y PERMISOS
# ==========================================

GRUPOS_LEGACY = ["MP", "MH", "VF", "RNCAS"]

GRUPO_MESA_AYUDA = "MESA_AYUDA"
GRUPO_FORMATOS_ATENCIONES = "FORMATOS_ATENCIONES"
GRUPOS_SEMAFORO = {
    "SEMAFORO_ADMIN": "Administración y Supervisión Global del Semáforo",
    "SEMAFORO_DGRJRDNNA": "Dirección General de Regulación, Jurisdicción y Restitución de Derechos de NNA",
    "SEMAFORO_DGRCAS": "Dirección General de Representación Jurídica y Restitución de NNA",
    "SEMAFORO_DGNPDDNNA": "Dirección General de Normatividad, Promoción y Difusión de los Derechos de NNA",
    "SEMAFORO_DGCP": "Dirección General de Coordinación y Políticas",
}


ACCIONES_BITACORA = {
    "VER_BITACORA": (
        "Permite consultar los registros de la bitácora de atenciones."
    ),
    "CREAR_BITACORA": (
        "Permite crear registros en la bitácora de atenciones."
    ),
    "ACTUALIZAR_BITACORA": (
        "Permite actualizar registros de la bitácora de atenciones."
    ),
    "ELIMINAR_BITACORA": (
        "Permite realizar la eliminación lógica de registros "
        "de la bitácora."
    ),
    "SUBIR_ARCHIVO_BITACORA": (
        "Permite adjuntar archivos a un registro de la bitácora."
    ),
}


ACCIONES_REPORTES_INDICADORES = {
    "VER_DASHBOARD": (
        "Permite consultar los indicadores estadísticos "
        "de las atenciones registradas."
    ),
    "GENERAR_REPORTE_EXCEL": (
        "Permite generar y descargar reportes de atenciones "
        "en formato Excel."
    ),
    "GENERAR_REPORTE_PDF": (
        "Permite generar y descargar reportes ejecutivos "
        "de atenciones en formato PDF."
    ),
}


ACCIONES_ADMINISTRACION_USUARIOS = {
    "SUPER_ADMIN": (
        "Permite administrar globalmente todos los sistemas, "
        "grupos y permisos."
    ),
    "ADMINISTRAR_USUARIOS": (
        "Permite administrar usuarios dentro del alcance autorizado."
    ),
    "CREAR_USUARIO": "Permite crear nuevos usuarios.",
    "VER_USUARIOS": "Permite consultar el listado de usuarios.",
    "VER_USUARIO_DETALLE": (
        "Permite consultar el detalle de un usuario."
    ),
    "ACTUALIZAR_USUARIO": (
        "Permite actualizar los datos administrativos de un usuario."
    ),
    "DESACTIVAR_USUARIO": (
        "Permite cambiar o desactivar el estatus de un usuario."
    ),
    "VER_GRUPOS_USUARIO": (
        "Permite consultar los grupos asignados a un usuario."
    ),
    "VER_MODULOS_USUARIO": (
        "Permite consultar los módulos asignados a un usuario."
    ),
    "VER_ACCIONES_USUARIO": (
        "Permite consultar las acciones asignadas a un usuario."
    ),
    "ASIGNAR_GRUPOS_USUARIO": (
        "Permite asignar grupos a un usuario."
    ),
    "ASIGNAR_MODULOS_USUARIO": (
        "Permite asignar módulos a un usuario."
    ),
    "ASIGNAR_ACCIONES_USUARIO": (
        "Permite asignar acciones a un usuario."
    ),
    "QUITAR_GRUPOS_USUARIO": (
        "Permite retirar grupos de un usuario."
    ),
    "QUITAR_MODULOS_USUARIO": (
        "Permite retirar módulos de un usuario."
    ),
    "QUITAR_ACCIONES_USUARIO": (
        "Permite retirar acciones de un usuario."
    ),
}


# Estas acciones quedan registradas para la administración futura del catálogo
# de permisos. Para que sean funcionales todavía deben existir endpoints que
# creen, actualicen y eliminen grupos, módulos y acciones.
ACCIONES_ADMINISTRACION_PERMISOS = {
    "VER_CATALOGO_PERMISOS": (
        "Permite consultar el catálogo de grupos, módulos y acciones."
    ),
    "CREAR_GRUPO": (
        "Permite crear grupos o sistemas dentro del servicio "
        "de autenticación."
    ),
    "ACTUALIZAR_GRUPO": "Permite actualizar grupos o sistemas.",
    "ELIMINAR_GRUPO": "Permite eliminar grupos o sistemas.",
    "CREAR_MODULO": "Permite crear módulos dentro de un grupo.",
    "ACTUALIZAR_MODULO": "Permite actualizar módulos.",
    "ELIMINAR_MODULO": "Permite eliminar módulos.",
    "CREAR_ACCION": "Permite crear acciones dentro de un módulo.",
    "ACTUALIZAR_ACCION": "Permite actualizar acciones.",
    "ELIMINAR_ACCION": "Permite eliminar acciones.",
}



ACCIONES_CAPTURA_FORMATOS = {
    "CAPTURAR_FORMATO_ATENCIONES": (
        "Permite registrar las atenciones mediante el formulario web, "
        "aplicar validaciones, calcular totales automáticamente y generar "
        "un folio único para identificar el registro."
    ),
    "VER_MIS_FORMATOS_ATENCIONES": (
        "Permite consultar únicamente los registros creados por el usuario "
        "autenticado, con folio, periodo, ubicación, fecha de captura y "
        "estatus de revisión."
    ),
    "VER_FORMATO_PROPIO": (
        "Permite consultar el contenido y desglose completo de un registro "
        "creado por el usuario autenticado, impidiendo el acceso a "
        "registros de otros usuarios."
    ),
    "DESCARGAR_COMPROBANTE_FORMATO": (
        "Permite generar y descargar el comprobante PDF de un registro "
        "propio, con folio, periodo, fecha y hora de captura, identificación "
        "y totales generales."
    ),
    "ACTUALIZAR_FORMATO_DEVUELTO": (
        "Permite corregir un registro propio devuelto con estatus "
        "REQUIERE_CORRECCION, conservando las observaciones y la "
        "trazabilidad de las modificaciones."
    ),
}



ACCIONES_GESTION_FORMATOS = {
    "VER_FORMATOS_RECIBIDOS": (
        "Permite consultar los registros recibidos de las procuradurías, "
        "con filtros por folio, usuario, entidad, municipio, periodo, "
        "fecha y estatus de revisión."
    ),
    "VER_DETALLE_FORMATO": (
        "Permite consultar datos generales, indicadores, rangos de edad, "
        "distribución por sexo, discapacidad, totales calculados e "
        "historial de revisión."
    ),
    "INICIAR_REVISION_FORMATO": (
        "Permite iniciar la revisión administrativa de un registro "
        "pendiente, asignar al revisor responsable y registrar la fecha "
        "de inicio del proceso."
    ),
    "DEVOLVER_FORMATO_CORRECCION": (
        "Permite devolver un registro cuando existan inconsistencias u "
        "omisiones, adjuntar observaciones obligatorias y habilitarlo "
        "para su corrección."
    ),
    "VALIDAR_FORMATO_ATENCIONES": (
        "Permite confirmar que la información fue revisada y es coherente, "
        "registrar al responsable y la fecha de validación, y bloquear "
        "su edición ordinaria."
    ),
    "ELIMINAR_FORMATO_ATENCIONES": (
        "Permite realizar la eliminación lógica de un registro por una "
        "causa justificada, conservando su historial y trazabilidad "
        "para auditoría."
    ),
}



ACCIONES_DASHBOARD_FORMATOS = {
    "VER_DASHBOARD_FORMATOS": (
        "Permite acceder al tablero general y consultar indicadores "
        "consolidados de registros pendientes, en revisión, devueltos, "
        "validados y eliminados lógicamente."
    ),
    "VER_ESTADISTICAS_POR_ESTADO": (
        "Permite comparar por entidad federativa los registros, personas "
        "atendidas, eventos reportados y su participación en el periodo "
        "seleccionado."
    ),
    "VER_ESTADISTICAS_POR_MUNICIPIO": (
        "Permite consultar y comparar atenciones por municipio mediante "
        "filtros de entidad federativa, año, periodo, estatus e indicador."
    ),
    "VER_ESTADISTICAS_POR_INDICADOR": (
        "Permite analizar resultados por tipo de atención e indicador, "
        "como NNA atendidos, planes de restitución, medidas de protección, "
        "reunificaciones y denuncias."
    ),
    "VER_ESTADISTICAS_POR_PERIODO": (
        "Permite comparar atenciones entre años y periodos para identificar "
        "variaciones, tendencias y participación de entidades y municipios."
    ),
}



ACCIONES_REPORTES_FORMATOS = {
    "GENERAR_EXCEL_FORMATO_INDIVIDUAL": (
        "Permite generar un Excel institucional de un registro individual "
        "con sus apartados, indicadores, rangos de edad, sexo, discapacidad "
        "y totales oficiales."
    ),
    "GENERAR_EXCEL_FORMATOS_CONSOLIDADO": (
        "Permite generar reportes consolidados en Excel aplicando filtros "
        "por entidad, municipio, año, periodo, estatus de revisión o "
        "nivel nacional."
    ),
    "EXPORTAR_DATOS_FORMATOS": (
        "Permite exportar datos estructurados para análisis autorizado, "
        "conservando la relación entre registros, indicadores, ubicación, "
        "periodo y estatus."
    ),
}


# 2. Acciones del Semáforo
ACCIONES_SEMAFORO_CRUD = {
    "VER_ACCIONES_SEMAFORO": "Permite visualizar las acciones de su respectiva DG.",
    "CREAR_ACCION_SEMAFORO": "Permite crear una nueva acción en el semáforo.",
    "EDITAR_ACCION_SEMAFORO": "Permite editar las acciones pertenecientes a su DG.",
    "ELIMINAR_ACCION_SEMAFORO": "Permite eliminar lógicamente una acción.",
}

ACCIONES_SEMAFORO_DASHBOARD = {
    "VER_DASHBOARD_SEMAFORO": "Permite consultar las estadísticas del semáforo.",
}

ACCIONES_SEMAFORO_ADMIN = {
    "ADMINISTRAR_TODO_SEMAFORO": "Permite consultar, editar y supervisar los registros de todas las DGs en el Semáforo.",
}

# 3. Usuarios base de prueba para Semáforo (Las CURP deben ser de 18 caracteres)
USUARIOS_PRUEBA_SEMAFORO = [
    {"curp": "DGRJRDNNA000000000", "nombre": "Usuario", "apellido": "DGRJRDNNA", "grupo": "SEMAFORO_DGRJRDNNA"},
    {"curp": "DGRCAS000000000000", "nombre": "Usuario", "apellido": "DGRCAS", "grupo": "SEMAFORO_DGRCAS"},
    {"curp": "DGNPDDNNA000000000", "nombre": "Usuario", "apellido": "DGNPDDNNA", "grupo": "SEMAFORO_DGNPDDNNA"},
    {"curp": "DGCP00000000000000", "nombre": "Usuario", "apellido": "DGCP", "grupo": "SEMAFORO_DGCP"},
]

async def asegurar_estatus_usuario(
    id_estatus: int,
    nombre: str,
) -> EstatusUsuario:
    estatus, _ = await EstatusUsuario.get_or_create(
        id=id_estatus,
        defaults={"nombre": nombre},
    )

    if estatus.nombre != nombre:
        estatus.nombre = nombre
        await estatus.save(update_fields=["nombre"])

    return estatus


async def asegurar_instancia(
    siglas: str,
    nombre: str,
) -> Instancia:
    instancia, _ = await Instancia.get_or_create(
        siglas=siglas,
        defaults={"nombre": nombre},
    )

    if instancia.nombre != nombre:
        instancia.nombre = nombre
        await instancia.save(update_fields=["nombre"])

    return instancia


async def asegurar_grupo(
    nombre: str,
    descripcion: str,
) -> tuple[Grupo, bool]:
    grupo, creado = await Grupo.get_or_create(
        nombre=nombre,
        defaults={"descripcion": descripcion},
    )

    if grupo.descripcion != descripcion:
        grupo.descripcion = descripcion
        await grupo.save(update_fields=["descripcion"])
        creado = True

    return grupo, creado


async def asegurar_modulo(
    grupo: Grupo,
    nombre: str,
    descripcion: str,
) -> tuple[Modulo, bool]:
    modulo, creado = await Modulo.get_or_create(
        grupo=grupo,
        nombre=nombre,
        defaults={"descripcion": descripcion},
    )

    if modulo.descripcion != descripcion:
        modulo.descripcion = descripcion
        await modulo.save(update_fields=["descripcion"])
        creado = True

    return modulo, creado


async def asegurar_acciones(
    modulo: Modulo,
    acciones: dict[str, str],
) -> tuple[list[Accion], bool]:
    acciones_creadas: list[Accion] = []
    hubo_cambios = False

    # El seed es la fuente de verdad para cada módulo: elimina acciones
    # que ya no estén declaradas y conserva únicamente el catálogo actual.
    eliminadas = await Accion.filter(
        modulo=modulo
    ).exclude(
        nombre__in=list(acciones.keys())
    ).delete()

    hubo_cambios = hubo_cambios or eliminadas > 0

    for nombre, descripcion in acciones.items():
        accion, creada = await Accion.get_or_create(
            modulo=modulo,
            nombre=nombre,
            defaults={"descripcion": descripcion},
        )

        if accion.descripcion != descripcion:
            accion.descripcion = descripcion
            await accion.save(update_fields=["descripcion"])
            creada = True

        acciones_creadas.append(accion)
        hubo_cambios = hubo_cambios or creada

    return acciones_creadas, hubo_cambios


async def eliminar_catalogo_legacy() -> bool:
    """
    Elimina los grupos heredados y todo su árbol mediante CASCADE.
    """

    eliminados = await Grupo.filter(
        nombre__in=GRUPOS_LEGACY
    ).delete()

    return eliminados > 0


async def main() -> None:
    await Tortoise.init(config=TORTOISE_ORM)

    try:
        print(
            "Iniciando seed de auth_service para "
            "Mesa de Ayuda y Formatos de Atenciones..."
        )

        permisos_modificados = await eliminar_catalogo_legacy()

        # ==========================================
        # 1. ESTATUS DE USUARIO
        # ==========================================

        estatus_activo = await asegurar_estatus_usuario(
            1,
            "Activo",
        )
        await asegurar_estatus_usuario(
            2,
            "En Proceso",
        )
        await asegurar_estatus_usuario(
            3,
            "Inactivo",
        )
        await asegurar_estatus_usuario(
            4,
            "Intentos en exceso sesión",
        )

        # ==========================================
        # 2. INSTANCIAS VIGENTES
        # ==========================================

        instancia_sndif = await asegurar_instancia(
            "SNDIF",
            "Sistema Nacional para el Desarrollo Integral de la Familia",
        )
        await asegurar_instancia(
            "PFPNNA",
            (
                "Procuraduría Federal de Protección de Niñas, "
                "Niños y Adolescentes"
            ),
        )

        # ==========================================
        # 3. GRUPOS VIGENTES
        # ==========================================

        grupo_mesa_ayuda, creado = await asegurar_grupo(
            GRUPO_MESA_AYUDA,
            "Sistema de Mesa de Ayuda y control de atenciones.",
        )
        permisos_modificados = permisos_modificados or creado


        grupo_formatos_atenciones, creado = await asegurar_grupo(
            GRUPO_FORMATOS_ATENCIONES,
            (
                "Plataforma institucional para registrar, revisar, validar "
                "y analizar las atenciones reportadas por procuradurías "
                "estatales y municipales, así como generar indicadores "
                "y reportes."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        # ==========================================
        # 4. MÓDULOS DE MESA DE AYUDA
        # ==========================================

        modulo_bitacora, creado = await asegurar_modulo(
            grupo_mesa_ayuda,
            "BITACORA_ATENCIONES",
            "Registro y seguimiento de las atenciones proporcionadas.",
        )
        permisos_modificados = permisos_modificados or creado

        acciones_bitacora, cambios = await asegurar_acciones(
            modulo_bitacora,
            ACCIONES_BITACORA,
        )
        permisos_modificados = permisos_modificados or cambios

        modulo_usuarios, creado = await asegurar_modulo(
            grupo_mesa_ayuda,
            "ADMINISTRACION_USUARIOS",
            "Administración de usuarios y asignación de accesos.",
        )
        permisos_modificados = permisos_modificados or creado

        acciones_usuarios, cambios = await asegurar_acciones(
            modulo_usuarios,
            ACCIONES_ADMINISTRACION_USUARIOS,
        )
        permisos_modificados = permisos_modificados or cambios

        modulo_permisos, creado = await asegurar_modulo(
            grupo_mesa_ayuda,
            "ADMINISTRACION_PERMISOS",
            (
                "Administración del catálogo de grupos, "
                "módulos y acciones."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_permisos, cambios = await asegurar_acciones(
            modulo_permisos,
            ACCIONES_ADMINISTRACION_PERMISOS,
        )
        permisos_modificados = permisos_modificados or cambios

        modulo_reportes, creado = await asegurar_modulo(
            grupo_mesa_ayuda,
            "REPORTES_INDICADORES",
            (
                "Consulta de indicadores estadísticos y generación "
                "de reportes de la Mesa de Ayuda."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_reportes, cambios = await asegurar_acciones(
            modulo_reportes,
            ACCIONES_REPORTES_INDICADORES,
        )
        permisos_modificados = permisos_modificados or cambios

        # ==========================================
        # 5. MÓDULOS DE FORMATOS DE ATENCIONES
        # ==========================================


        modulo_captura_formatos, creado = await asegurar_modulo(
            grupo_formatos_atenciones,
            "CAPTURA_FORMATOS",
            (
                "Permite registrar atenciones mediante formularios web, "
                "consultar registros propios, descargar comprobantes y "
                "corregir información devuelta con observaciones."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_captura_formatos, cambios = await asegurar_acciones(
            modulo_captura_formatos,
            ACCIONES_CAPTURA_FORMATOS,
        )
        permisos_modificados = permisos_modificados or cambios


        modulo_gestion_formatos, creado = await asegurar_modulo(
            grupo_formatos_atenciones,
            "GESTION_FORMATOS",
            (
                "Permite consultar y revisar registros recibidos, emitir "
                "observaciones, devolver información para corrección, "
                "validarla y conservar la trazabilidad administrativa."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_gestion_formatos, cambios = await asegurar_acciones(
            modulo_gestion_formatos,
            ACCIONES_GESTION_FORMATOS,
        )
        permisos_modificados = permisos_modificados or cambios


        modulo_dashboard_formatos, creado = await asegurar_modulo(
            grupo_formatos_atenciones,
            "DASHBOARD_FORMATOS",
            (
                "Permite consultar indicadores por entidad, municipio, "
                "periodo, tipo de atención, rango de edad, sexo, "
                "discapacidad y estatus de revisión."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_dashboard_formatos, cambios = await asegurar_acciones(
            modulo_dashboard_formatos,
            ACCIONES_DASHBOARD_FORMATOS,
        )
        permisos_modificados = permisos_modificados or cambios


        modulo_reportes_formatos, creado = await asegurar_modulo(
            grupo_formatos_atenciones,
            "REPORTES_FORMATOS",
            (
                "Permite generar y descargar reportes individuales o "
                "consolidados en Excel, con filtros por entidad, municipio, "
                "periodo y estatus de revisión."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_reportes_formatos, cambios = await asegurar_acciones(
            modulo_reportes_formatos,
            ACCIONES_REPORTES_FORMATOS,
        )
        permisos_modificados = permisos_modificados or cambios

        # ==========================================
        # 6. CATÁLOGO VIGENTE
        # ==========================================

        grupos_actuales = [
            grupo_mesa_ayuda,
            grupo_formatos_atenciones,
        ]

        modulos_mesa_ayuda = [
            modulo_bitacora,
            modulo_usuarios,
            modulo_permisos,
            modulo_reportes,
        ]

        modulos_formatos_atenciones = [
            modulo_captura_formatos,
            modulo_gestion_formatos,
            modulo_dashboard_formatos,
            modulo_reportes_formatos,
        ]

        modulos_actuales = [
            *modulos_mesa_ayuda,
            *modulos_formatos_atenciones,
        ]

        acciones_actuales = [
            *acciones_bitacora,
            *acciones_usuarios,
            *acciones_permisos,
            *acciones_reportes,
            *acciones_captura_formatos,
            *acciones_gestion_formatos,
            *acciones_dashboard_formatos,
            *acciones_reportes_formatos,
        ]

        # El seed es la fuente de verdad para los módulos de ambos grupos.
        modulos_eliminados_mesa = await Modulo.filter(
            grupo=grupo_mesa_ayuda
        ).exclude(
            id__in=[
                modulo.id
                for modulo in modulos_mesa_ayuda
            ]
        ).delete()

        modulos_eliminados_formatos = await Modulo.filter(
            grupo=grupo_formatos_atenciones
        ).exclude(
            id__in=[
                modulo.id
                for modulo in modulos_formatos_atenciones
            ]
        ).delete()

        permisos_modificados = permisos_modificados or any(
            cantidad > 0
            for cantidad in [
                modulos_eliminados_mesa,
                modulos_eliminados_formatos,
            ]
        )

        # ==========================================
        # X. MÓDULOS Y GRUPOS DE SEMÁFORO
        # ==========================================
        
        grupos_semaforo_obj = []
        
        for nombre_grupo, desc_grupo in GRUPOS_SEMAFORO.items():
            # 1. Asegurar la creación del grupo
            grupo, creado = await asegurar_grupo(nombre_grupo, desc_grupo)
            grupos_semaforo_obj.append(grupo)
            permisos_modificados = permisos_modificados or creado
            grupos_actuales.append(grupo) # Agregar a la lista global del seed

            # 2. Lógica ramificada: DGs normales vs Administrador
            if nombre_grupo != "SEMAFORO_ADMIN":
                # ---------------------------------------------------------
                # RAMA A: Módulos estándar para las DGs (CRUD y Dashboard)
                # ---------------------------------------------------------
                
                # A.1. Módulo de Gestión de Acciones
                modulo_crud, creado = await asegurar_modulo(
                    grupo, "GESTION_ACCIONES", "Gestión del CRUD de Semáforo"
                )
                permisos_modificados = permisos_modificados or creado
                modulos_actuales.append(modulo_crud)

                acciones_crud, cambios = await asegurar_acciones(modulo_crud, ACCIONES_SEMAFORO_CRUD)
                permisos_modificados = permisos_modificados or cambios
                acciones_actuales.extend(acciones_crud)

                # A.2. Módulo de Dashboard
                modulo_dash, creado = await asegurar_modulo(
                    grupo, "DASHBOARD_SEMAFORO", "Estadísticas del Semáforo"
                )
                permisos_modificados = permisos_modificados or creado
                modulos_actuales.append(modulo_dash)

                acciones_dash, cambios = await asegurar_acciones(modulo_dash, ACCIONES_SEMAFORO_DASHBOARD)
                permisos_modificados = permisos_modificados or cambios
                acciones_actuales.extend(acciones_dash)

            else:
                # ---------------------------------------------------------
                # RAMA B: Módulo exclusivo para el Grupo Administrador
                # ---------------------------------------------------------
                
                modulo_admin, creado = await asegurar_modulo(
                    grupo, "CONTROL_GLOBAL_SEMAFORO", "Supervisión total del Semáforo"
                )
                permisos_modificados = permisos_modificados or creado
                modulos_actuales.append(modulo_admin) # ¡CRÍTICO! Para que no sea eliminado

                acciones_admin, cambios = await asegurar_acciones(modulo_admin, ACCIONES_SEMAFORO_ADMIN)
                permisos_modificados = permisos_modificados or cambios
                acciones_actuales.extend(acciones_admin) # ¡CRÍTICO! Para que no sean eliminadas
                
        # ==========================================
        # 7. USUARIO ADMIN PREDETERMINADO
        # ==========================================

        admin = await User.get_or_none(
            correo_electronico=ADMIN_EMAIL
        )

        if admin is None:
            admin = await User.create(
                curp=ADMIN_CURP,
                nombre="Administrador",
                primer_apellido="General",
                segundo_apellido="Sistema",
                correo_electronico=ADMIN_EMAIL,
                entidad_federativa_id=ADMIN_ENTIDAD_FEDERATIVA_ID,
                numero_telefono="5500000000",
                contrasena_hasheada=get_password_hash(
                    ADMIN_PASSWORD
                ),
                is_2fa_enabled=False,
                totp_secret=None,
                estatus=estatus_activo,
                instancia=instancia_sndif,
                intentos_login=0,
            )
            admin_creado = True

        else:
            admin_creado = False

            admin.curp = ADMIN_CURP
            admin.nombre = "Administrador"
            admin.primer_apellido = "General"
            admin.segundo_apellido = "Sistema"
            admin.entidad_federativa_id = (
                ADMIN_ENTIDAD_FEDERATIVA_ID
            )
            admin.numero_telefono = "5500000000"
            admin.estatus = estatus_activo
            admin.instancia = instancia_sndif
            admin.intentos_login = 0

            # No se modifica la contraseña, el secreto TOTP ni el estado 2FA
            # cuando el administrador ya existe.
            await admin.save(
                update_fields=[
                    "curp",
                    "nombre",
                    "primer_apellido",
                    "segundo_apellido",
                    "entidad_federativa_id",
                    "numero_telefono",
                    "estatus_id",
                    "instancia_id",
                    "intentos_login",
                ]
            )

        # ==========================================
        # 8. SINCRONIZAR ACCESOS DEL ADMIN
        # ==========================================

        grupos_retirados = await UsuarioGrupo.filter(
            usuario=admin
        ).exclude(
            grupo_id__in=[
                grupo.id
                for grupo in grupos_actuales
            ]
        ).delete()

        modulos_retirados = await UsuarioModulo.filter(
            usuario=admin
        ).exclude(
            modulo_id__in=[
                modulo.id
                for modulo in modulos_actuales
            ]
        ).delete()

        acciones_retiradas = await UsuarioAccion.filter(
            usuario=admin
        ).exclude(
            accion_id__in=[
                accion.id
                for accion in acciones_actuales
            ]
        ).delete()

        permisos_modificados = permisos_modificados or any(
            cantidad > 0
            for cantidad in [
                grupos_retirados,
                modulos_retirados,
                acciones_retiradas,
            ]
        )

        for grupo in grupos_actuales:
            _, creada = await UsuarioGrupo.get_or_create(
                usuario=admin,
                grupo=grupo,
            )
            permisos_modificados = permisos_modificados or creada

        for modulo in modulos_actuales:
            _, creada = await UsuarioModulo.get_or_create(
                usuario=admin,
                modulo=modulo,
            )
            permisos_modificados = permisos_modificados or creada

        for accion in acciones_actuales:
            _, creada = await UsuarioAccion.get_or_create(
                usuario=admin,
                accion=accion,
            )
            permisos_modificados = permisos_modificados or creada

        # Invalida tokens anteriores únicamente cuando el catálogo
        # o las asignaciones realmente cambiaron.
        if permisos_modificados and not admin_creado:
            await User.filter(
                id=admin.id
            ).update(
                token_version=F("token_version") + 1
            )

        # ==========================================
        # 8.5. CREACIÓN DE USUARIOS DE PRUEBA (SEMÁFORO)
        # ==========================================
        print("\nSincronizando usuarios de prueba para Semáforo...")
        contrasena_test = get_password_hash("Semaforo2026!")

        for u_data in USUARIOS_PRUEBA_SEMAFORO:
            user_test = await User.get_or_none(curp=u_data["curp"])
            
            if not user_test:
                user_test = await User.create(
                    curp=u_data["curp"],
                    nombre=u_data["nombre"],
                    primer_apellido=u_data["apellido"],
                    segundo_apellido="Prueba",
                    correo_electronico=f"{u_data['apellido'].lower()}@portusderechos.gob.mx",
                    entidad_federativa_id=9, # CDMX por defecto
                    numero_telefono="5500000000",
                    contrasena_hasheada=contrasena_test,
                    is_2fa_enabled=False,
                    estatus=estatus_activo,
                    instancia=instancia_sndif,
                    intentos_login=0,
                )
                print(f"- Usuario creado: {u_data['curp']}")
            
            # Buscar el grupo correspondiente
            grupo_correspondiente = next(g for g in grupos_semaforo_obj if g.nombre == u_data["grupo"])
            
            # Asignar Grupo al usuario
            await UsuarioGrupo.get_or_create(usuario=user_test, grupo=grupo_correspondiente)
            
            # Asignar los módulos y acciones de ese grupo al usuario
            modulos_del_grupo = await Modulo.filter(grupo=grupo_correspondiente)
            for mod in modulos_del_grupo:
                await UsuarioModulo.get_or_create(usuario=user_test, modulo=mod)
                acciones_del_modulo = await Accion.filter(modulo=mod)
                for acc in acciones_del_modulo:
                    await UsuarioAccion.get_or_create(usuario=user_test, accion=acc)

        # ==========================================
        # 9. RESULTADO DEL SEED
        # ==========================================

        print("")
        print("Seed ejecutado correctamente.")

        print("")
        print("Grupos vigentes:")
        print("- MESA_AYUDA")
        print("- FORMATOS_ATENCIONES")

        print("")
        print("Módulos de Mesa de Ayuda:")
        print("- BITACORA_ATENCIONES")
        print("- ADMINISTRACION_USUARIOS")
        print("- ADMINISTRACION_PERMISOS")
        print("- REPORTES_INDICADORES")

        print("")
        print("Módulos de Formatos de Atenciones:")
        print("- CAPTURA_FORMATOS")
        print("- GESTION_FORMATOS")
        print("- DASHBOARD_FORMATOS")
        print("- REPORTES_FORMATOS")

        print("")
        print("Acciones de Bitácora:")
        for nombre in ACCIONES_BITACORA:
            print(f"- {nombre}")

        print("")
        print("Acciones de Reportes e Indicadores:")
        for nombre in ACCIONES_REPORTES_INDICADORES:
            print(f"- {nombre}")

        print("")
        print("Acciones de Captura de Formatos:")
        for nombre in ACCIONES_CAPTURA_FORMATOS:
            print(f"- {nombre}")

        print("")
        print("Acciones de Gestión de Formatos:")
        for nombre in ACCIONES_GESTION_FORMATOS:
            print(f"- {nombre}")

        print("")
        print("Acciones de Dashboard de Formatos:")
        for nombre in ACCIONES_DASHBOARD_FORMATOS:
            print(f"- {nombre}")

        print("")
        print("Acciones de Reportes de Formatos:")
        for nombre in ACCIONES_REPORTES_FORMATOS:
            print(f"- {nombre}")

        print("")
        print(
            "El administrador tiene SUPER_ADMIN "
            "y todos los permisos vigentes."
        )

        print("")
        if admin_creado:
            print(
                "Administrador creado con la contraseña "
                "inicial de desarrollo."
            )
        else:
            print(
                "Administrador actualizado sin restablecer "
                "su contraseña ni su 2FA."
            )

    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
