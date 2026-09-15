import re
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# Expresión regular para contraseñas fuertes
PASSWORD_REGEX = r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&._-])[A-Za-z\d@$!%*?&._-]{8,}$"
PASSWORD_ERROR_MSG = "La contraseña debe tener mínimo 8 caracteres, una mayúscula, una minúscula, un número y un carácter especial."
# ==========================================
# CATÁLOGOS
# ==========================================

class EstatusUsuarioRead(BaseModel):
    id: int
    nombre: str

    class Config:
        from_attributes = True


class InstanciaRead(BaseModel):
    id: int
    nombre: str
    siglas: str

    class Config:
        from_attributes = True


# ==========================================
# USUARIOS
# ==========================================

class UserCreate(BaseModel):
    nombre: str = Field(..., max_length=100)
    primer_apellido: str = Field(..., max_length=100)
    segundo_apellido: Optional[str] = Field(default=None, max_length=100)

    correo_electronico: EmailStr = Field(..., max_length=200)
    curp: str = Field(..., min_length=18, max_length=18)

    entidad_federativa_id: int = Field(
        ...,
        gt=0,
        description="ID de la entidad federativa obtenido desde el catálogo externo",
    )

    numero_telefono: Optional[str] = Field(default=None, max_length=15)

    estatus_id: Optional[int] = None
    instancia_id: Optional[int] = None

    grupo_id: UUID = Field(
        ...,
        description="ID del grupo/registro al que pertenecerá el usuario desde su creación",
    )



class UserUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    primer_apellido: Optional[str] = Field(default=None, max_length=100)
    segundo_apellido: Optional[str] = Field(default=None, max_length=100)

    correo_electronico: Optional[EmailStr] = Field(default=None, max_length=200)
    curp: Optional[str] = Field(default=None, min_length=18, max_length=18)

    entidad_federativa_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID de la entidad federativa obtenido desde el catálogo externo",
    )

    numero_telefono: Optional[str] = Field(default=None, max_length=15)

    estatus_id: Optional[int] = None
    instancia_id: Optional[int] = None



class UserMeUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    primer_apellido: Optional[str] = Field(default=None, max_length=100)
    segundo_apellido: Optional[str] = Field(default=None, max_length=100)

    correo_electronico: Optional[EmailStr] = Field(default=None, max_length=200)
    numero_telefono: Optional[str] = Field(default=None, max_length=15)




class CrearPasswordPrimeraVez(BaseModel):
    token: str
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def validar_password_fuerte(cls, v: str) -> str:
        if not re.match(PASSWORD_REGEX, v):
            raise ValueError(PASSWORD_ERROR_MSG)
        return v


class CambiarPasswordUsuario(BaseModel):
    password_actual: str
    password_nueva: str = Field(..., min_length=8)

    @field_validator("password_nueva")
    @classmethod
    def validar_password_fuerte(cls, v: str) -> str:
        if not re.match(PASSWORD_REGEX, v):
            raise ValueError(PASSWORD_ERROR_MSG)
        return v



class UserRead(BaseModel):
    id: UUID

    nombre: str
    primer_apellido: str
    segundo_apellido: Optional[str] = None

    correo_electronico: EmailStr
    curp: str
    entidad_federativa_id: Optional[int] = None
    numero_telefono: Optional[str] = None

    is_2fa_enabled: bool

    estatus: Optional[EstatusUsuarioRead] = None
    instancia: Optional[InstanciaRead] = None

    intentos_login: int
    fecha_correo_verificado: Optional[datetime] = None
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    class Config:
        from_attributes = True


class GrupoUsuarioListRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None

    class Config:
        from_attributes = True



class AccionUsuarioListRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None

    class Config:
        from_attributes = True


class ModuloUsuarioListRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None
    acciones: List[AccionUsuarioListRead] = Field(default_factory=list)

    class Config:
        from_attributes = True


class GrupoUsuarioListRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None

    # Solo se enviará para SUPER_ADMIN.
    # Para admins normales irá como None y FastAPI lo ocultará.
    modulos: Optional[List[ModuloUsuarioListRead]] = None

    class Config:
        from_attributes = True



class UserListPublic(BaseModel):
    id: UUID
    nombre: str
    primer_apellido: str
    segundo_apellido: Optional[str] = None
    correo_electronico: EmailStr
    curp: str
    entidad_federativa_id: Optional[int] = None
    numero_telefono: Optional[str] = None

    estatus: Optional[EstatusUsuarioRead] = None
    instancia: Optional[InstanciaRead] = None

    grupos: List[GrupoUsuarioListRead] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ==========================================
# RECURSOS DEL SISTEMA
# ==========================================

class GrupoRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None

    class Config:
        from_attributes = True


class ModuloRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None
    grupo_id: UUID

    class Config:
        from_attributes = True


class AccionRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None
    modulo_id: UUID

    class Config:
        from_attributes = True


# ==========================================
# ASIGNACIONES
# ==========================================

class UsuarioGrupoCreate(BaseModel):
    grupo_id: UUID


class UsuarioModuloCreate(BaseModel):
    modulo_id: UUID


class UsuarioAccionCreate(BaseModel):
    accion_id: UUID


class UsuarioGrupoRead(BaseModel):
    id: UUID
    fecha_asignacion: datetime
    grupo: GrupoRead

    class Config:
        from_attributes = True


class UsuarioModuloRead(BaseModel):
    id: UUID
    fecha_asignacion: datetime
    modulo: ModuloRead

    class Config:
        from_attributes = True


