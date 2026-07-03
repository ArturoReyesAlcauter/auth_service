# Resumen de cambios - Integración Frontend auth_service

Cambios aplicados para alinear el backend con el contrato de integración frontend:

1. `/auth/login` ahora devuelve `temp_token`, no `temp_user_id`.
2. `/auth/setup`, `/auth/enable` y `/auth/login/2fa` ahora reciben `temp_token`.
3. Se mantiene el flujo aprobado de recuperación de contraseña: un usuario con permisos usa `POST /users/{user_id}/enviar-recuperacion-password` para enviar el correo. No se expone endpoint público de “Olvidé mi contraseña”.
4. Se mantiene `POST /auth/restablecer-password` únicamente para guardar la nueva contraseña usando el token recibido por correo.
5. Se agregó `/auth/redirect-code` y `/auth/exchange-code` para pasar del Login Universal a módulos externos sin exponer tokens en URL.
6. Se agregó formato estándar de errores `{ "code": "...", "detail": "..." }`.
7. Se valida que solo tokens `type = "access"` puedan consumir endpoints protegidos.
8. El `refresh_token` ahora incluye `jti`.
9. El campo `tokens_usuario.token` se amplió a 500 caracteres.

## Archivos principales modificados

- `app/api/routes/auth.py`
- `app/api/dependencies.py`
- `app/core/security.py`
- `app/core/config.py`
- `app/core/errors.py`
- `app/main.py`
- `app/models/user.py`
- `app/schemas/token.py`
- `app/services/auth_service.py`

## Migración necesaria si ya existe PostgreSQL

```sql
ALTER TABLE tokens_usuario ALTER COLUMN token TYPE VARCHAR(500);
```

También se agregó el archivo:

```text
docs/migracion_tokens_usuario_token_500.sql
```
