from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración general de auth_service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    PROJECT_NAME: str = (       
        "API Central de Autenticación y Autorización"
    )
    VERSION: str = "1.0.0"
    TOTP_ISSUER: str = "Acceso Central - SNDIF"

    DATABASE_URL: str = "sqlite://database.db"

    SECRET_KEY: str
    ADMIN_INITIAL_PASSWORD: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Tiempo máximo de inactividad de una sesión.
    SESSION_IDLE_TIMEOUT_MINUTES: int = 60

    # URLs exactas autorizadas para redirecciones SSO.
    # Deben permanecer como texto separado por comas.
    ALLOWED_REDIRECT_URLS: str = (
        "http://127.0.0.1:5173/app/dashboard,"
        "http://127.0.0.1:5173/app/formato-nna,"
        "http://127.0.0.1:5173/app/usuarios,"
        "http://127.0.0.1:5175/app/dashboard,"
        "http://127.0.0.1:5177/procuradores,"
        "http://127.0.0.1:5179/app/dashboard,"
        "http://127.0.0.1:5180/app/dashboard"
    )

    REDIRECT_CODE_EXPIRE_SECONDS: int = 60
    # Configuración SMTP para envío de correos.
    SMTP_HOST: str = "sandbox.smtp.mailtrap.io"
    SMTP_PORT: int = 2525
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@portusderechos.gob.mx"

    # URL base del frontend para enlaces de activación.
    FRONTEND_URL: str = "http://localhost:5173"


settings = Settings()


TORTOISE_ORM = {
    "connections": {
        "default": settings.DATABASE_URL,
    },
    "apps": {
        "models": {
            "models": [
                "app.models.user",
                "aerich.models",
            ],
            "default_connection": "default",
        },
    },
}
