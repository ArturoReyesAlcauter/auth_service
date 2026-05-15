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


ADMIN_CURP = "REAA950504HDFYLR01"
ADMIN_PASSWORD = "admin123"
ADMIN_EMAIL = "portusderechos@dif.gob.mx"


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
    # 3. REGISTROS PRINCIPALES
    # ==========================================

    registro_mp, _ = await RegistroPrincipal.get_or_create(
        nombre="MP",
        defaults={
            "descripcion": "Registro de Medidas de Protección",
        },
    )

    registro_mh, _ = await RegistroPrincipal.get_or_create(
        nombre="MH",
        defaults={
            "descripcion": "Registro de Movilidad Humana",
        },
    )

    registro_vf, _ = await RegistroPrincipal.get_or_create(
        nombre="VF",
        defaults={
            "descripcion": "Registro de Derecho a Vivir en Familia",
        },
    )

    registro_rncas, _ = await RegistroPrincipal.get_or_create(
        nombre="RNCAS",
        defaults={
            "descripcion": "Registro Nacional de Centros de Asistencia Social",
        },
    )

    registros = [
        registro_mp,
        registro_mh,
        registro_vf,
        registro_rncas,
    ]

    # ==========================================
    # 4. MÓDULOS Y ACCIONES BASE
    # ==========================================

    acciones_creadas = []
    modulos_creados = []

    for registro in registros:
        # ------------------------------------------
        # Módulo operativo: DATOS_GENERALES
        # ------------------------------------------
        modulo_datos_generales, _ = await Modulo.get_or_create(
            registro_principal=registro,
            nombre="DATOS_GENERALES",
            defaults={
                "descripcion": f"Módulo de datos generales para {registro.nombre}",
            },
        )

        modulos_creados.append(modulo_datos_generales)

        acciones_operativas = [
            f"LEER_{registro.nombre}_DATOS_GENERALES",
            f"CREAR_{registro.nombre}_DATOS_GENERALES",
            f"EDITAR_{registro.nombre}_DATOS_GENERALES",
            f"ELIMINAR_{registro.nombre}_DATOS_GENERALES",
        ]

        for nombre_accion in acciones_operativas:
            accion, _ = await Accion.get_or_create(
                modulo=modulo_datos_generales,
                nombre=nombre_accion,
                defaults={
                    "descripcion": f"Permite {nombre_accion.lower().replace('_', ' ')}",
                },
            )

            acciones_creadas.append(accion)

        # ------------------------------------------
        # Módulo administrativo: ADMINISTRACION_USUARIOS
        # ------------------------------------------
        modulo_usuarios, _ = await Modulo.get_or_create(
            registro_principal=registro,
            nombre="ADMINISTRACION_USUARIOS",
            defaults={
                "descripcion": f"Módulo de administración de usuarios para {registro.nombre}",
            },
        )

        modulos_creados.append(modulo_usuarios)

        acciones_administracion_usuarios = [
            "ADMINISTRAR_USUARIOS",
            "CREAR_USUARIO",
            "VER_USUARIOS",
            "VER_USUARIO_DETALLE",
            "EDITAR_USUARIO",
            "DESACTIVAR_USUARIO",
            "VER_REGISTROS_USUARIO",
            "VER_MODULOS_USUARIO",
            "VER_ACCIONES_USUARIO",
            "ASIGNAR_REGISTROS_USUARIO",
            "ASIGNAR_MODULOS_USUARIO",
            "ASIGNAR_ACCIONES_USUARIO",
        ]

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
    # Solución recomendada:
    # Primero buscamos por correo_electronico porque es único.
    # Si el admin ya existe, actualizamos su CURP.
    # Así evitamos el error:
    # duplicate key value violates unique constraint "usuarios_correo_electronico_key"

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

        # Dejamos el 2FA apagado para que tenga que configurarlo otra vez.
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

            # El admin NO queda con 2FA activo desde el seed.
            # Tendrá que configurarlo en su primer inicio de sesión.
            is_2fa_enabled=False,
            totp_secret=None,

            estatus=estatus_activo,
            instancia=instancia_sndif,
        )

    # ==========================================
    # 6. ASIGNAR TODOS LOS PERMISOS AL ADMIN
    # ==========================================

    for registro in registros:
        await UsuarioRegistro.get_or_create(
            usuario=admin,
            registro=registro,
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
    print("Permisos asignados:")
    print("- Todos los registros principales")
    print("- Todos los módulos")
    print("- Todas las acciones operativas")
    print("- Todas las acciones administrativas de usuarios")
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