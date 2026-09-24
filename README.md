# Sistema de Login Biométrico — Django + FastAPI

Proyecto compuesto por dos aplicaciones independientes que se comunican por HTTP:

- **`backend/`** — API en **FastAPI** que expone autenticación por JWT y reconocimiento
  facial (detección con Haar Cascade + reconocimiento con LBPH, ambos de OpenCV).
  Documentación interactiva automática en `/docs` (Swagger).
- **`frontend/`** — Sitio **Django** con vistas, plantillas HTML5 y JavaScript que
  captura video de la cámara del usuario (`getUserMedia`), lo envía al backend y
  muestra el resultado.

```
fastapi_taller4/
├── backend/     # API FastAPI (Python, Pydantic, OpenCV, JWT)
└── frontend/    # Sitio Django (vistas, plantillas, JS de cámara)
```

## Cómo funciona el reconocimiento facial

Se usa OpenCV en vez de librerías basadas en `dlib` (como `face_recognition`)
porque estas últimas requieren compilar dependencias pesadas que suelen fallar
al desplegar en entornos serverless como Vercel. El enfoque usado es real
reconocimiento facial, no una simulación:

1. **Detección**: Haar Cascade (`haarcascade_frontalface_default.xml`, incluido con OpenCV)
   localiza el rostro dentro de la imagen capturada.
2. **Entrenamiento**: cada vez que un usuario registra una foto de referencia
   (`POST /face/register`), se guarda el recorte de su rostro y se reentrena un
   modelo **LBPH** (`cv2.face.LBPHFaceRecognizer_create`) con todas las muestras
   de todos los usuarios.
3. **Reconocimiento**: al capturar una nueva foto (`POST /face/recognize`), se
   detecta el rostro y se compara contra el modelo entrenado. Si la distancia
   (confianza) es menor al umbral configurado (`LBPH_CONFIDENCE_THRESHOLD`,
   por defecto 80), se considera una coincidencia.

Se recomienda registrar 3-5 fotos por usuario (distintos ángulos/gestos) para
mejorar la precisión.

## 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # ajusta SECRET_KEY, etc.
uvicorn main:app --reload --port 8001
```

- Swagger interactivo: http://127.0.0.1:8001/docs
- Endpoints principales:
  - `POST /auth/register` — crea un usuario (`username`, `email`, `password`)
  - `POST /auth/login` — devuelve un JWT (`access_token`)
  - `GET  /auth/me` — datos del usuario autenticado (requiere `Authorization: Bearer <token>`)
  - `POST /face/register` — guarda una foto de referencia del usuario autenticado
  - `POST /face/recognize` — compara una foto contra los rostros registrados (público)

## 2. Frontend (Django)

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # ajusta FASTAPI_BASE_URL si es necesario
python manage.py migrate
python manage.py runserver 8000
```

- Sitio: http://127.0.0.1:8000
- Flujo: `Registrarse` → `Iniciar sesión` → página de captura de cámara con
  botones **"Registrar mi rostro"** y **"Reconocer rostro"`.

> Importante: levanta primero el backend (puerto 8001) y luego el frontend
> (puerto 8000); el registro y el login de Django llaman al backend para
> crear el usuario también en la API y obtener su JWT.

## 3. Autenticación

- **Django** usa su sistema de sesiones estándar (`django.contrib.auth`) para
  proteger las vistas del sitio (`@login_required`).
- **FastAPI** usa JWT (`python-jose` + `passlib`/bcrypt) para proteger sus
  propios endpoints. Al iniciar sesión en Django, este también hace login
  contra FastAPI y guarda el `access_token` en `request.session`, que luego
  se envía como `Authorization: Bearer` al llamar `/face/register`.

Ambos sistemas están desacoplados a propósito: la API puede consumirse desde
cualquier otro cliente (una app móvil, Swagger, etc.) sin depender de Django.

## 4. Despliegue

El backend (FastAPI) se despliega en **Render** y el frontend (Django) en
**Vercel**, cada uno como proyecto independiente.

### Backend → Render (Web Service)

1. Sube el repo a GitHub (ya está en `sofiGonza/Taller4`).
2. En Render: **New + → Blueprint** y elige el repositorio. Render leerá
   `backend/render.yaml` y creará el Web Service con:
   - `rootDir: backend`
   - Instalación de las librerías de sistema que OpenCV necesita
     (`libglib2.0-0 libsm6 libgl1`) en el build
   - `startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Healthcheck en `/`
