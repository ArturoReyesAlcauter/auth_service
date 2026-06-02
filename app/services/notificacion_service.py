from pathlib import Path

from app.core.config import settings
from app.models.user import User, EstatusUsuario
from app.services.email_service import enviar_correo_html


def render_template_email(nombre_template: str, contexto: dict) -> str:
    """
    Carga una plantilla HTML desde app/templates y reemplaza variables simples.
    """

    ruta_template = (
        Path(__file__).resolve().parent.parent
        / "templates"
        / nombre_template
    )

    html = ruta_template.read_text(encoding="utf-8")

    for clave, valor in contexto.items():
        html = html.replace(f"{{{{ {clave} }}}}", str(valor))

    return html


async def enviar_correo_cambio_estatus_usuario(
    user: User,
    estatus_anterior: EstatusUsuario | None,
    estatus_nuevo: EstatusUsuario,
    motivo: str | None = None,
) -> None:
    """
    Envía correo al usuario cuando su estatus cambia.

    Sirve para:
    - activación
    - inactivación
    - bloqueo por intentos
    - reactivación
    - cualquier estatus de cat_estatus_usuarios
    """

    nombre_completo = " ".join(
        parte
        for parte in [
            user.nombre,
            user.primer_apellido,
            user.segundo_apellido,
        ]
        if parte
    )

    estatus_anterior_nombre = (
        estatus_anterior.nombre
        if estatus_anterior
        else "Sin estatus anterior"
    )

    motivo_texto = motivo or "Actualización de estatus de cuenta."

    html = render_template_email(
        "email_cambio_estatus.html",
        {
            "nombre_completo": nombre_completo,
            "correo_electronico": user.correo_electronico,
            "curp": user.curp,
            "estatus_anterior": estatus_anterior_nombre,
            "estatus_nuevo": estatus_nuevo.nombre,
            "motivo": motivo_texto,
            "frontend_url": settings.FRONTEND_URL,
        },
    )

    enviar_correo_html(
        destinatario=user.correo_electronico,
        asunto=f"Actualización de estatus de cuenta - {estatus_nuevo.nombre}",
        html=html,
    )