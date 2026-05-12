from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from app.core.config import settings, TORTOISE_ORM
from app.api.routes import auth, users

app = FastAPI(
    title="Auth Service",
    version=settings.VERSION,
    description="API independiente para autenticación, usuarios, roles y generación de tokens.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        "message": "Auth Service funcionando correctamente. Ve a /docs para la documentación."
    }