import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


def enviar_correo_html(
    destinatario: str,
    asunto: str,
    html: str,
):
    """
    Envía un correo HTML usando SMTP.

    En desarrollo se puede usar Mailtrap para simular la salida de correos
    sin enviarlos a usuarios reales.
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