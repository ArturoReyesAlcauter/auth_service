import asyncio

from tortoise import Tortoise
from tortoise.expressions import F

from app.core.config import TORTOISE_ORM, settings
from app.core.security import get_password_hash
from app.services.semaforo_catalog import SEMAFORO_CATALOG
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
GRUPO_CRONOS = "CRONOS"


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

ACCIONES_CRONOS_PERSONAL_ORGANIZACION = {
    "VER_PERSONAL": (
        "Permite consultar el personal registrado en CRONOS."
    ),
    "CREAR_PERSONAL": (
        "Permite registrar personal y vincularlo con una identidad "
        "existente en auth_service."
    ),
    "ACTUALIZAR_PERSONAL": (
        "Permite actualizar la información laboral y organizacional "
        "del personal."
    ),
    "GESTIONAR_BAJA_PERSONAL": (
        "Permite registrar y administrar la baja institucional "
        "del personal conservando su historial."
    ),
    "GESTIONAR_UNIDADES": (
        "Permite crear, actualizar y administrar unidades "
        "organizacionales."
    ),
    "GESTIONAR_PUESTOS": (
        "Permite crear, actualizar y administrar puestos."
    ),
    "GESTIONAR_EQUIPOS": (
        "Permite crear, actualizar y administrar equipos de trabajo."
    ),
    "ASIGNAR_EQUIPO": (
        "Permite asignar personal a uno o varios equipos de trabajo."
    ),
    "ASIGNAR_SUPERVISOR": (
        "Permite establecer o modificar la relación de supervisión "
        "del personal."
    ),
    "VER_ORGANIGRAMA": (
        "Permite consultar la estructura y el organigrama "
        "organizacional de CRONOS."
    ),
}
ACCIONES_CRONOS_JORNADAS_SEDES = {
    "VER_JORNADAS": (
        "Permite consultar jornadas, horarios y esquemas asignados "
        "al personal."
    ),
    "GESTIONAR_ESQUEMAS_JORNADA": (
        "Permite crear, actualizar y administrar esquemas "
        "de jornada laboral."
    ),
    "ASIGNAR_JORNADAS": (
        "Permite asignar esquemas de jornada al personal "
        "y administrar su vigencia."
    ),
    "GESTIONAR_EXCEPCIONES_JORNADA": (
        "Permite registrar y administrar excepciones temporales "
        "a la jornada habitual del personal."
    ),
    "GESTIONAR_SEDES": (
        "Permite crear, actualizar y administrar las sedes "
        "de trabajo y sus parámetros de geolocalización."
    ),
}
ACCIONES_CRONOS_ASISTENCIA = {
    "REGISTRAR_ASISTENCIA": (
        "Permite registrar entradas y salidas utilizando los mecanismos "
        "de validación definidos por CRONOS."
    ),
    "VER_MI_ASISTENCIA": (
        "Permite consultar el historial propio de entradas, salidas, "
        "retardos y estado de puntualidad."
    ),
    "VER_ASISTENCIA_PERSONAL": (
        "Permite consultar la asistencia del personal dentro del alcance "
        "organizacional autorizado."
    ),
    "VER_ASISTENCIA_GLOBAL": (
        "Permite consultar la asistencia del personal de toda la "
        "organización."
    ),
    "AJUSTAR_ASISTENCIA": (
        "Permite realizar correcciones administrativas justificadas "
        "sobre registros de asistencia conservando su trazabilidad."
    ),
}
ACCIONES_CRONOS_VACACIONES_PERMISOS = {
    "SOLICITAR_VACACIONES": (
        "Permite al personal registrar solicitudes de vacaciones "
        "conforme a su disponibilidad y periodo correspondiente."
    ),
    "VER_MIS_VACACIONES": (
        "Permite consultar las solicitudes, periodos y estado "
        "de vacaciones propias."
    ),
    "VER_VACACIONES_PERSONAL": (
        "Permite consultar las vacaciones del personal dentro "
        "del alcance organizacional autorizado."
    ),
    "AUTORIZAR_VACACIONES": (
        "Permite aprobar, rechazar o gestionar solicitudes "
        "de vacaciones del personal autorizado."
    ),
    "GESTIONAR_SALDOS_VACACIONES": (
        "Permite administrar los saldos y días disponibles "
        "de vacaciones del personal."
    ),
    "SOLICITAR_PERMISO": (
        "Permite registrar solicitudes de permiso o ausencia "
        "con la justificación correspondiente."
    ),
    "VER_MIS_PERMISOS": (
        "Permite consultar las solicitudes de permiso propias "
        "y su estado."
    ),
    "VER_PERMISOS_PERSONAL": (
        "Permite consultar las solicitudes de permiso del personal "
        "dentro del alcance organizacional autorizado."
    ),
    "AUTORIZAR_PERMISOS": (
        "Permite aprobar, rechazar o gestionar solicitudes "
        "de permiso del personal autorizado."
    ),
    "GESTIONAR_DESCANSOS": (
        "Permite administrar días de descanso, compensaciones "
        "y sus periodos de vigencia."
    ),
}
ACCIONES_CRONOS_EVIDENCIAS = {
    "SUBIR_EVIDENCIA": (
        "Permite adjuntar evidencias relacionadas con asistencia, "
        "jornadas, permisos u otros procesos autorizados en CRONOS."
    ),
    "VER_MIS_EVIDENCIAS": (
        "Permite consultar las evidencias propias registradas "
        "en CRONOS."
    ),
    "VER_EVIDENCIAS_PERSONAL": (
        "Permite consultar las evidencias del personal dentro "
        "del alcance organizacional autorizado."
    ),
    "VALIDAR_EVIDENCIAS": (
        "Permite revisar y validar administrativamente evidencias "
        "conservando su archivo original y la trazabilidad "
        "del proceso de verificación."
    ),
}
ACCIONES_CRONOS_AUDITORIA = {
    "VER_BITACORA_AUDITORIA": (
        "Permite consultar la bitácora de auditoría de CRONOS "
        "para revisar acciones administrativas, cambios y trazabilidad."
    ),
}
ACCIONES_CRONOS_REPORTES = {
    "VER_DASHBOARD_CRONOS": (
        "Permite consultar indicadores generales de personal, "
        "jornadas, asistencia, vacaciones y permisos en CRONOS."
    ),
    "GENERAR_REPORTES_CRONOS": (
        "Permite generar reportes administrativos de información "
        "laboral y operativa registrada en CRONOS."
    ),
    "EXPORTAR_DATOS_CRONOS": (
        "Permite exportar información autorizada de CRONOS "
        "para análisis y seguimiento institucional."
    ),
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


# El catálogo de Control Agenda Nacional se define en
# app.services.semaforo_catalog y conserva los grupos técnicos SEMAFORO_*.


USUARIOS_PRUEBA_CRONOS = [
    {
        "curp": "CRONOS000000000001",
        "nombre": "Oliver",
        "primer_apellido": "Castañeda",
        "segundo_apellido": "Correa",
        "correo": "oliver.castaneda.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000002",
        "nombre": "Raúl Alberto",
        "primer_apellido": "Cantú",
        "segundo_apellido": "Martínez",
        "correo": "raul.cantu.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000003",
        "nombre": "Carlos",
        "primer_apellido": "Reyes",
        "segundo_apellido": "Ramírez",
        "correo": "carlos.reyes.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000004",
        "nombre": "Danton",
        "primer_apellido": "Bazaldua",
        "segundo_apellido": "Camarena",
        "correo": "danton.bazaldua.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000005",
        "nombre": "Paulina",
        "primer_apellido": "Martínez",
        "segundo_apellido": "Pérez",
        "correo": "paulina.martinez.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000006",
        "nombre": "Atenas",
        "primer_apellido": "Román",
        "segundo_apellido": "Fuentes",
        "correo": "atenas.roman.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000007",
        "nombre": "Alma",
        "primer_apellido": "Sandoval",
        "segundo_apellido": "Mancilla",
        "correo": "alma.sandoval.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000008",
        "nombre": "Julio",
        "primer_apellido": "Sánchez",
        "segundo_apellido": "López",
        "correo": "julio.sanchez.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000009",
        "nombre": "Arturo",
        "primer_apellido": "Reyes",
        "segundo_apellido": "Alcauter",
        "correo": "arturo.reyes.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000010",
        "nombre": "Brandon De Jesús",
        "primer_apellido": "Monroy",
        "segundo_apellido": None,
        "correo": "brandon.monroy.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000011",
        "nombre": "Javier Alfonso",
        "primer_apellido": "Hernández",
        "segundo_apellido": "Briones",
        "correo": "javier.hernandez.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000012",
        "nombre": "Francisco G.",
        "primer_apellido": "Cortés",
        "segundo_apellido": None,
        "correo": "francisco.cortes.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000013",
        "nombre": "Gustavo G.",
        "primer_apellido": "Morales",
        "segundo_apellido": None,
        "correo": "gustavo.morales.cronos@example.com",
    },
    {
        "curp": "CRONOS000000000014",
        "nombre": "Mauricio L.",
        "primer_apellido": "Pérez",
        "segundo_apellido": None,
        "correo": "mauricio.perez.cronos@example.com",
    },
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
        
        grupo_cronos, creado = await asegurar_grupo(
            GRUPO_CRONOS,
            (
                "Plataforma Integral de Gestión de Jornada y Personal "
                "para la administración de personal, estructura organizacional, "
                "jornadas, asistencia, vacaciones, permisos y procesos relacionados."
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
        # 5.5. MÓDULOS DE CRONOS
        # ==========================================

        modulo_cronos_personal, creado = await asegurar_modulo(
            grupo_cronos,
            "PERSONAL_ORGANIZACION",
            (
                "Gestión del personal, estructura organizacional, "
                "puestos, equipos de trabajo, supervisión y organigrama."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_cronos_personal, cambios = await asegurar_acciones(
            modulo_cronos_personal,
            ACCIONES_CRONOS_PERSONAL_ORGANIZACION,
        )
        permisos_modificados = permisos_modificados or cambios


        modulo_cronos_jornadas, creado = await asegurar_modulo(
            grupo_cronos,
            "JORNADAS_SEDES",
            (
                "Gestión de jornadas laborales, esquemas de horario, "
                "asignaciones, excepciones y sedes de trabajo."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_cronos_jornadas, cambios = await asegurar_acciones(
            modulo_cronos_jornadas,
            ACCIONES_CRONOS_JORNADAS_SEDES,
        )
        permisos_modificados = permisos_modificados or cambios
        
        modulo_cronos_asistencia, creado = await asegurar_modulo(
            grupo_cronos,
            "ASISTENCIA",
            (
                "Gestión de registros de entrada y salida, puntualidad, "
                "retardos, geolocalización y seguimiento de asistencia."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_cronos_asistencia, cambios = await asegurar_acciones(
            modulo_cronos_asistencia,
            ACCIONES_CRONOS_ASISTENCIA,
        )
        permisos_modificados = permisos_modificados or cambios
        
        modulo_cronos_vacaciones, creado = await asegurar_modulo(
            grupo_cronos,
            "VACACIONES_PERMISOS",
            (
                "Gestión de vacaciones, permisos, descansos, saldos, "
                "solicitudes y autorizaciones del personal."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_cronos_vacaciones, cambios = await asegurar_acciones(
            modulo_cronos_vacaciones,
            ACCIONES_CRONOS_VACACIONES_PERMISOS,
        )
        permisos_modificados = permisos_modificados or cambios
        
        modulo_cronos_evidencias, creado = await asegurar_modulo(
            grupo_cronos,
            "EVIDENCIAS",
            (
                "Gestión de evidencias asociadas con asistencia, jornadas, "
                "permisos y otros procesos de CRONOS."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_cronos_evidencias, cambios = await asegurar_acciones(
            modulo_cronos_evidencias,
            ACCIONES_CRONOS_EVIDENCIAS,
        )
        permisos_modificados = permisos_modificados or cambios
        
        
        modulo_cronos_auditoria, creado = await asegurar_modulo(
            grupo_cronos,
            "AUDITORIA",
            (
                "Consulta de la bitácora de auditoría y trazabilidad "
                "de acciones administrativas realizadas en CRONOS."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_cronos_auditoria, cambios = await asegurar_acciones(
            modulo_cronos_auditoria,
            ACCIONES_CRONOS_AUDITORIA,
        )
        permisos_modificados = permisos_modificados or cambios
        
        modulo_cronos_reportes, creado = await asegurar_modulo(
            grupo_cronos,
            "REPORTES",
            (
                "Consulta de indicadores, generación de reportes "
                "y exportación autorizada de información de CRONOS."
            ),
        )
        permisos_modificados = permisos_modificados or creado

        acciones_cronos_reportes, cambios = await asegurar_acciones(
            modulo_cronos_reportes,
            ACCIONES_CRONOS_REPORTES,
        )
        permisos_modificados = permisos_modificados or cambios
    

        # ==========================================
        # 6. CATÁLOGO VIGENTE
        # ==========================================

        grupos_actuales = [
            grupo_mesa_ayuda,
            grupo_formatos_atenciones,
            grupo_cronos,
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

        modulos_cronos = [
            modulo_cronos_personal,
            modulo_cronos_jornadas,
            modulo_cronos_asistencia,
            modulo_cronos_vacaciones,
            modulo_cronos_evidencias,
            modulo_cronos_auditoria,
            modulo_cronos_reportes,
        ]

        modulos_actuales = [
            *modulos_mesa_ayuda,
            *modulos_formatos_atenciones,
            *modulos_cronos,
        ]

        acciones_cronos = [
            *acciones_cronos_personal,
            *acciones_cronos_jornadas,
            *acciones_cronos_asistencia,
            *acciones_cronos_vacaciones,
            *acciones_cronos_evidencias,
            *acciones_cronos_auditoria,
            *acciones_cronos_reportes,
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
            *acciones_cronos,
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
        
        
        modulos_eliminados_cronos = await Modulo.filter(
            grupo=grupo_cronos
        ).exclude(
            id__in=[
                modulo.id
                for modulo in modulos_cronos
            ]
        ).delete()
        

        permisos_modificados = permisos_modificados or any(
            cantidad > 0
            for cantidad in [
                modulos_eliminados_mesa,
                modulos_eliminados_formatos,
                modulos_eliminados_cronos,
            ]
        )

        # ==========================================
        # 6.5. CATÁLOGO DE CONTROL AGENDA NACIONAL
        # ==========================================

        # Agenda resuelve el rol exclusivamente desde los grupos SEMAFORO_*.
        # Por ello estos nombres deben conservarse como grupos y no como módulos.
        for nombre_grupo, especificacion in SEMAFORO_CATALOG.items():
            grupo, creado = await asegurar_grupo(
                nombre_grupo,
                especificacion.descripcion,
            )
            permisos_modificados = permisos_modificados or creado
            grupos_actuales.append(grupo)

            for especificacion_modulo in especificacion.modulos:
                modulo, creado = await asegurar_modulo(
                    grupo,
                    especificacion_modulo.nombre,
                    especificacion_modulo.descripcion,
                )
                permisos_modificados = permisos_modificados or creado
                modulos_actuales.append(modulo)

                acciones, cambios = await asegurar_acciones(
                    modulo,
                    dict(especificacion_modulo.acciones),
                )
                permisos_modificados = permisos_modificados or cambios
                acciones_actuales.extend(acciones)

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
        # 8.4. USUARIOS DE PRUEBA DE CRONOS
        # ==========================================

        print("\nSincronizando usuarios de prueba para CRONOS...")

        contrasena_cronos = get_password_hash(
            settings.CRONOS_TEST_PASSWORD
        )

        for u_data in USUARIOS_PRUEBA_CRONOS:
            usuario_cronos = await User.get_or_none(
                curp=u_data["curp"]
            )

            if usuario_cronos is None:
                usuario_cronos = await User.create(
                    curp=u_data["curp"],
                    nombre=u_data["nombre"],
                    primer_apellido=u_data["primer_apellido"],
                    segundo_apellido=u_data["segundo_apellido"],
                    correo_electronico=u_data["correo"],
                    entidad_federativa_id=9,
                    numero_telefono=None,
                    contrasena_hasheada=contrasena_cronos,
                    is_2fa_enabled=False,
                    totp_secret=None,
                    creado_por=admin.id,
                    estatus=estatus_activo,
                    instancia=instancia_sndif,
                    intentos_login=0,
                )

                print(
                    f"- Usuario CRONOS creado: "
                    f"{usuario_cronos.nombre} "
                    f"{usuario_cronos.primer_apellido}"
                )

            await UsuarioGrupo.get_or_create(
                usuario=usuario_cronos,
                grupo=grupo_cronos,
            )
            
                    
    

        # ==========================================
        # 9. RESULTADO DEL SEED
        # ==========================================

        print("")
        print("Seed ejecutado correctamente.")

        print("")
        print("Grupos vigentes:")
        print("- MESA_AYUDA")
        print("- FORMATOS_ATENCIONES")
        print("- CRONOS")
        for nombre_grupo in SEMAFORO_CATALOG:
            print(f"- {nombre_grupo}")

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
