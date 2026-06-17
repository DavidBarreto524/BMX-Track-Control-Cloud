# BMX Track Control Cloud
Aplicaci?n para gestionar ?reas de trabajo de una cancha BMX con carga de fotos peri?dica y alertas por retraso.

## Qu? hace
- Crea y administra ?reas de trabajo de la cancha BMX.
- Permite subir fotos por ?rea y guardar historial.
- Detecta autom?ticamente ?reas sin fotos recientes seg?n un intervalo esperado.
- Ofrece panel web y API REST.
- Est? lista para despliegue en nube (Docker + variables de entorno).

## Stack
- FastAPI
- SQLAlchemy
- Jinja2 + Bootstrap
- APScheduler
- Cloudinary (opcional para almacenamiento en nube)

## Ejecutar localmente
1. Instala Python 3.12+.
2. Crea y activa entorno virtual.
3. Instala dependencias:
   `pip install -r requirements.txt`
4. Crea archivo `.env` basado en `.env.example`.
5. Levanta el servidor (recomendado, evita reinicios por `.venv`):
   `powershell -ExecutionPolicy Bypass -File .\scripts\dev-server.ps1`

   O manualmente:
   `uvicorn app.main:app --reload --reload-dir app --reload-exclude ".venv" --reload-exclude "**/.venv/**"`
6. Abre `http://127.0.0.1:8000`.

## Variables importantes
- `DATABASE_URL`: cadena de conexi?n (SQLite o PostgreSQL).
- `DEFAULT_PHOTO_INTERVAL_MINUTES`: intervalo esperado de subida por defecto.
- `UPLOAD_CHECK_INTERVAL_MINUTES`: cada cu?nto se ejecuta la revisi?n de alertas.
- `ENABLE_SCHEDULER`: habilita/deshabilita revisi?n autom?tica.
- `CLOUDINARY_*`: credenciales para subir im?genes a Cloudinary.

## API principal
- `POST /api/areas` crear ?rea.
- `GET /api/areas` listar ?reas y estado de carga.
- `POST /api/areas/{area_id}/photos` subir foto a un ?rea.
- `GET /api/areas/{area_id}/photos` historial de fotos.
- `GET /api/alerts` listar alertas (abiertas o todas).

## Despliegue en nube (Render/Railway/Fly.io)
1. Sube el proyecto a GitHub.
2. Crea un servicio web con Docker.
3. Define variables de entorno:
   - `DATABASE_URL` (PostgreSQL recomendado en producci?n).
   - `ENABLE_SCHEDULER=true`
   - Variables `CLOUDINARY_*` si usar?s almacenamiento de im?genes en nube.
4. Exp?n puerto `8000`.
5. Comando de inicio (si lo piden):
   `uvicorn app.main:app --host 0.0.0.0 --port 8000`

## Nota de producci?n
Para producci?n, usa PostgreSQL administrado y Cloudinary para no depender del disco local de la instancia.

