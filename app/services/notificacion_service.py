from app.core.config import settings
from app.services.email_service import (
    enviar_correo_html,
    render_template_email,
)


def obtener_nombre_completo_usuario(user) -> str:
    """
    Construye el nombre completo del usuario.
    """

    return " ".join(
        parte
        for parte in [
            user.nombre,
            user.primer_apellido,
            user.segundo_apellido,
        ]
        if parte
    )


async def enviar_correo_activacion_usuario(
    user,
    token: str,
    sistemas_html: str,
) -> None:
    """
    Envía correo de activación para que el usuario cree su contraseña
    por primera vez.

    Lo usan:
    - POST /users/{user_id}/permisos
    - POST /users/{user_id}/reenviar-activacion
    """

    nombre_completo = obtener_nombre_completo_usuario(user)

    link_activacion = (
        f"{settings.FRONTEND_URL}/crear-password?token={token}"
    )

    html = render_template_email(
        "email_bienvenida.html",
        {
            "nombre_completo": nombre_completo,
            "curp": user.curp,
            "correo_electronico": user.correo_electronico,
            "link_activacion": link_activacion,
            "link_creacion_password": link_activacion,
            "link_crear_password": link_activacion,
            "sistemas_html": sistemas_html,
        },
    )

    enviar_correo_html(
        destinatario=user.correo_electronico,
        asunto="Bienvenida/o - Activación de cuenta institucional",
        html=html,
    )


async def enviar_correo_recuperacion_password(user, token: str) -> None:
    """
    Envía correo para restablecer contraseña.

    Lo usa:
    - POST /users/{user_id}/enviar-recuperacion-password
    """

    nombre_completo = obtener_nombre_completo_usuario(user)

    link_recuperacion = (
        f"{settings.FRONTEND_URL}/restablecer-password?token={token}"
    )

    html = render_template_email(
        "email_recuperacion_password.html",
        {
            "nombre_completo": nombre_completo,
            "link_recuperacion": link_recuperacion,
            "link_restablecer_password": link_recuperacion,
        },
    )

    enviar_correo_html(
        destinatario=user.correo_electronico,
        asunto="Restablecimiento de contraseña",
        html=html,
    )


async def enviar_correo_cambio_estatus_usuario(
    user,
    estatus_anterior,
    estatus_nuevo,
    motivo: str,
) -> None:
    """
    Envía correo cuando cambia el estatus de la cuenta.

    Lo usa:
    - PATCH /users/{user_id}/estatus/{estatus_id}
    """

    nombre_completo = obtener_nombre_completo_usuario(user)

    html = render_template_email(
        "email_cambio_estatus.html",
        {
            "nombre_completo": nombre_completo,
            "estatus_anterior": (
                estatus_anterior.nombre
                if estatus_anterior
                else "Sin estatus previo"
            ),
            "estatus_nuevo": estatus_nuevo.nombre,
            "motivo": motivo,
        },
    )

    enviar_correo_html(
        destinatario=user.correo_electronico,
        asunto="Actualización de estatus de cuenta",
        html=html,
    )