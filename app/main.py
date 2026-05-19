from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from app.core.config import settings, TORTOISE_ORM
from app.api.routes import auth, users

ORIGINES_PERMITIDOS = [
    "http://localhost:3000",      # Frontend (React/Vue/Angular - puerto típico)
    "http://127.0.0.1:3000",      # Variante de localhost
    "http://localhost:8000",      # El mismo Swagger
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
]

app = FastAPI(
    title="Auth Service",
    version=settings.VERSION,
    description="API independiente para autenticación, usuarios, roles y generación de tokens.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINES_PERMITIDOS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)

register_tortoise(
    app,
    config=TORTOISE_ORM,
    generate_schemas=False,
    add_exception_handlers=True,
)


@app.get("/")
async def root():
    return {
        "message": "Login Sistema de información Por Tus Derechos. Ve a /docs para la documentación."
    }