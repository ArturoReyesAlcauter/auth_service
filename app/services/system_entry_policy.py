"""Effective DGCP SSO authorization. All rights come from current DB grants.

A global SUPER_ADMIN action authorizes Configuracion, *not* other applications.
Unknown redirect targets are rejected instead of implicitly allowed.
"""
from __future__ import annotations

from urllib.parse import urlsplit
from fastapi import HTTPException, status
from app.services.agenda_system_access import derive_agenda_system_access

MESA_ACTIONS = frozenset({
    "VER_BITACORA", "CREAR_BITACORA", "ACTUALIZAR_BITACORA", "ELIMINAR_BITACORA",
    "SUBIR_ARCHIVO_BITACORA", "VER_DASHBOARD", "GENERAR_REPORTE_EXCEL",
    "GENERAR_REPORTE_PDF",
})
FORMATOS_ACTIONS = frozenset({
    "CAPTURAR_FORMATO_ATENCIONES", "VER_MIS_FORMATOS_ATENCIONES",
    "VER_FORMATO_PROPIO", "DESCARGAR_COMPROBANTE_FORMATO",
    "ACTUALIZAR_FORMATO_DEVUELTO", "VER_FORMATOS_RECIBIDOS",
    "VER_DETALLE_FORMATO", "INICIAR_REVISION_FORMATO",
    "DEVOLVER_FORMATO_CORRECCION", "VALIDAR_FORMATO_ATENCIONES",
    "ELIMINAR_FORMATO_ATENCIONES", "VER_DASHBOARD_FORMATOS",
    "VER_ESTADISTICAS_POR_ESTADO", "VER_ESTADISTICAS_POR_MUNICIPIO",
    "VER_ESTADISTICAS_POR_INDICADOR", "VER_ESTADISTICAS_POR_PERIODO",
    "GENERAR_EXCEL_FORMATO_INDIVIDUAL", "GENERAR_EXCEL_FORMATOS_CONSOLIDADO",
    "EXPORTAR_DATOS_FORMATOS",
})
CONFIG_ACTIONS = frozenset({
    "SUPER_ADMIN", "ADMINISTRAR_USUARIOS", "VER_USUARIOS",
    "VER_CATALOGO_PERMISOS", "ASIGNAR_GRUPOS_USUARIO",
    "ASIGNAR_MODULOS_USUARIO", "ASIGNAR_ACCIONES_USUARIO",
})
PRODUCTION_HOSTS = {
    "mesa.pfpnna.tech": "MESA_AYUDA",
    "agenda.pfpnna.tech": "CONTROL_AGENDA_NACIONAL",
    "config.pfpnna.tech": "ADMINISTRACION_SISTEMA",
    "formato.pfpnna.tech": "FORMATOS_ATENCIONES",
    "formatos.pfpnna.tech": "FORMATOS_ATENCIONES",
    "nna.pfpnna.tech": "FORMATOS_ATENCIONES",
    "directorio.pfpnna.tech": "DIRECTORIO_PROCURADORES",
    "procuradores.pfpnna.tech": "DIRECTORIO_PROCURADORES",
}
DEVELOPMENT_PORTS = {
    5175: "FORMATOS_ATENCIONES",
    5177: "DIRECTORIO_PROCURADORES",
    5179: "CONTROL_AGENDA_NACIONAL",
    5180: "ADMINISTRACION_SISTEMA",
}


def target_for_redirect(url: str) -> str | None:
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.fragment:
        return None
    if hostname in PRODUCTION_HOSTS and parsed.scheme == "https" and port in (None, 443):
        return PRODUCTION_HOSTS[hostname]
    if hostname in {"localhost", "127.0.0.1"} and parsed.scheme == "http":
        # El puerto 5173 históricamente aloja rutas de distintos sistemas.
        if port == 5173:
            if parsed.path.startswith("/app/formato-nna"):
                return "FORMATOS_ATENCIONES"
            if parsed.path.startswith("/app/usuarios"):
                return "ADMINISTRACION_SISTEMA"
            if parsed.path.startswith("/app/dashboard"):
                return "MESA_AYUDA"
            return None
        return DEVELOPMENT_PORTS.get(port)
    return None


def _grupos(permisos: object) -> list:
    if not isinstance(permisos, dict):
        return []
    grupos = permisos.get("grupos")
    return grupos if isinstance(grupos, list) else []


def _actions(grupos: list, group_name: str | None = None) -> set[str]:
    out: set[str] = set()
    for grupo in grupos:
        if not isinstance(grupo, dict):
            continue
        if group_name is not None and grupo.get("nombre") != group_name:
            continue
        for modulo in grupo.get("modulos", []) or []:
            if not isinstance(modulo, dict):
                continue
            for accion in modulo.get("acciones", []) or []:
                if isinstance(accion, dict) and isinstance(accion.get("nombre"), str):
                    out.add(accion["nombre"])
    return out


def has_system_access(target: str, permisos: object) -> bool:
    grupos = _grupos(permisos)
    if target == "MESA_AYUDA":
        return bool(_actions(grupos, "MESA_AYUDA") & MESA_ACTIONS)
    if target == "FORMATOS_ATENCIONES":
        return bool(_actions(grupos, "FORMATOS_ATENCIONES") & FORMATOS_ACTIONS)
    if target == "DIRECTORIO_PROCURADORES":
        # Directorio aún se habilita por membresía explícita al grupo.
        return any(isinstance(g, dict) and g.get("nombre") == "DIRECTORIO_PROCURADORES" for g in grupos)
    if target == "CONTROL_AGENDA_NACIONAL":
        return derive_agenda_system_access(grupos) is not None
    if target == "ADMINISTRACION_SISTEMA":
        return bool(_actions(grupos) & CONFIG_ACTIONS)
    return False


def require_system_entry(redirect_url: str, permisos: object) -> None:
    target = target_for_redirect(redirect_url)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SSO_TARGET_UNMAPPED", "detail": "El destino SSO no tiene una política de autorización explícita."},
        )
    if not has_system_access(target, permisos):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SYSTEM_ACCESS_REVOKED", "detail": "El usuario ya no cuenta con permisos para ese sistema."},
        )
