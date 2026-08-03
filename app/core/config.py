from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Login PorTusDerechos"
    VERSION: str = "1.0.0"
    TOTP_ISSUER: str = "Acceso Central - SNDIF"

    DATABASE_URL: str = "sqlite://database.db"

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SESSION_IDLE_TIMEOUT_MINUTES: int = 60 #Si el usuario no hace nada por 60 minutos, se debe cerrar sesión.

    # URLs permitidas para generar códigos temporales de redirección SSO.
    # Separar múltiples URLs con coma.
    ALLOWED_REDIRECT_URLS: str = "http://localhost:5173/medidas,http://127.0.0.1:5173/medidas"
    REDIRECT_CODE_EXPIRE_SECONDS: int = 60

    # Configuración SMTP para envío de correos
    SMTP_HOST: str = "sandbox.smtp.mailtrap.io"
    SMTP_PORT: int = 2525
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@portusderechos.gob.mx"

    # URL del frontend para construir links de activación
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()


TORTOISE_ORM = {
    "connections": {"default": settings.DATABASE_URL},
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