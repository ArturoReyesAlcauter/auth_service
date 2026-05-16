import asyncio

from tortoise import Tortoise

from app.core.config import TORTOISE_ORM
from app.core.security import get_password_hash
from app.models.user import (
    EstatusUsuario,
    Instancia,
    User,
    RegistroPrincipal,
    Modulo,
    Accion,
    UsuarioRegistro,
    UsuarioModulo,
    UsuarioAccion,
)


# ==========================================
# USUARIO ADMIN PREDETERMINADO
# ==========================================

ADMIN_CURP = "AURA000101HDFXXX01"
ADMIN_PASSWORD = "Admin12345!"
ADMIN_EMAIL = "admin@portusderechos.gob.mx"


async def main():
    await Tortoise.init(config=TORTOISE_ORM)

    print("Iniciando seed de base de datos...")

    # ==========================================
    # 1. ESTATUS DE USUARIO
    # ==========================================

    estatus_activo, _ = await EstatusUsuario.get_or_create(
        nombre="Activo"
    )

    await EstatusUsuario.get_or_create(nombre="En Proceso")
    await EstatusUsuario.get_or_create(nombre="Inactivo")

    # ==========================================
    # 2. INSTANCIAS
    # ==========================================

    instancia_sndif, _ = await Instancia.get_or_create(
        siglas="SNDIF",
        defaults={
            "nombre": "Sistema Nacional DIF",
        },
    )

    await Instancia.get_or_create(
        siglas="PFPNNA",
        defaults={
            "nombre": "Procuraduría Federal de Protección de Niñas, Niños y Adolescentes",
        },
    )

    await Instancia.get_or_create(
        siglas="COMAR",
        defaults={
            "nombre": "Comisión Mexicana de Ayuda a Refugiados",
        },
    )

    await Instancia.get_or_create(
        siglas="UAPV",
        defaults={
            "nombre": "Unidad de Atención a Población Vulnerable",
        },
    )

    # ==========================================
    # 3. GRUPOS PRINCIPALES
    # Internamente todavía usan el modelo RegistroPrincipal.
    # ==========================================

    grupo_mp, _ = await RegistroPrincipal.get_or_create(
        nombre="MP",
        defaults={
            "descripcion": "Registro de Medidas de Protección",
        },
    )

    grupo_mh, _ = await RegistroPrincipal.get_or_create(
        nombre="MH",
        defaults={
            "descripcion": "Registro de Movilidad Humana",
        },
    )

    grupo_vf, _ = await RegistroPrincipal.get_or_create(
        nombre="VF",
        defaults={
            "descripcion": "Registro de Derecho a Vivir en Familia",
        },
    )

    grupo_rncas, _ = await RegistroPrincipal.get_or_create(
        nombre="RNCAS",
        defaults={
            "descripcion": "Registro Nacional de Centros de Asistencia Social",
        },
    )

    grupos = [
        grupo_mp,
        grupo_mh,
        grupo_vf,
        grupo_rncas,
    ]

    # ==========================================
    # 4. MÓDULOS Y ACCIONES
    # ==========================================

    acciones_creadas = []
    modulos_creados = []

    # =====================================================
    # GRUPO MP - MÓDULO: EXPEDIENTES
    # =====================================================

    modulo_mp_expedientes, _ = await Modulo.get_or_create(
        registro_principal=grupo_mp,
        nombre="EXPEDIENTES",
        defaults={
            "descripcion": "Módulo core de expedientes del Registro de Medidas de Protección",
        },
    )

    modulos_creados.append(modulo_mp_expedientes)

    acciones_mp_expedientes = [
        {
            "nombre": "MP_LEER_REGISTRO",
            "descripcion": "Permite leer o consultar registros de medidas de protección. Permiso base para capturista y supervisor.",
        },
        {
            "nombre": "MP_CREAR_REGISTRO",
            "descripcion": "Permite crear un nuevo registro de medidas de protección. Permiso tipo capturista.",
        },
        {
            "nombre": "MP_ENVIAR_REVISION",
            "descripcion": "Permite enviar un registro a revisión. Permiso tipo capturista.",
        },
        {
            "nombre": "MP_APROBAR_REGISTRO",
            "descripcion": "Permite aprobar un registro de medidas de protección. Permiso tipo supervisor.",
        },
        {
            "nombre": "MP_DEVOLVER_REGISTRO",
            "descripcion": "Permite devolver un registro para corrección. Permiso tipo supervisor.",
        },
        {
            "nombre": "MP_VER_DASHBOARD",
            "descripcion": "Permite visualizar el dashboard del Registro de Medidas de Protección. Permiso base para capturista y supervisor.",
        },
    ]

    for accion_data in acciones_mp_expedientes:
        accion, _ = await Accion.get_or_create(
            modulo=modulo_mp_expedientes,
            nombre=accion_data["nombre"],
            defaults={
                "descripcion": accion_data["descripcion"],
            },
        )

        acciones_creadas.append(accion)

    # =====================================================
    # GRUPO MP - MÓDULO: SECCIONES
    # =====================================================

    modulo_mp_secciones, _ = await Modulo.get_or_create(
        registro_principal=grupo_mp,
        nombre="SECCIONES",
        defaults={
            "descripcion": "Módulo de secciones editables del Registro de Medidas de Protección",
        },
    )

    modulos_creados.append(modulo_mp_secciones)

    acciones_mp_secciones = [
        {
            "nombre": "MP_EDITAR_DATOS_GENERALES",
            "descripcion": "Permite editar la sección de datos generales. Permiso tipo capturista.",
        },
        {
            "nombre": "MP_EDITAR_IMPRESION_DIAGNOSTICA",
            "descripcion": "Permite editar la sección de impresión diagnóstica. Permiso tipo capturista.",
        },
        {
            "nombre": "MP_EDITAR_INTERVENCION",
            "descripcion": "Permite editar la sección de intervención. Permiso tipo capturista.",
        },
        {
            "nombre": "MP_EDITAR_PLAN_RESTITUCION",
            "descripcion": "Permite editar la sección de plan de restitución. Permiso tipo capturista.",
        },
        {
            "nombre": "MP_EDITAR_MEDIDAS_PROTECCION",
            "descripcion": "Permite editar la sección de medidas de protección. Permiso tipo capturista.",
        },
        {
            "nombre": "MP_EDITAR_CIERRE_CASO",
            "descripcion": "Permite editar la sección de cierre de caso. Permiso tipo capturista.",
        },
    ]

    for accion_data in acciones_mp_secciones:
        accion, _ = await Accion.get_or_create(
            modulo=modulo_mp_secciones,
            nombre=accion_data["nombre"],
            defaults={
                "descripcion": accion_data["descripcion"],
            },
        )

        acciones_creadas.append(accion)

    # =====================================================
    # MÓDULO ADMINISTRATIVO PARA TODOS LOS GRUPOS
    # =====================================================

    acciones_administracion_usuarios = [
        "ADMINISTRAR_USUARIOS",
        "CREAR_USUARIO",
        "VER_USUARIOS",
        "VER_USUARIO_DETALLE",
        "EDITAR_USUARIO",
        "DESACTIVAR_USUARIO",

        "VER_GRUPOS_USUARIO",
        "VER_MODULOS_USUARIO",
        "VER_ACCIONES_USUARIO",

        "ASIGNAR_GRUPOS_USUARIO",
        "ASIGNAR_MODULOS_USUARIO",
        "ASIGNAR_ACCIONES_USUARIO",

        "QUITAR_GRUPOS_USUARIO",
        "QUITAR_MODULOS_USUARIO",
        "QUITAR_ACCIONES_USUARIO",
    ]

    for grupo in grupos:
        modulo_usuarios, _ = await Modulo.get_or_create(
            registro_principal=grupo,
            nombre="ADMINISTRACION_USUARIOS",
            defaults={
                "descripcion": f"Módulo de administración de usuarios para {grupo.nombre}",
            },
        )

        modulos_creados.append(modulo_usuarios)

        for nombre_accion in acciones_administracion_usuarios:
            accion, _ = await Accion.get_or_create(
                modulo=modulo_usuarios,
                nombre=nombre_accion,
                defaults={
                    "descripcion": f"Permite {nombre_accion.lower().replace('_', ' ')}",
                },
            )

            acciones_creadas.append(accion)

    # ==========================================
    # 5. USUARIO ADMIN PREDETERMINADO
    # ==========================================
    # Buscamos por correo para evitar error de correo duplicado
    # si cambias el CURP del admin.

    admin = await User.get_or_none(correo_electronico=ADMIN_EMAIL)

    if admin:
        created = False

        admin.curp = ADMIN_CURP
        admin.nombre = "Administrador"
        admin.primer_apellido = "General"
        admin.segundo_apellido = "Sistema"
        admin.correo_electronico = ADMIN_EMAIL
        admin.numero_telefono = "5500000000"
        admin.contrasena_hasheada = get_password_hash(ADMIN_PASSWORD)

        # El admin debe configurar Google Authenticator en su primer login.
        admin.is_2fa_enabled = False
        admin.totp_secret = None

        admin.estatus = estatus_activo
        admin.instancia = instancia_sndif

        await admin.save()

    else:
        created = True

        admin = await User.create(
            curp=ADMIN_CURP,
            nombre="Administrador",
            primer_apellido="General",
            segundo_apellido="Sistema",
            correo_electronico=ADMIN_EMAIL,
            numero_telefono="5500000000",
            contrasena_hasheada=get_password_hash(ADMIN_PASSWORD),

            # El admin debe configurar Google Authenticator en su primer login.
            is_2fa_enabled=False,
            totp_secret=None,

            estatus=estatus_activo,
            instancia=instancia_sndif,
        )

    # ==========================================
    # 6. ASIGNAR TODOS LOS PERMISOS AL ADMIN
    # ==========================================

    for grupo in grupos:
        await UsuarioRegistro.get_or_create(
            usuario=admin,
            registro=grupo,
        )

    for modulo in modulos_creados:
        await UsuarioModulo.get_or_create(
            usuario=admin,
            modulo=modulo,
        )

    for accion in acciones_creadas:
        await UsuarioAccion.get_or_create(
            usuario=admin,
            accion=accion,
        )

    # ==========================================
    # 7. MENSAJE FINAL
    # ==========================================

    print("")
    print("Seed ejecutado correctamente.")
    print("")

    if created:
        print("Usuario administrador creado.")
    else:
        print("Usuario administrador actualizado.")

    print("")
    print("Usuario administrador predeterminado:")
    print(f"CURP: {ADMIN_CURP}")
    print(f"Correo: {ADMIN_EMAIL}")
    print(f"Password: {ADMIN_PASSWORD}")
    print("")
    print("Grupos creados/asignados:")
    print("- MP  : Registro de Medidas de Protección")
    print("- MH  : Registro de Movilidad Humana")
    print("- VF  : Registro de Derecho a Vivir en Familia")
    print("- RNCAS: Registro Nacional de Centros de Asistencia Social")
    print("")
    print("Módulos MP creados:")
    print("- EXPEDIENTES")
    print("- SECCIONES")
    print("")
    print("Acciones MP - EXPEDIENTES:")
    print("- MP_LEER_REGISTRO")
    print("- MP_CREAR_REGISTRO")
    print("- MP_ENVIAR_REVISION")
    print("- MP_APROBAR_REGISTRO")
    print("- MP_DEVOLVER_REGISTRO")
    print("- MP_VER_DASHBOARD")
    print("")
    print("Acciones MP - SECCIONES:")
    print("- MP_EDITAR_DATOS_GENERALES")
    print("- MP_EDITAR_IMPRESION_DIAGNOSTICA")
    print("- MP_EDITAR_INTERVENCION")
    print("- MP_EDITAR_PLAN_RESTITUCION")
    print("- MP_EDITAR_MEDIDAS_PROTECCION")
    print("- MP_EDITAR_CIERRE_CASO")
    print("")
    print("Permisos administrativos asignados:")
    print("- ADMINISTRAR_USUARIOS")
    print("- CREAR_USUARIO")
    print("- VER_USUARIOS")
    print("- ASIGNAR_GRUPOS_USUARIO")
    print("- ASIGNAR_MODULOS_USUARIO")
    print("- ASIGNAR_ACCIONES_USUARIO")
    print("- QUITAR_GRUPOS_USUARIO")
    print("- QUITAR_MODULOS_USUARIO")
    print("- QUITAR_ACCIONES_USUARIO")
    print("")
    print("2FA Google Authenticator:")
    print("El usuario administrador deberá configurar Google Authenticator en su primer inicio de sesión.")
    print("")
    print("Flujo esperado:")
    print("1. POST /login con CURP y contraseña")
    print("2. El sistema responderá status='pending_setup'")
    print("3. POST /setup con temp_user_id para generar QR")
    print("4. POST /enable con el código de Google Authenticator")
    print("5. El sistema entregará el JWT final")
    print("")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())