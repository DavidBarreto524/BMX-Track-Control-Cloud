# Despliegue gratis — paso a paso

Guía para publicar **BMX Track Control Cloud** en internet sin costo, usando:

| Servicio | Rol | Costo |
|----------|-----|-------|
| [Neon](https://neon.tech) | Base de datos PostgreSQL | $0 |
| [Cloudinary](https://cloudinary.com) | Almacenar fotos | $0 |
| [Render](https://render.com) | Ejecutar la aplicación | $0 |
| [cron-job.org](https://cron-job.org) | Mantener la app activa (alertas 24/7) | $0 |

Tiempo estimado: **30–45 minutos**.

---

## Paso 0 — Requisitos en tu PC

- [ ] Cuenta en [GitHub](https://github.com)
- [ ] Node.js instalado (para `npx neonctl`, opcional)
- [ ] Python 3.12+ (ya lo tienes para desarrollo)

---

## Paso 1 — Subir el código a GitHub

Si el repo **ya está en GitHub**, salta al paso 2.

```powershell
cd "c:\Users\David Barreto\OneDrive - PARKING INTERNATIONAL_SAS\Escritorio\Proyect-01\bmx-track-control-cloud"

# Verifica que NO se suban secretos
git status
# .env y *.db deben estar ignorados

git add .
git commit -m "Preparar despliegue en Render con PostgreSQL y Cloudinary"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/bmx-track-control-cloud.git
git push -u origin main
```

> Crea el repositorio vacío en GitHub antes del `git push`.

---

## Paso 2 — Crear base de datos en Neon

### Opción A — Con el asistente (recomendado en Cursor)

```powershell
cd bmx-track-control-cloud
npx neonctl@latest init
```

1. Elige **Cursor** como editor.
2. Inicia sesión en Neon (cuenta gratis).
3. Crea un proyecto nuevo (ej. `bmx-track-control`).
4. Reinicia Cursor y escribe en el chat: **"Get started with Neon"**.

### Opción B — Manual en la consola

1. Entra a [console.neon.tech](https://console.neon.tech).
2. **New Project** → nombre `bmx-track-control` → región **AWS US East** (o la más cercana).
3. En **Dashboard → Connection string**, copia la URL que empieza con:
   ```
   postgresql://...
   ```
4. Guárdala; la usarás en Render.

> La app convierte automáticamente `postgresql://` a `postgresql+psycopg2://`. Pega la URL tal como la da Neon.

---

## Paso 3 — Crear cuenta en Cloudinary (fotos)

1. Regístrate en [cloudinary.com](https://cloudinary.com).
2. En el **Dashboard** anota:
   - **Cloud name**
   - **API Key**
   - **API Secret**
3. Sin Cloudinary, las fotos se pierden cuando Render reinicia el contenedor.

---

## Paso 4 — Generar una clave de sesión segura

En PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copia el resultado; será tu `SESSION_SECRET_KEY`.

---

## Paso 5 — Desplegar en Render

1. Entra a [render.com](https://render.com) e inicia sesión con **GitHub**.
2. **New +** → **Web Service**.
3. Conecta el repositorio `bmx-track-control-cloud`.
4. Configuración:

| Campo | Valor |
|-------|-------|
| **Name** | `bmx-track-control` |
| **Region** | Oregon (US West) o la más cercana |
| **Branch** | `main` |
| **Runtime** | **Docker** |
| **Instance Type** | **Free** |

5. En **Environment Variables**, agrega:

| Variable | Valor |
|----------|-------|
| `DATABASE_URL` | URL de Neon del paso 2 |
| `ENABLE_SCHEDULER` | `true` |
| `UPLOAD_CHECK_INTERVAL_MINUTES` | `5` |
| `DEFAULT_PHOTO_INTERVAL_MINUTES` | `120` |
| `SESSION_SECRET_KEY` | clave generada en paso 4 |
| `ADMIN_USERNAME` | `admin` (o el que prefieras) |
| `ADMIN_PASSWORD` | **contraseña fuerte** (no uses `admin123`) |
| `JIMMY_USERNAME` | `Jimmy` |
| `JIMMY_PASSWORD` | **contraseña fuerte** |
| `JIMMY_ROLE` | `supervisor` |
| `CLOUDINARY_CLOUD_NAME` | tu cloud name |
| `CLOUDINARY_API_KEY` | tu API key |
| `CLOUDINARY_API_SECRET` | tu API secret |

6. Clic en **Create Web Service**.
7. Espera 5–10 minutos el primer deploy.
8. Tu URL será algo como: `https://bmx-track-control.onrender.com`

### Probar

- Abre `https://TU-URL.onrender.com/login`
- Inicia sesión con admin / tu contraseña
- Sube una foto de prueba en un área
- Verifica en Cloudinary que la imagen apareció

---

## Paso 6 — Mantener la app despierta (alertas automáticas)

En el plan gratis, Render **apaga** la app tras 15 min sin tráfico. Eso detiene las alertas.

1. Crea cuenta en [cron-job.org](https://cron-job.org).
2. **Create cronjob**:
   - **Title:** `BMX keep-alive`
   - **URL:** `https://TU-URL.onrender.com/health`
   - **Schedule:** cada **10 minutos**
   - **Method:** GET
3. Guarda y activa el cron.

Con esto la app no se duerme y el scheduler de alertas sigue funcionando.

---

## Paso 7 — Probar desde el celular

1. Abre la URL de Render en el navegador del móvil.
2. Inicia sesión (Jimmy o admin).
3. Sube una foto en un área.
4. Revisa que las notificaciones y el mapa carguen bien.

---

## Resumen de URLs útiles

| Qué | Dónde |
|-----|-------|
| App en producción | `https://TU-APP.onrender.com` |
| Health check | `https://TU-APP.onrender.com/health` |
| Panel Neon | [console.neon.tech](https://console.neon.tech) |
| Fotos subidas | [cloudinary.com/console](https://cloudinary.com/console) |
| Logs de la app | Render → tu servicio → **Logs** |

---

## Solución de problemas

### Error al conectar a la base de datos
- Verifica que `DATABASE_URL` en Render sea la de Neon (con `?sslmode=require`).
- Revisa los logs en Render → **Logs**.

### Las fotos no se guardan
- Configura las tres variables `CLOUDINARY_*` en Render.
- Redeploy después de agregarlas.

### La app tarda ~1 minuto en cargar
- El plan gratis “despertó” tras inactividad. Configura cron-job.org (paso 6).

### Error 500 al entrar
- Revisa logs en Render.
- Asegúrate de que `SESSION_SECRET_KEY` esté definida.

### Cambié variables de entorno
- Render redeploya solo; si no, usa **Manual Deploy → Deploy latest commit**.

---

## Probar Neon en local (opcional)

Antes de desplegar, puedes probar con Neon desde tu PC:

1. Copia la URL de Neon en tu `.env`:
   ```
   DATABASE_URL=postgresql://...
   ```
2. Instala dependencias:
   ```powershell
   pip install -r requirements.txt
   ```
3. Arranca el servidor:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\dev-server.ps1
   ```
4. La app crea las tablas automáticamente al iniciar.

---

## Checklist final

- [ ] Código en GitHub (sin `.env` ni `.db`)
- [ ] Proyecto Neon creado y `DATABASE_URL` en Render
- [ ] Cloudinary configurado
- [ ] Contraseñas de producción cambiadas
- [ ] `SESSION_SECRET_KEY` única y larga
- [ ] Deploy en Render exitoso (verde)
- [ ] Cron en cron-job.org cada 10 min → `/health`
- [ ] Login y subida de foto probados desde el celular
