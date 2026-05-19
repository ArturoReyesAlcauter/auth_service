from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

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
        description="ID de la entidad federativa obtenido desde el catálogo externo"
    )
    
    numero_telefono: Optional[str] = Field(default=None, max_length=15)
    password: str = Field(
        ..., 
        min_length=8, 
        pattern=PASSWORD_REGEX,
        description=PASSWORD_ERROR_MSG
    )

    estatus_id: Optional[int] = None
    instancia_id: Optional[int] = None

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
    password: Optional[str] = Field(
        default=None, 
        min_length=8, 
        pattern=PASSWORD_REGEX,
        description=PASSWORD_ERROR_MSG
    )

    estatus_id: Optional[int] = None
    instancia_id: Optional[int] = None



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

    class Config:
        from_attributes = True


# ==========================================
# RECURSOS DEL SISTEMA
# ==========================================

class RegistroPrincipalRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None

    class Config:
        from_attributes = True


class ModuloRead(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None
    registro_principal_id: UUID

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

class UsuarioRegistroCreate(BaseModel):
    registro_id: UUID


class UsuarioModuloCreate(BaseModel):
    modulo_id: UUID


class UsuarioAccionCreate(BaseModel):
    accion_id: UUID


class UsuarioRegistroRead(BaseModel):
    id: UUID
    fecha_asignacion: datetime
    registro: RegistroPrincipalRead

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


class PermisosUsuarioRead(BaseModel):
    registros: List[RegistroPrincipalRead] = []
    modulos: List[ModuloRead] = []
    acciones: List[AccionRead] = []


class UserWithPermissionsRead(UserRead):
    permisos: PermisosUsuarioRead

    # ==========================================
# CATÁLOGO COMPLETO DE PERMISOS
# ==========================================
# Estos schemas sirven para devolver el árbol completo:
#
# Registro / Grupo
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


class RegistroCatalogoRead(BaseModel):
    # ID del registro o grupo principal.
    # Ejemplo: MP, MH, VF, RNCAS
    id: UUID

    # Nombre corto del registro/grupo.
    nombre: str

    # Descripción del registro/grupo.
    descripcion: Optional[str] = None

    # Lista de módulos que pertenecen a este registro/grupo.
    modulos: List[ModuloCatalogoRead] = []

    class Config:
        from_attributes = True


# ==========================================
# ASIGNACIÓN MASIVA DE PERMISOS
# ==========================================
# Este schema permite asignar a un usuario:
# - un registro/grupo
# - varios módulos
# - varias acciones
#
# Nota:
# Si se mandan acciones, el service también asignará automáticamente
# el módulo padre y el registro padre de esas acciones.


class UsuarioPermisosMasivosCreate(BaseModel):
    # Registro/grupo principal que se quiere asignar.
    # Es opcional porque podrías asignar solo módulos o acciones,
    # y el backend detectará automáticamente su registro padre.
    registro_id: Optional[UUID] = None

    # Lista de módulos que se quieren asignar al usuario.
    # Puede venir vacía.
    modulo_ids: List[UUID] = []

    # Lista de acciones que se quieren asignar al usuario.
    # Puede venir vacía.
    accion_ids: List[UUID] = []