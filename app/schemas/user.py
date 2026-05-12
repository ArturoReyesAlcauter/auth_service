from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


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

    numero_telefono: Optional[str] = Field(default=None, max_length=15)
    password: str = Field(..., min_length=8)

    estatus_id: Optional[int] = None
    instancia_id: Optional[int] = None


class UserRead(BaseModel):
    id: UUID

    nombre: str
    primer_apellido: str
    segundo_apellido: Optional[str] = None

    correo_electronico: EmailStr
    curp: str
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