3. Al crearlo, Render te pedirá (variables con `sync: false`):
   - `SECRET_KEY` — clave aleatoria larga
   - `DATABASE_URL` — opcional; por defecto usa SQLite en el disco de Render
     (efímero; ver limitaciones abajo)
4. URL resultante, p.ej. `https://taller4-api.onrender.com`. Verifica
   `https://<url>/docs`.

> Si prefieres crear el Web Service a mano (sin Blueprint), usa los mismos
> valores: runtime Python, `rootDir backend`, el build y start de arriba, y
> las mismas variables de entorno.

### Postgres externo (para el frontend)

El frontend Django necesita una base de datos persistente; en Vercel
(serverless) el filesystem es de solo lectura y SQLite no funciona. Crea un
Postgres gratuito (Neon, Supabase o Vercel Postgres) y copia su
`DATABASE_URL` (formato `postgresql://…`).

### Frontend → Vercel

1. En Vercel: **Add New → Project → Importar el repo de GitHub**.
2. Configura el proyecto:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Other (Python/WSGI)
   - Vercel usará `vercel.json` (runtime `@vercel/python`, entrada
     `api/index.py` como WSGI, y build que ejecuta `collectstatic` para
     servir los estáticos con whitenoise).
3. Variables de entorno (Project Settings → Environment Variables):
   - `DJANGO_SECRET_KEY` — clave aleatoria larga
   - `DJANGO_DEBUG=False`
   - `DJANGO_ALLOWED_HOSTS=<tu-dominio>.vercel.app,.vercel.app`
   - `FASTAPI_BASE_URL=https://<tu-backend>.onrender.com` — la URL pública del
     backend de Render
   - `DATABASE_URL=postgresql://…` — el Postgres del paso anterior
4. Deploy. Verifica el sitio y el flujo completo (registro → login → cámara).

### Limitaciones (plan gratuito)

- **Render free** duerme la instancia tras ~15 minutos sin tráfico; el primer
  request tras dormir tarda unos segundos en responder (y OpenCV pesa al
  importar).
- El disco de Render es **efímero**: las fotos de referencia y el modelo LBPH
  (carpetas `data/` y `models_store/`) se guardan en el filesystem local, así
  que **se pierden si Render recicla la instancia**. La BD del backend (SQLite
  por defecto) sufre lo mismo, por lo que el sistema vuelve a un estado
  consistente: hay que re-registrar usuarios y sus rostros. Es aceptable para
  un taller/demo; para producción real conviene:
  - mover la BD del backend a un Postgres externo vía `DATABASE_URL`, y
  - subir las muestras de rostro y el modelo entrenado a un storage externo
    (S3, Vercel Blob, etc.) en lugar del filesystem local.

## 5. Pruebas realizadas

Antes de entregar este esqueleto se verificó, de punta a punta, con un
servidor FastAPI real y el test client de Django:

- Registro e inicio de sesión (Django + FastAPI sincronizados, JWT emitido).
- Registro de una foto de referencia con detección de rostro real (OpenCV).
- Reconocimiento facial exitoso contra el usuario registrado.
- Manejo de errores: imagen sin rostro (`422`), sin coincidencia registrada,
  backend no disponible.

## Próximos pasos sugeridos

- Agregar límite de intentos / rate limiting al login y al reconocimiento.
- Servir los archivos de datos biométricos desde un storage externo antes de
  desplegar a producción.
- Agregar tests automatizados (`pytest` para el backend, `pytest-django` o
  `unittest` para el frontend).
- Mostrar en la interfaz un recuadro sobre el rostro detectado (dibujando el
  bounding box que ya calcula `face_service.extract_face`).