class UsuarioAccionRead(BaseModel):
    id: UUID
    fecha_asignacion: datetime
    accion: AccionRead

    class Config:
        from_attributes = True


class AccionPermisoRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None

    class Config:
        from_attributes = True


class ModuloPermisoRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None
    acciones: List[AccionPermisoRead] = []

    class Config:
        from_attributes = True


class GrupoPermisoRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None
    modulos: List[ModuloPermisoRead] = []

    class Config:
        from_attributes = True


class PermisosUsuarioRead(BaseModel):
    grupos: List[GrupoPermisoRead] = []


class UserWithPermissionsRead(UserRead):
    permisos: PermisosUsuarioRead

    # ==========================================
# CATÁLOGO COMPLETO DE PERMISOS
# ==========================================
# Estos schemas sirven para devolver el árbol completo:
#
# Grupo
#   -> Módulos
#       -> Acciones
#
# Este árbol se usa para que el frontend pueda mostrar todos los permisos
# disponibles sin tener que consultar manualmente la base de datos.


class AccionCatalogoRead(BaseModel):
    # ID de la acción.
    # Ejemplo: permiso para crear, leer, aprobar, editar, etc.
    id: UUID

    # Nombre técnico de la acción.
    # Ejemplo: MP_CREAR_REGISTRO, VER_USUARIOS, ASIGNAR_ACCIONES_USUARIO
    nombre: str

    # Descripción legible de lo que permite hacer esta acción.
    descripcion: Optional[str] = None

    class Config:
        from_attributes = True


class ModuloCatalogoRead(BaseModel):
    # ID del módulo.
    # Ejemplo: EXPEDIENTES, SECCIONES, ADMINISTRACION_USUARIOS
    id: UUID

    # Nombre del módulo.
    nombre: str

    # Descripción del módulo.
    descripcion: Optional[str] = None

    # Lista de acciones que pertenecen a este módulo.
    acciones: List[AccionCatalogoRead] = []

    class Config:
        from_attributes = True


class GrupoCatalogoRead(BaseModel):
    # ID del grupo.
    # Ejemplo: MP, MH, VF, RNCAS
    id: UUID

    # Nombre corto del grupo.
    nombre: str

    # Descripción del grupo.
    descripcion: Optional[str] = None

    # Lista de módulos que pertenecen a este grupo.
    modulos: List[ModuloCatalogoRead] = []

    class Config:
        from_attributes = True


# ==========================================
# ASIGNACIÓN MASIVA DE PERMISOS
# ==========================================
# Este schema permite asignar permisos a un usuario en una sola petición.
#
# Puede asignar:
# - Un grupo directo usando grupo_id.
# - Varios módulos usando modulo_ids.
# - Varias acciones usando accion_ids.
#
# Reglas importantes:
# - Si se manda grupo_id, se asigna ese grupo directamente.
# - Si se mandan módulos, el service asignará automáticamente
#   el grupo padre de cada módulo.
# - Si se mandan acciones, el service asignará automáticamente
#   la acción, su módulo padre y el grupo padre de ese módulo.
#
# Por eso, para asignar permisos de varios grupos en una sola petición,
# se debe mandar grupo_id=None y agregar en modulo_ids o accion_ids
# elementos que pertenezcan a distintos grupos.
#
# Ejemplo:
# {
#   "grupo_id": null,
#   "modulo_ids": [
#       "uuid-modulo-del-grupo-mp",
#       "uuid-modulo-del-grupo-mh"
#   ],
#   "accion_ids": []
# }
#
# En ese caso, el backend asignará automáticamente:
# - el módulo de MP
# - el grupo MP
# - el módulo de MH
# - el grupo MH
#
# Este endpoint también forma parte del flujo de activación:
# - Si el usuario todavía no tiene contraseña, al asignarle permisos
#   se envía el correo de bienvenida/activación.
# - Ese correo contiene el enlace para crear la contraseña por primera vez.
# - Si el usuario ya tiene contraseña, no se vuelve a enviar ese correo.


class UsuarioPermisosDeltaCreate(BaseModel):
    """Delta completo de permisos aplicado en una sola operación administrativa."""

    grupo_ids_agregar: List[UUID] = Field(default_factory=list)
    grupo_ids_quitar: List[UUID] = Field(default_factory=list)
    modulo_ids_agregar: List[UUID] = Field(default_factory=list)
    modulo_ids_quitar: List[UUID] = Field(default_factory=list)
    accion_ids_agregar: List[UUID] = Field(default_factory=list)
    accion_ids_quitar: List[UUID] = Field(default_factory=list)


class UsuarioPermisosMasivosCreate(BaseModel):
    # Grupo que se quiere asignar directamente.
    #
    # Es opcional porque también se pueden asignar solo módulos o acciones.
    # En ese caso, el backend detecta automáticamente los grupos padre.
    #
    # Para asignar permisos de varios grupos en una sola petición,
    # usar grupo_id=None y mandar módulos/acciones de distintos grupos.
    grupo_id: Optional[UUID] = None

    # Lista de módulos que se quieren asignar al usuario.
    #
    # Puede venir vacía.
    # Si se mandan módulos, el backend también asignará automáticamente
    # el grupo padre de cada módulo.
    modulo_ids: List[UUID] = []

    # Lista de acciones que se quieren asignar al usuario.
    #
    # Puede venir vacía.
    # Si se mandan acciones, el backend también asignará automáticamente:
    # - la acción
    # - el módulo padre
    # - el grupo padre
    accion_ids: List[UUID] = []