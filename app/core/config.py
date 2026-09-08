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
    #para los usuarios ficticios que compondran el organigrama de cronos, de una vez se les asignara su usuario y contraseña y no quiero que sea el mismo para el usuario seed del super dios admin
    CRONOS_TEST_PASSWORD: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7


    # ==========================================
    # COOKIE SEGURA PARA REFRESH TOKEN
    # ==========================================

    # Nombre único de la cookie utilizada por auth_service.
    REFRESH_COOKIE_NAME: str = "dgcp_refresh_token"

    # En desarrollo local usamos HTTP, por lo que debe ser False.
    # En producción con HTTPS deberá configurarse como True.
    REFRESH_COOKIE_SECURE: bool = False

    # Política SameSite inicial.
    # "lax" funciona para nuestra arquitectura local actual.
    REFRESH_COOKIE_SAMESITE: str = "lax"

    # La cookie solamente será enviada a endpoints de autenticación.
    REFRESH_COOKIE_PATH: str = "/auth"

    # Se deja sin dominio explícito para crear una cookie host-only.
    REFRESH_COOKIE_DOMAIN: str | None = None

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

        # ==========================================
    # ORÍGENES AUTORIZADOS PARA CORS / CSRF
    # ==========================================

    CORS_ALLOWED_ORIGINS: list[str] = [
        # --- IPs DEL SERVIDOR (PRODUCCIÓN) ---
        "http://10.2.5.68:5173",
        "http://10.2.5.68:5174",
        "http://10.2.5.68:5175",
        "http://10.2.5.68:5177",
        "http://10.2.5.68:5179",
        "http://10.2.5.68:5180",

        # --- LOCALHOST (DESARROLLO) ---
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",

        # Directorio de Procuradores
        "http://127.0.0.1:5177",

        # Control Agenda Nacional
        "http://127.0.0.1:5179",

        # Configuración
        "http://127.0.0.1:5180",

        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8001",
    ]

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
