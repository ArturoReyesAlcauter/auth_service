from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from app.core.config import settings, TORTOISE_ORM
from app.api.routes import auth, users
from app.core.errors import http_exception_handler, validation_exception_handler

ORIGENES_PERMITIDOS = [
    # Frontend Vite local
    "http://localhost:5173",
    "http://127.0.0.1:5173",

    # Puertos alternos de Vite si cambia automáticamente
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",

    # Puertos comunes de frontend
    "http://localhost:3000",
    "http://127.0.0.1:3000",

    # Backend / Swagger local
    "http://localhost:8000",
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
    allow_origins=ORIGENES_PERMITIDOS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.include_router(auth.router, prefix="/auth")
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
        "message": "API Central de Autenticación y Autorización - Sistema Integral de la DGCP. Ve a /docs para la documentación."
    }
