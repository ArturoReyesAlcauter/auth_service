import asyncio
import pyotp

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

    registros = [registro_mp, registro_mh, registro_vf, registro_rncas]

    # ==========================================
    # 4. MÓDULOS Y ACCIONES BASE
    # ==========================================

    acciones_creadas = []
    modulos_creados = []

    for registro in registros:
        modulo_datos_generales, _ = await Modulo.get_or_create(
            registro_principal=registro,
            nombre="DATOS_GENERALES",
            defaults={
                "descripcion": f"Módulo de datos generales para {registro.nombre}",
            },
        )

        modulos_creados.append(modulo_datos_generales)

        for nombre_accion in [
            f"LEER_{registro.nombre}_DATOS_GENERALES",
            f"CREAR_{registro.nombre}_DATOS_GENERALES",
            f"EDITAR_{registro.nombre}_DATOS_GENERALES",
            f"ELIMINAR_{registro.nombre}_DATOS_GENERALES",
        ]:
            accion, _ = await Accion.get_or_create(
                modulo=modulo_datos_generales,
                nombre=nombre_accion,
                defaults={
                    "descripcion": f"Permite {nombre_accion.lower().replace('_', ' ')}",
                },
            )

            acciones_creadas.append(accion)

    # ==========================================
    # 5. USUARIO ADMIN PREDETERMINADO
    # ==========================================

    totp_secret = pyotp.random_base32()

    admin, created = await User.get_or_create(
        curp=ADMIN_CURP,
        defaults={
            "nombre": "Administrador",
            "primer_apellido": "General",
            "segundo_apellido": "Sistema",
            "correo_electronico": ADMIN_EMAIL,
            "numero_telefono": "5500000000",
            "contrasena_hasheada": get_password_hash(ADMIN_PASSWORD),
            "is_2fa_enabled": True,
            "totp_secret": totp_secret,
            "estatus": estatus_activo,
            "instancia": instancia_sndif,
        },
    )

    if not created:
        admin.nombre = "Administrador"
        admin.primer_apellido = "General"
        admin.segundo_apellido = "Sistema"
        admin.correo_electronico = ADMIN_EMAIL
        admin.numero_telefono = "5500000000"
        admin.contrasena_hasheada = get_password_hash(ADMIN_PASSWORD)
        admin.is_2fa_enabled = True

        if not admin.totp_secret:
            admin.totp_secret = totp_secret
        else:
            totp_secret = admin.totp_secret

        admin.estatus = estatus_activo
        admin.instancia = instancia_sndif

        await admin.save()

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
    # 7. URI PARA GOOGLE AUTHENTICATOR
    # ==========================================

    totp = pyotp.TOTP(totp_secret)

    provisioning_uri = totp.provisioning_uri(
        name=ADMIN_EMAIL,
        issuer_name="Login PorTusDerechos",
    )

    print("")
    print("Seed ejecutado correctamente.")
    print("")
    print("Usuario administrador predeterminado:")
    print(f"CURP: {ADMIN_CURP}")
    print(f"Correo: {ADMIN_EMAIL}")
    print(f"Password: {ADMIN_PASSWORD}")
    print("")
    print("2FA Google Authenticator:")
    print(f"Secret: {totp_secret}")
    print("")
    print("Provisioning URI:")
    print(provisioning_uri)
    print("")
    print("Abre Google Authenticator y agrega la cuenta usando el secret manualmente.")
    print("")


    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())