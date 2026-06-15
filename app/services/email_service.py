import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


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


def enviar_correo_html(
    destinatario: str,
    asunto: str,
    html: str,
):
    """
    Envía un correo HTML usando SMTP.
    """

    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"] = asunto
    mensaje["From"] = settings.SMTP_FROM
    mensaje["To"] = destinatario

    mensaje.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as servidor:
        servidor.starttls()
        servidor.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        servidor.sendmail(
            settings.SMTP_FROM,
            destinatario,
            mensaje.as_string(),
        )