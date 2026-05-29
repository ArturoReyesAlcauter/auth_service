from tortoise import fields
from tortoise.models import Model
import uuid


# ==========================================
# 1. USUARIOS Y SEGURIDAD
# ==========================================

class EstatusUsuario(Model):
    id = fields.IntField(pk=True)
    nombre = fields.CharField(
        max_length=50,
        description="Activo, En Proceso, Inactivo"
    )

    class Meta:
        table = "cat_estatus_usuarios"


class Instancia(Model):
    id = fields.IntField(pk=True)
    nombre = fields.CharField(
        max_length=100,
        description="Ej: Sistema Nacional DIF, Procuraduría..."
    )
    siglas = fields.CharField(
        max_length=20,
        description="Ej: SNDIF, PFPNNA, COMAR, UAPV"
    )

    class Meta:
        table = "cat_instancias"


class User(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)

    nombre = fields.CharField(max_length=100)
    primer_apellido = fields.CharField(max_length=100)
    segundo_apellido = fields.CharField(max_length=100, null=True)

    correo_electronico = fields.CharField(max_length=200, unique=True)
    curp = fields.CharField(max_length=18, unique=True)
    entidad_federativa_id = fields.IntField(null=True, description="ID de la entidad federativa obtenido desde el catálogo externo")
    numero_telefono = fields.CharField(max_length=15, null=True)

    contrasena_hasheada = fields.CharField(max_length=200, null=True)

    # Control de versiones de sesión / revocación
    token_version = fields.IntField(default=1, description="Incrementa para invalidar todos los tokens activos de este usuario")

    is_2fa_enabled = fields.BooleanField(default=False)
    totp_secret = fields.CharField(max_length=100, null=True)

    creado_por = fields.UUIDField(null=True)

    estatus = fields.ForeignKeyField(
        "models.EstatusUsuario",
        related_name="usuarios",
        null=True,
        on_delete=fields.SET_NULL
    )

    instancia = fields.ForeignKeyField(
        "models.Instancia",
        related_name="usuarios",
        null=True,
        on_delete=fields.SET_NULL
    )

    intentos_login = fields.IntField(default=0)

    fecha_correo_verificado = fields.DatetimeField(null=True)
    fecha_creacion = fields.DatetimeField(auto_now_add=True)
    fecha_actualizacion = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "usuarios"


class UltimaSesion(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)

    usuario = fields.OneToOneField(
        "models.User",
        related_name="ultima_sesion",
        on_delete=fields.CASCADE
    )

    fecha_inicio_sesion = fields.DatetimeField(null=True)

    fecha_creacion = fields.DatetimeField(auto_now_add=True)
    fecha_actualizacion = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "ultima_sesion"


class TokenUsuario(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)

    usuario = fields.ForeignKeyField(
        "models.User",
        related_name="tokens",
        on_delete=fields.CASCADE
    )

    token = fields.CharField(max_length=200, unique=True)

    tipo = fields.CharField(
        max_length=50,
        description="VERIFICACION_CORREO, RECUPERACION_CONTRASENA"
    )

    fecha_expiracion = fields.DatetimeField()
    fecha_creacion = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "tokens_usuario"


# ==========================================
# 2. JERARQUÍA DEL SISTEMA
# ==========================================

class Grupo(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)

    nombre = fields.CharField(
        max_length=100,
        description="Ej: VF, MH, MP, RNCAS"
    )

    descripcion = fields.CharField(max_length=200, null=True)

    class Meta:
        table = "grupos"


class Modulo(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)

    grupo = fields.ForeignKeyField(
        "models.Grupo",
        related_name="modulos",
        on_delete=fields.CASCADE
    )

    nombre = fields.CharField(
        max_length=100,
        description="Ej: Datos Generales, NNA, Medidas, Seguimiento"
    )

    descripcion = fields.CharField(max_length=200, null=True)

    class Meta:
        table = "modulos"


class Accion(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)

    modulo = fields.ForeignKeyField(
        "models.Modulo",
        related_name="acciones",
        on_delete=fields.CASCADE
    )

    nombre = fields.CharField(
        max_length=50,
        description="Ej: LEER_NNA, CREAR_NNA, EDITAR_NNA"
    )

    descripcion = fields.CharField(max_length=200, null=True)

    class Meta:
        table = "acciones"


# ==========================================
# 3. ASIGNACIONES DESCENTRALIZADAS
# ==========================================

class UsuarioGrupo(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)

    usuario = fields.ForeignKeyField(
        "models.User",
        related_name="grupos_asignados",
        on_delete=fields.CASCADE
    )

    grupo = fields.ForeignKeyField(
        "models.Grupo",
        related_name="usuarios_asignados",
        on_delete=fields.CASCADE
    )

    fecha_asignacion = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "usuario_grupos"
        unique_together = (("usuario", "grupo"),)


class UsuarioModulo(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)

    usuario = fields.ForeignKeyField(
        "models.User",
        related_name="modulos_asignados",
        on_delete=fields.CASCADE
    )

    modulo = fields.ForeignKeyField(
        "models.Modulo",
        related_name="usuarios_asignados",
        on_delete=fields.CASCADE
    )

    fecha_asignacion = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "usuario_modulos"
        unique_together = (("usuario", "modulo"),)


class UsuarioAccion(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)

    usuario = fields.ForeignKeyField(
        "models.User",
        related_name="acciones_asignadas",
        on_delete=fields.CASCADE
    )

    accion = fields.ForeignKeyField(
        "models.Accion",
        related_name="usuarios_asignados",
        on_delete=fields.CASCADE
    )

    fecha_asignacion = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "usuario_acciones"
        unique_together = (("usuario", "accion"),)