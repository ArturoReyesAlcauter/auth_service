from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from app.core.config import settings, TORTOISE_ORM
from app.api.routes import auth, users
from app.core.errors import http_exception_handler, validation_exception_handler



app = FastAPI(
    title="Auth Service",
    version=settings.VERSION,
    description="API independiente para autenticación, usuarios, roles y generación de tokens.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
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
